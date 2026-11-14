"""NagrikOS demonstration API. All records seeded on first boot are SYNTHETIC."""
from __future__ import annotations
import csv, io, json, os, re, secrets, time, hashlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from .ai import analyze, mock_image_description
from .auth import (current_user, hash_password, verify_password, require_admin, require_official,
                   encrypt_totp, decrypt_totp, generate_totp_secret, totp_counter,
                   require_officer, token_hash, apply_cookies, remove_cookies, verify_csrf,
                   SESSION_COOKIE, SESSION_SECONDS, SESSION_IDLE_SECONDS)
from .data import CATEGORIES, DEPARTMENTS, DISTRICTS
from .db import connect, initialize, iso, reset_demo

UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', str(Path(__file__).resolve().parent.parent / 'uploads')))
VALID_STATUSES = {'new','in_progress','escalated','resolved'}
VALID_PRIORITIES = {'low','medium','high','critical'}

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix': UPLOAD_DIR.chmod(0o700)
    yield

app = FastAPI(title='NagrikOS Demo API', version='1.0.0', lifespan=lifespan,
              description='Fully local operational prototype. AI is deterministic and demo data is synthetic.')
allowed_origins = [x.strip() for x in os.environ.get('CORS_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True,
                   allow_methods=['GET','POST','PATCH','DELETE'], allow_headers=['Content-Type','X-CSRF-Token'])

@app.middleware('http')
async def security_headers_and_csrf(request: Request, call_next):
    # Deny cross-site state-changing API calls, even if a browser accidentally sends cookies.
    if request.url.path.startswith('/api/') and request.method in {'POST','PATCH','PUT','DELETE'}:
        origin = request.headers.get('origin')
        if origin and origin not in allowed_origins and origin != f'{request.url.scheme}://{request.headers.get("host", "")}':
            return JSONResponse({'detail':'Untrusted request origin'}, status_code=403)
        if request.url.path != '/api/auth/login':
            try:
                verify_csrf(request)
            except HTTPException as exc:
                return JSONResponse({'detail':exc.detail}, status_code=exc.status_code)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), geolocation=()'
    response.headers['X-Permitted-Cross-Domain-Policies'] = 'none'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    elif request.url.path == '/' or request.url.path.startswith('/lite/'):
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' blob: data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return response


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str = Field(default='', max_length=6)

class PasswordChangeBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)

class MFASetupBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)

class MFAConfirmBody(BaseModel):
    code: str = Field(min_length=6, max_length=6)

class MFADisableBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=6, max_length=6)

class AnalyzeBody(BaseModel):
    title: str = Field(default='', max_length=200)
    description: str = Field(min_length=3, max_length=4000)
    district: str = 'Prayagraj'
    image_hint: str = Field(default='', max_length=240)

class CreateComplaintBody(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    description: str = Field(min_length=12, max_length=4000)
    district: str
    channel: Literal['web','voice','photo'] = 'web'
    attachment_path: str | None = None
    image_hint: str = Field(default='', max_length=240)

class PatchComplaintBody(BaseModel):
    status: Literal['new','in_progress','escalated','resolved'] | None = None
    priority: Literal['low','medium','high','critical'] | None = None
    department: str | None = None
    assigned_to: int | None = None

class NoteBody(BaseModel):
    body: str = Field(min_length=2, max_length=1500)
    is_public: bool = False


def complaint_obj(row) -> dict:
    data = dict(row)
    data['tags'] = json.loads(data.get('tags') or '[]')
    data['requires_human_review'] = data['priority'] == 'critical' or data['confidence'] < 0.58
    return data


def get_complaint(db, complaint_id: int, user: dict) -> dict:
    row = db.execute('SELECT c.*, u.name AS assigned_name FROM complaints c '
                     'LEFT JOIN users u ON u.id=c.assigned_to WHERE c.id=?', (complaint_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Complaint not found')
    if (user['role'] == 'citizen' and row['citizen_id'] != user['id']) or (
        user['role'] == 'officer' and row['department'] != user['department']
    ):
        raise HTTPException(404, 'Complaint not found')
    return complaint_obj(row)


def add_history(db, complaint_id: int, actor: int | None, action: str, details: str) -> None:
    db.execute('INSERT INTO history (complaint_id,actor_id,action,details,created_at) VALUES (?,?,?,?,?)',
               (complaint_id, actor, action, details, iso(datetime.now(timezone.utc))))


@app.get('/api/health')
def health():
    return {'status':'ok', 'service':'NagrikOS', 'mode':'offline-demo', 'ai':'mock-rules-v1'}


@app.get('/api/meta')
def meta():
    return {'districts':DISTRICTS,'departments':DEPARTMENTS,'categories':[
        {'name':cat['name'],'department':cat['department'],'sla_hours':cat['sla_hours']} for cat in CATEGORIES],
        'statuses':sorted(VALID_STATUSES),'priorities':['critical','high','medium','low'],
        'is_demo':True,'data_disclaimer':'Seeded records are synthetic. Routing/urgency/ETA outputs are illustrative.'}


_DUMMY_PASSWORD_HASH = hash_password('nagrikos-invalid-unknown-account')

@app.post('/api/auth/login')
def login(body: LoginBody, request: Request, response: Response):
    # Throttle by account and remote IP. Store hashes of identifiers, not raw emails/IPs.
    now = int(time.time())
    email = body.email.strip().casefold()[:254]
    address = request.client.host if request.client else 'unknown'
    keys = [hashlib.sha256(f'account:{email}'.encode()).hexdigest(),
            hashlib.sha256(f'ip:{address}'.encode()).hexdigest()]
    with connect() as db:
        db.execute('DELETE FROM login_attempts WHERE attempted_at < ?', (now - 900,))
        counts = [db.execute('SELECT COUNT(*) FROM login_attempts WHERE identifier=?',
                             (key,)).fetchone()[0] for key in keys]
        if max(counts) >= 8:
            raise HTTPException(429, 'Too many sign-in attempts. Try again after 15 minutes.')
        row = db.execute('SELECT * FROM users WHERE lower(email)=?', (email,)).fetchone()
        valid, rehash = verify_password(body.password, row['password_hash'], row['id']) if row else (False, False)
        if not row:
            # Execute one expensive dummy hash to reduce account-existence timing leakage.
            verify_password(body.password, _DUMMY_PASSWORD_HASH, 0)
        if valid and row['mfa_secret']:
            counter = totp_counter(decrypt_totp(row['mfa_secret']),body.mfa_code,now,row['mfa_last_counter'])
            if counter is None: valid=False
        else: counter=None
        if not valid:
            db.executemany('INSERT INTO login_attempts VALUES (?,?)', [(key, now) for key in keys])
            db.commit()  # Failed attempts must persist even when an HTTP error is raised.
            raise HTTPException(401, 'Incorrect email or password')
        # On successful login, clear this account's failures but retain IP failures.
        db.execute('DELETE FROM login_attempts WHERE identifier=?', (keys[0],))
        if counter is not None:
            db.execute('UPDATE users SET mfa_last_counter=? WHERE id=?', (counter,row['id']))
        if rehash:
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(body.password), row['id']))
        session = secrets.token_hex(32)
        csrf = secrets.token_hex(32)
        db.execute('DELETE FROM sessions WHERE expires_at<=?', (now,))
        db.execute('INSERT INTO sessions (token_hash,user_id,csrf_hash,expires_at,created_at,last_seen_at) VALUES (?,?,?,?,?,?)',
                   (token_hash(session), row['id'], token_hash(csrf), now + SESSION_SECONDS, now, now))
    apply_cookies(response, session, csrf)
    user = {k: row[k] for k in ('id','name','email','role','department','district')}
    return {'user':user,'session_expires_in':SESSION_SECONDS,'idle_timeout_seconds':SESSION_IDLE_SECONDS}


@app.post('/api/auth/logout')
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (token_hash(token),))
    remove_cookies(response)
    return {'ok':True}


@app.get('/api/auth/me')
def me(user: dict = Depends(current_user)):
    return user


@app.get('/api/auth/security')
def security_settings(user: dict = Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT mfa_secret,mfa_pending FROM users WHERE id=?', (user['id'],)).fetchone()
    return {'mfa_enabled': bool(row['mfa_secret']), 'mfa_pending': bool(row['mfa_pending']),
            'session_idle_minutes':SESSION_IDLE_SECONDS//60}


@app.post('/api/auth/password')
def change_password(body: PasswordChangeBody, response: Response, user: dict = Depends(current_user)):
    if body.new_password == body.current_password:
        raise HTTPException(422, 'New password must be different')
    if body.new_password.casefold() in ('password1234','password12345','demo123demo123'):
        raise HTTPException(422, 'Choose a less common password')
    with connect() as db:
        row = db.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()
        valid, _ = verify_password(body.current_password, row['password_hash'], user['id'])
        if not valid: raise HTTPException(403, 'Current password is incorrect')
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(body.new_password),user['id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
    remove_cookies(response)
    return {'ok': True, 'message':'Password changed. Sign in again on all devices.'}


@app.post('/api/auth/mfa/setup')
def setup_mfa(body: MFASetupBody, user: dict = Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT password_hash,mfa_secret FROM users WHERE id=?', (user['id'],)).fetchone()
        valid,_ = verify_password(body.current_password,row['password_hash'],user['id'])
        if not valid: raise HTTPException(403, 'Current password is incorrect')
        if row['mfa_secret']: raise HTTPException(409,'Two-step verification is already active')
        secret = generate_totp_secret()
        db.execute('UPDATE users SET mfa_pending=? WHERE id=?', (encrypt_totp(secret),user['id']))
    from urllib.parse import quote
    label=quote(f'NagrikOS:{user["email"]}')
    uri=f'otpauth://totp/{label}?secret={secret}&issuer=NagrikOS&algorithm=SHA1&digits=6&period=30'
    return {'secret':secret,'otpauth_uri':uri,'message':'Add the key to your authenticator, then confirm a code.'}


@app.post('/api/auth/mfa/enable')
def enable_mfa(body: MFAConfirmBody, request: Request, user: dict = Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT mfa_pending,mfa_secret FROM users WHERE id=?', (user['id'],)).fetchone()
        if row['mfa_secret'] or not row['mfa_pending']:
            raise HTTPException(409, 'Start setup before enabling two-step verification')
        counter=totp_counter(decrypt_totp(row['mfa_pending']),body.code)
        if counter is None: raise HTTPException(422,'Invalid authenticator code')
        db.execute('UPDATE users SET mfa_secret=mfa_pending,mfa_pending=NULL,mfa_last_counter=? WHERE id=?', (counter,user['id']))
        # Existing sessions issued before enrollment are revoked except the current session.
        # This prevents an attacker holding an older cookie from retaining access.
        db.execute('DELETE FROM sessions WHERE user_id=? AND token_hash!=?',
                   (user['id'],token_hash(request.cookies[SESSION_COOKIE])))
    return {'ok': True}


@app.post('/api/auth/mfa/disable')
def disable_mfa(body: MFADisableBody, response: Response, user: dict = Depends(current_user)):
    with connect() as db:
        row = db.execute('SELECT password_hash,mfa_secret,mfa_last_counter FROM users WHERE id=?', (user['id'],)).fetchone()
        valid,_ = verify_password(body.current_password,row['password_hash'],user['id'])
        if not valid: raise HTTPException(403,'Current password is incorrect')
        if not row['mfa_secret']: raise HTTPException(409,'Two-step verification is not enabled')
        counter=totp_counter(decrypt_totp(row['mfa_secret']),body.code,last=row['mfa_last_counter'])
        if counter is None: raise HTTPException(422,'Invalid authenticator code')
        db.execute('UPDATE users SET mfa_secret=NULL,mfa_pending=NULL,mfa_last_counter=-1 WHERE id=?', (user['id'],))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
    remove_cookies(response)
    return {'ok':True,'message':'Two-step verification disabled. Sign in again.'}


@app.post('/api/ai/analyze')
def preview(body: AnalyzeBody, user: dict = Depends(current_user)):
    if body.district not in DISTRICTS: raise HTTPException(422, 'Select a valid district')
    result = analyze(body.description, body.title, body.image_hint)
    with connect() as db:
        rows = db.execute('SELECT id,title,description,ticket_no FROM complaints '
                          "WHERE category=? AND district=? AND (? != 'citizen' OR citizen_id=?) "
                          "AND (? != 'officer' OR department=?) ORDER BY created_at DESC LIMIT 150",
                          (result['category'],body.district,user['role'],user['id'],user['role'],user['department'])).fetchall()
    similar = sorted((
        {'id':r['id'],'ticket_no':r['ticket_no'],'title':r['title'],
         'similarity':round(SequenceMatcher(None, body.description.casefold(), r['description'].casefold()).ratio(), 2)}
        for r in rows
    ), key=lambda r:r['similarity'], reverse=True)
    result['similar_cases'] = [s for s in similar[:3] if s['similarity'] >= .48]
    result['similar_count'] = len([s for s in similar if s['similarity'] >= .48])
    return result


@app.post('/api/attachments')
async def upload_attachment(file: UploadFile = File(...), user: dict = Depends(current_user)):
    if user['role']=='officer':
        raise HTTPException(403, 'Only citizens and administrators can attach photos to a new complaint')
    name = (file.filename or 'photo').split('/')[-1].split('\\')[-1][:150]
    ext = Path(name).suffix.lower()
    if ext not in {'.png','.jpg','.jpeg','.webp'}:
        raise HTTPException(400, 'Only PNG, JPG, or WEBP photos are supported')
    data = await file.read(5 * 1024 * 1024 + 1)
    if len(data) > 5 * 1024 * 1024: raise HTTPException(413, 'Photo must be smaller than 5 MB')
    valid = (data.startswith(b'\x89PNG\r\n\x1a\n') if ext == '.png' else
             (data.startswith(b'\xff\xd8\xff') if ext in ('.jpg','.jpeg') else
              data[:4] == b'RIFF' and data[8:12] == b'WEBP'))
    if not valid: raise HTTPException(400, 'File contents do not match the supported image format')
    # Prevent malformed images, decompression bombs, and mislabeled payloads.
    from PIL import Image, UnidentifiedImageError
    try:
        Image.MAX_IMAGE_PIXELS = 24_000_000
        with Image.open(io.BytesIO(data)) as im:
            if im.width * im.height > 24_000_000:
                raise HTTPException(413,'Photo dimensions are too large')
            im.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning, SyntaxError):
        raise HTTPException(400,'Invalid or oversized image contents')
    # Re-encode and remove EXIF/GPS and ancillary metadata rather than serving raw camera uploads.
    try:
        from PIL import ImageOps
        with Image.open(io.BytesIO(data)) as image:
            if image.width * image.height > 24_000_000:
                raise HTTPException(413,'Photo dimensions are too large')
            clean = ImageOps.exif_transpose(image)
            clean.load()
            if ext in ('.jpg','.jpeg') and clean.mode not in ('RGB','L'):
                clean=clean.convert('RGB')
            elif ext in ('.png','.webp') and clean.mode not in ('RGB','RGBA','L','LA','P'):
                clean=clean.convert('RGBA')
            output_buffer=io.BytesIO()
            clean.save(output_buffer,format={'png':'PNG','jpg':'JPEG','jpeg':'JPEG','webp':'WEBP'}[ext.lstrip('.')])
            data=output_buffer.getvalue()
        if len(data)>5*1024*1024: raise HTTPException(413,'Processed image exceeds 5 MB')
    except (OSError, ValueError, SyntaxError):
        raise HTTPException(400,'Could not safely process image')
    filename = f'{secrets.token_hex(12)}{ext}'
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix': UPLOAD_DIR.chmod(0o700)
    photo_path = UPLOAD_DIR / filename
    with open(photo_path, 'xb') as output:
        output.write(data)
    if os.name == 'posix':
        photo_path.chmod(0o600)
    try:
        with connect() as db:
            db.execute('INSERT INTO attachments VALUES (?,?,?,?,?)',
                       (filename, user['id'], None, name, iso(datetime.now(timezone.utc))))
    except Exception:
        photo_path.unlink(missing_ok=True)
        raise
    return {'path':filename,'url':f'/api/attachments/{filename}',
            'description':mock_image_description(name),'filename':name,'size':len(data)}


@app.get('/api/attachments/{filename}')
def fetch_attachment(filename: str, user: dict = Depends(current_user)):
    if not re.fullmatch(r'[a-f0-9]{24}\.(?:png|jpg|jpeg|webp)', filename):
        raise HTTPException(404, 'File not found')
    path = UPLOAD_DIR / filename
    if not path.is_file(): raise HTTPException(404, 'File not found')
    with connect() as db:
        row = db.execute('SELECT uploaded_by,complaint_id FROM attachments WHERE filename=?', (filename,)).fetchone()
        if not row:
            raise HTTPException(404, 'File not found')
        if row['complaint_id'] is not None:
            get_complaint(db, row['complaint_id'], user)  # Enforce ownership / department scope.
        elif row['uploaded_by'] != user['id']:
            raise HTTPException(404, 'File not found')
    media_type = {'png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp'}[filename.rsplit('.',1)[-1]]
    return FileResponse(path, media_type=media_type)



@app.post('/api/complaints', status_code=201)
def create_complaint(body: CreateComplaintBody, user: dict = Depends(current_user)):
    if user['role']=='officer':
        raise HTTPException(403, 'File new grievances using a citizen or administrator account')
    if body.district not in DISTRICTS: raise HTTPException(422, 'Select a valid district')
    if not body.title.strip() or len(body.title.strip()) < 5 or len(body.description.strip()) < 12:
        raise HTTPException(422,'Provide a meaningful title and description')
    if body.channel == 'photo' and not body.attachment_path:
        raise HTTPException(422,'Photo channel requires an attached photo')
    if body.attachment_path and not re.fullmatch(r'[a-f0-9]{24}\.(?:png|jpg|jpeg|webp)', body.attachment_path):
        raise HTTPException(422, 'Invalid photo reference')
    if body.attachment_path and not (UPLOAD_DIR / body.attachment_path).is_file():
        raise HTTPException(422, 'Uploaded photo not found')
    now = datetime.now(timezone.utc)
    citizen_id = user['id'] if user['role']=='citizen' else None
    with connect() as db:
        if body.attachment_path:
            upload_row = db.execute('SELECT uploaded_by,complaint_id,original_name FROM attachments WHERE filename=?',
                                    (body.attachment_path,)).fetchone()
            if not upload_row or upload_row['uploaded_by'] != user['id'] or upload_row['complaint_id'] is not None:
                raise HTTPException(422, 'Photo does not belong to this session or is already attached')
        # Only the stored server-side original name can act as a mock visual hint.
        stored_hint = upload_row['original_name'] if body.attachment_path else ''
        ai = analyze(body.description, body.title, stored_hint)
        cursor = db.execute('''INSERT INTO complaints (ticket_no,title,description,district,category,department,
            priority,urgency_score,confidence,estimated_hours,rationale,language,tags,status,channel,
            citizen_id,assigned_to,attachment_path,attachment_description,created_at,updated_at,due_at,resolved_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            None,body.title.strip(),body.description.strip(),body.district,ai['category'],ai['department'],
            ai['priority'],ai['urgency_score'],ai['confidence'],ai['estimated_hours'],ai['rationale'],
            ai['language'],json.dumps(ai['tags']),'new',body.channel,citizen_id,None,
            body.attachment_path, mock_image_description(stored_hint) if body.attachment_path else None,
            iso(now),iso(now),iso(now + timedelta(hours=ai['estimated_hours'])),None))
        case_id = cursor.lastrowid
        ticket_no = f'UP-{now.year}-{case_id:06d}'
        db.execute('UPDATE complaints SET ticket_no=? WHERE id=?',(ticket_no,case_id))
        if body.attachment_path:
            db.execute('UPDATE attachments SET complaint_id=? WHERE filename=?', (case_id,body.attachment_path))
        add_history(db,case_id,user['id'],'created','Complaint submitted and queued for human review.')
    with connect() as db:
        return get_complaint(db, case_id, user)


@app.get('/api/complaints')
def complaints(status: str | None = None, priority: str | None = None,
               district: str | None = None, department: str | None = None,
               search: str | None = None, assigned_to_me: bool = False,
               page: int = Query(1, ge=1), page_size: int = Query(12, ge=1, le=100),
               user: dict = Depends(current_user)):
    clauses, values = [], []
    if user['role']=='citizen': clauses.append('c.citizen_id=?'); values.append(user['id'])
    if user['role']=='officer': clauses.append('c.department=?'); values.append(user['department'])
    if status: clauses.append('c.status=?'); values.append(status)
    if priority: clauses.append('c.priority=?'); values.append(priority)
    if district: clauses.append('c.district=?'); values.append(district)
    if department: clauses.append('c.department=?'); values.append(department)
    if assigned_to_me: clauses.append('c.assigned_to=?'); values.append(user['id'])
    if search:
        clauses.append('(c.title LIKE ? OR c.description LIKE ? OR c.ticket_no LIKE ?)')
        values.extend([f'%{search[:100]}%']*3)
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    with connect() as db:
        total = db.execute('SELECT COUNT(*) AS n FROM complaints c'+where, values).fetchone()['n']
        rows = db.execute('SELECT c.*, u.name AS assigned_name FROM complaints c LEFT JOIN users u ON c.assigned_to=u.id'+where+
                          ' ORDER BY CASE c.priority WHEN "critical" THEN 0 WHEN "high" THEN 1 WHEN "medium" THEN 2 ELSE 3 END, c.created_at DESC LIMIT ? OFFSET ?',
                          [*values,page_size,(page-1)*page_size]).fetchall()
    return {'items':[complaint_obj(row) for row in rows], 'total':total,'page':page,
            'page_size':page_size,'pages':max(1,(total+page_size-1)//page_size)}


@app.get('/api/complaints/{complaint_id}')
def complaint_detail(complaint_id: int, user: dict = Depends(current_user)):
    with connect() as db:
        result = get_complaint(db,complaint_id,user)
        history_filter = "AND h.action IN ('created','status_changed')" if user['role']=='citizen' else ''
        result['history']=[dict(r) for r in db.execute(f'''SELECT h.*, u.name AS actor_name FROM history h
            LEFT JOIN users u ON u.id=h.actor_id WHERE h.complaint_id=? {history_filter}
            ORDER BY h.created_at DESC,h.id DESC''', (complaint_id,)).fetchall()]
        notes_filter = 'AND n.is_public=1' if user['role']=='citizen' else ''
        result['notes']=[dict(r) for r in db.execute(f'''SELECT n.*,u.name AS author_name FROM notes n
            LEFT JOIN users u ON u.id=n.author_id WHERE n.complaint_id=? {notes_filter}
            ORDER BY n.created_at DESC,n.id DESC''', (complaint_id,)).fetchall()]
    return result


@app.patch('/api/complaints/{complaint_id}')
def patch_complaint(complaint_id: int, body: PatchComplaintBody, user: dict=Depends(require_official)):
    fields = body.model_dump(exclude_unset=True)
    if not fields: raise HTTPException(400, 'No changes supplied')
    if any(k != 'assigned_to' and v is None for k,v in fields.items()):
        raise HTTPException(422, 'Only assigned_to can be cleared')
    if 'department' in fields and fields['department'] not in [d['name'] for d in DEPARTMENTS]:
        raise HTTPException(422, 'Invalid department')
    if 'status' in fields and fields['status']=='new':
        raise HTTPException(422, 'Use in progress, escalated, or resolved for case workflow')
    with connect() as db:
        existing = get_complaint(db,complaint_id,user)
        if user['role']=='officer' and 'department' in fields and fields['department'] != user['department']:
            raise HTTPException(403, 'Only administrators can route cases to another department')
        target_department = fields.get('department', existing['department'])
        if 'assigned_to' in fields and fields['assigned_to'] is not None:
            assignee = db.execute('SELECT role,department FROM users WHERE id=?',
                                  (fields['assigned_to'],)).fetchone()
            if not assignee or assignee['role'] != 'officer' or assignee['department'] != target_department:
                raise HTTPException(422, 'Assign to an officer in the selected department')
        elif 'department' in fields and existing['assigned_to'] is not None and fields['department'] != existing['department']:
            # Clear outdated ownership when administrators reroute a case.
            fields['assigned_to'] = None
        changes = {k:v for k,v in fields.items() if v != existing[k]}
        if not changes: return existing
        now = iso(datetime.now(timezone.utc))
        changes['updated_at'] = now
        if changes.get('status')=='resolved': changes['resolved_at']=now
        elif 'status' in changes and existing['status']=='resolved': changes['resolved_at']=None
        assignments=', '.join(f'{k}=?' for k in changes)
        db.execute(f'UPDATE complaints SET {assignments} WHERE id=?', [*changes.values(),complaint_id])
        for field,value in changes.items():
            if field not in ('updated_at','resolved_at'):
                add_history(db,complaint_id,user['id'],f'{field}_changed', f'{field.replace("_"," ").title()}: {existing.get(field)} → {value}')
    with connect() as db:
        return get_complaint(db,complaint_id,user)


@app.post('/api/complaints/{complaint_id}/notes', status_code=201)
def note_complaint(complaint_id: int, body: NoteBody, user: dict=Depends(require_official)):
    if len(body.body.strip()) < 2: raise HTTPException(422,'Note needs at least two non-space characters')
    with connect() as db:
        get_complaint(db,complaint_id,user)
        db.execute('INSERT INTO notes (complaint_id,author_id,body,is_public,created_at) VALUES (?,?,?,?,?)',
                   (complaint_id,user['id'],body.body.strip(),int(body.is_public),iso(datetime.now(timezone.utc))))
        add_history(db,complaint_id,user['id'],'note_added',
                    'Public update added.' if body.is_public else 'Internal case note added.')
    return {'ok':True}


@app.get('/api/users/officers')
def officers(user: dict = Depends(require_official)):
    with connect() as db:
        if user['role']=='admin':
            rows = db.execute("SELECT id,name,role,department FROM users WHERE role='officer' ORDER BY name").fetchall()
        else:
            rows = db.execute("SELECT id,name,role,department FROM users WHERE role='officer' AND department=? ORDER BY name",(user['department'],)).fetchall()
        return [dict(r) for r in rows]


def sql_stats(db, where: str = '', params: tuple | list = ()):
    return dict(db.execute(f'''SELECT COUNT(*) AS total,
      SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) AS new_count,
      SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) AS in_progress,
      SUM(CASE WHEN status='escalated' THEN 1 ELSE 0 END) AS escalated,
      SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved,
      SUM(CASE WHEN priority IN ('critical','high') AND status!='resolved' THEN 1 ELSE 0 END) AS urgent_open,
      SUM(CASE WHEN status!='resolved' AND due_at < ? THEN 1 ELSE 0 END) AS overdue,
      SUM(CASE WHEN resolved_at IS NOT NULL AND resolved_at <= due_at THEN 1 ELSE 0 END) AS resolved_within_target,
      ROUND(AVG(CASE WHEN resolved_at IS NOT NULL THEN (julianday(resolved_at)-julianday(created_at))*24 ELSE NULL END),1) AS avg_resolution_hours
      FROM complaints {where}''', [iso(datetime.now(timezone.utc)), *params]).fetchone())


@app.get('/api/citizen/overview')
def citizen_overview(user: dict = Depends(current_user)):
    if user['role'] != 'citizen': raise HTTPException(403,'Citizen access only')
    with connect() as db:
        counts=db.execute('''SELECT COUNT(*) AS total,
           SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved
           FROM complaints WHERE citizen_id=?''',(user['id'],)).fetchone()
        rows=db.execute('''SELECT c.*,u.name AS assigned_name FROM complaints c
           LEFT JOIN users u ON u.id=c.assigned_to WHERE c.citizen_id=?
           ORDER BY c.created_at DESC LIMIT 5''',(user['id'],)).fetchall()
    return {'total':counts['total'],'resolved':counts['resolved'] or 0,
            'active':counts['total']-(counts['resolved'] or 0),
            'recent':[complaint_obj(r) for r in rows]}


@app.get('/api/dashboard')
def dashboard(user: dict=Depends(require_admin)):
    with connect() as db:
        stats=sql_stats(db)
        total_resolved = stats['resolved'] or 0
        stats['resolution_rate'] = round(100*total_resolved/max(stats['total'],1),1)
        stats['on_time_rate'] = round(100*(stats['resolved_within_target'] or 0)/max(total_resolved,1),1)
        by_category=[dict(r) for r in db.execute('SELECT category AS name,COUNT(*) AS value FROM complaints GROUP BY category ORDER BY value DESC')]
        by_department=[dict(r) for r in db.execute('''SELECT department AS name,
          SUM(CASE WHEN status!='resolved' THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved,
          COUNT(*) AS total FROM complaints GROUP BY department ORDER BY open DESC''')]
        by_district=[dict(r) for r in db.execute('SELECT district AS name,COUNT(*) AS value FROM complaints GROUP BY district ORDER BY value DESC LIMIT 10')]
        monthly=[dict(r) for r in db.execute('''SELECT substr(created_at,1,7) AS month,COUNT(*) AS total,
          SUM(CASE WHEN priority IN ('critical','high') THEN 1 ELSE 0 END) AS urgent
          FROM complaints GROUP BY month ORDER BY month''')]
        recent=[complaint_obj(r) for r in db.execute('''SELECT c.*,u.name AS assigned_name FROM complaints c
          LEFT JOIN users u ON c.assigned_to=u.id WHERE c.status!='resolved'
          ORDER BY CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,c.created_at DESC LIMIT 6''')]
        activity=[dict(r) for r in db.execute('''SELECT h.*,c.ticket_no,c.title FROM history h JOIN complaints c ON c.id=h.complaint_id
          ORDER BY h.created_at DESC,h.id DESC LIMIT 8''')]
    return {'stats':stats,'by_category':by_category,'by_department':by_department,
            'by_district':by_district,'monthly':monthly,'attention':recent,'activity':activity}


@app.get('/api/officer/overview')
def officer_overview(user: dict=Depends(require_officer)):
    with connect() as db:
        dept = user['department']
        stats = sql_stats(db, 'WHERE department=?', (dept,))
        stats['resolution_rate'] = round(100*(stats['resolved'] or 0)/max(stats['total'],1), 1)
        mine = db.execute('''SELECT c.*,u.name AS assigned_name FROM complaints c
            LEFT JOIN users u ON u.id=c.assigned_to WHERE c.department=?
            AND c.assigned_to=? AND c.status!='resolved' ORDER BY c.created_at DESC LIMIT 6''',
            (dept,user['id'])).fetchall()
        queue = db.execute('''SELECT c.*,u.name AS assigned_name FROM complaints c
            LEFT JOIN users u ON u.id=c.assigned_to WHERE c.department=? AND c.status!='resolved'
            ORDER BY CASE c.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
            c.created_at DESC LIMIT 8''',(dept,)).fetchall()
        monthly = [dict(r) for r in db.execute('''SELECT substr(created_at,1,7) AS month,
            COUNT(*) AS total FROM complaints WHERE department=? GROUP BY month ORDER BY month''',(dept,))]
    return {'department':dept,'stats':stats,'my_cases':[complaint_obj(r) for r in mine],
            'queue':[complaint_obj(r) for r in queue],'monthly':monthly}


@app.get('/api/departments')
def departments(user: dict=Depends(require_admin)):
    with connect() as db:
        rows = db.execute('''SELECT department AS name,COUNT(*) AS total,
          SUM(CASE WHEN status!='resolved' THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN status='resolved' THEN 1 ELSE 0 END) AS resolved,
          SUM(CASE WHEN status='escalated' THEN 1 ELSE 0 END) AS escalated,
          SUM(CASE WHEN status!='resolved' AND due_at < ? THEN 1 ELSE 0 END) AS overdue,
          ROUND(AVG(CASE WHEN resolved_at IS NOT NULL THEN (julianday(resolved_at)-julianday(created_at))*24 END),1) AS avg_resolution_hours
          FROM complaints GROUP BY department ORDER BY open DESC''', (iso(datetime.now(timezone.utc)),)).fetchall()
    return [{**dict(row),'short':next((d['short'] for d in DEPARTMENTS if d['name']==row['name']), 'GEN'),
             'resolution_rate':round(100*(row['resolved'] or 0)/max(row['total'],1),1)} for row in rows]


@app.get('/api/insights')
def insights(user: dict=Depends(require_admin)):
    with connect() as db:
        clusters=[dict(r) for r in db.execute('''SELECT category,district,department,
          COUNT(*) AS count,
          SUM(CASE WHEN status!='resolved' THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN priority IN ('high','critical') THEN 1 ELSE 0 END) AS urgent
          FROM complaints GROUP BY category,district HAVING COUNT(*)>=3 ORDER BY count DESC,urgent DESC LIMIT 12''')]
        trends=[dict(r) for r in db.execute('''SELECT category,substr(created_at,1,7) AS month,COUNT(*) AS count
          FROM complaints GROUP BY category,month ORDER BY month,category''')]
        district_risk=[dict(r) for r in db.execute('''SELECT district AS name,
          SUM(CASE WHEN status!='resolved' THEN 1 ELSE 0 END) AS open,
          SUM(CASE WHEN status='escalated' THEN 1 ELSE 0 END) AS escalated,
          COUNT(*) AS total FROM complaints GROUP BY district ORDER BY open DESC LIMIT 10''')]
    return {'clusters':clusters,'category_trends':trends,'district_risk':district_risk,
            'disclaimer':'Clusters reflect repeated category+district groupings, not semantic duplicates. All rows are synthetic.'}


@app.get('/api/export/complaints.csv')
def export_complaints(user: dict=Depends(require_admin)):
    fields=['ticket_no','title','description','district','category','department','priority','status',
            'channel','created_at','updated_at','due_at','resolved_at','confidence','estimated_hours']
    with connect() as db:
        rows=db.execute(f'SELECT {",".join(fields)} FROM complaints ORDER BY created_at DESC').fetchall()
    output=io.StringIO()
    writer=csv.writer(output)
    writer.writerow(fields)
    for row in rows:
        # Spreadsheet formula injection can hide behind leading whitespace/control characters.
        def safe_cell(value):
            if not isinstance(value,str): return value
            return "'" + value if value.lstrip(' \t\r\n').startswith(('=','+','-','@')) else value
        writer.writerow([safe_cell(row[f]) for f in fields])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="nagrikos_demo_cases.csv"'})


@app.post('/api/admin/reset-demo')
def reset(user: dict=Depends(require_admin)):
    reset_demo()
    for old_photo in UPLOAD_DIR.glob('*'):
        if old_photo.is_file() and re.fullmatch(r'[a-f0-9]{24}\.(?:png|jpg|jpeg|webp)',old_photo.name):
            old_photo.unlink(missing_ok=True)
    return {'ok':True,'message':'All changes cleared; 520 synthetic complaints restored.'}


# Dependency-free browser fallback (React is served separately by Vite on :5173).
LITE_DIR = Path(__file__).resolve().parent.parent / 'static'


@app.get('/', include_in_schema=False)
def lite_home():
    return FileResponse(LITE_DIR / 'index.html', media_type='text/html')


@app.get('/lite/{filename}', include_in_schema=False)
def lite_asset(filename: str):
    if filename not in ('app.js', 'style.css'):
        raise HTTPException(404, 'Asset not found')
    return FileResponse(LITE_DIR / filename)
