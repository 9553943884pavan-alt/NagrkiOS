"""Verified account lifecycle and mail transport. No secrets are returned by public routes."""
from __future__ import annotations

import binascii
import hashlib
import os
import re
import secrets
import smtplib
import ssl
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from urllib.parse import quote
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .auth import hash_password, remove_cookies, require_admin, token_hash, verify_password
from .db import connect

router = APIRouter(prefix='/api/auth')

COMMON = {'password', 'password123', 'password1234', 'password12345', 'qwerty123456789',
          '123456789012345', '1234567890123456', 'letmein123456789', 'admin1234567890',
          'iloveyou12345678', 'demo123demo123', 'correcthorsebatterystaple'}


def mode() -> str:
    return os.getenv('NAGRIKOS_MODE', '')


def mail_ready() -> bool:
    return mode() == 'demo' or bool(os.getenv('SMTP_HOST','').strip() and os.getenv('MAIL_FROM','').strip())


def validate_config() -> None:
    if mode() not in {'demo', 'public'}:
        raise RuntimeError('Set NAGRIKOS_MODE=demo or public explicitly')
    if mode() == 'public':
        if os.getenv('COOKIE_SECURE', '').lower() != 'true':
            raise RuntimeError('Public mode requires COOKIE_SECURE=true and HTTPS')
        if not os.getenv('NAGRIKOS_TOTP_KEY'):
            raise RuntimeError('Public mode requires a persistent NAGRIKOS_TOTP_KEY')
        from cryptography.fernet import Fernet
        try:
            Fernet(os.environ['NAGRIKOS_TOTP_KEY'].encode('ascii'))
        except (ValueError, TypeError, binascii.Error):
            raise RuntimeError('NAGRIKOS_TOTP_KEY must be a valid Fernet key')
        if not mail_ready():
            raise RuntimeError('Public mode requires SMTP_HOST and MAIL_FROM')
        try:
            canonical(os.environ['MAIL_FROM'])
        except HTTPException:
            raise RuntimeError('MAIL_FROM must be a plain email address')
        base=urlsplit(os.getenv('PUBLIC_BASE_URL',''))
        if base.scheme != 'https' or not base.hostname or base.hostname in {'localhost','127.0.0.1'} or base.username or base.password or base.query or base.fragment:
            raise RuntimeError('Public mode requires HTTPS PUBLIC_BASE_URL')
        if os.getenv('SMTP_USER') and not os.getenv('SMTP_PASSWORD'):
            raise RuntimeError('SMTP_PASSWORD is required when SMTP_USER is set')
        try:
            port=int(os.getenv('SMTP_PORT','587'))
        except ValueError:
            raise RuntimeError('SMTP_PORT must be a valid port')
        if port<1 or port>65535:
            raise RuntimeError('SMTP_PORT must be a valid port')
        origins = [x.strip() for x in os.getenv('CORS_ORIGINS', '').split(',') if x.strip()]
        if any(urlsplit(x).scheme != 'https' or not urlsplit(x).hostname or '*' in x or
               urlsplit(x).hostname in {'localhost','127.0.0.1'} or urlsplit(x).path or
               urlsplit(x).query or urlsplit(x).fragment or urlsplit(x).username for x in origins):
            raise RuntimeError('Public CORS origins must use HTTPS')


def canonical(email: str) -> str:
    result = email.strip().casefold()
    if len(result) > 254 or result.count('@') != 1:
        raise HTTPException(422, 'Enter a valid email address')
    local, domain = result.split('@')
    labels = domain.split('.')
    if (not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}",local) or
        local.startswith('.') or local.endswith('.') or '..' in local or
        len(labels)<2 or len(domain)>253 or
        any(not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in labels)):
        raise HTTPException(422, 'Enter a valid email address')
    return result


def password_policy(password: str) -> None:
    if len(password) < 15 or len(password) > 1024:
        raise HTTPException(422, 'Use a password of 15 to 1024 characters')
    if password.casefold().strip() in COMMON:
        raise HTTPException(422, 'Choose a less common password')
    if mode() == 'public':
        digest = hashlib.sha1(password.encode()).hexdigest().upper()
        req = urllib.request.Request('https://api.pwnedpasswords.com/range/' + digest[:5],
                                     headers={'Add-Padding':'true', 'User-Agent':'NagrikOS-password-check'})
        try:
            with urllib.request.urlopen(req, timeout=4) as result:
                response = result.read(1_000_001)
                if len(response)>1_000_000:
                    raise ValueError('Password check response too large')
                lines = response.decode('ascii').splitlines()
        except (OSError, UnicodeError, ValueError, urllib.error.URLError):
            raise HTTPException(503, 'Password safety check is temporarily unavailable')
        if any(line.split(':', 1)[0] == digest[5:] and int(line.split(':', 1)[1]) > 0 for line in lines if ':' in line):
            raise HTTPException(422, 'This password has appeared in a data breach. Choose another.')


def throttle(db, request: Request, purpose: str, email: str, limit: int = 5, window: int = 3600) -> bool:
    now = int(time.time())
    address = request.client.host if request.client else 'unknown'
    keys = [token_hash(f'{purpose}:email:{email}'), token_hash(f'{purpose}:ip:{address}')]
    db.execute('DELETE FROM login_attempts WHERE attempted_at<?', (now-3600,))
    limited = any(db.execute('SELECT COUNT(*) FROM login_attempts WHERE identifier=? AND attempted_at>=?',
                             (key, now-window)).fetchone()[0] >= limit for key in keys)
    if not limited:
        db.executemany('INSERT INTO login_attempts(identifier,attempted_at) VALUES (?,?)', [(key, now) for key in keys])
    return limited


def send_mail(db, recipient: str, subject: str, body: str) -> None:
    if mode() == 'demo':
        db.execute('INSERT INTO mail_outbox(recipient,subject,body,created_at) VALUES (?,?,?,?)',
                   (recipient, subject, body, int(time.time())))
        return
    message = EmailMessage()
    message['From'] = os.environ['MAIL_FROM']
    message['To'] = recipient
    message['Subject'] = subject
    message.set_content(body)
    host = os.environ['SMTP_HOST']
    port = int(os.getenv('SMTP_PORT', '587'))
    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            if os.getenv('SMTP_USER'):
                smtp.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(503, 'Email delivery is unavailable. Try again later.') from exc


def issue_token(db, user_id: int, purpose: str, ttl: int = 1800) -> str:
    now = int(time.time())
    db.execute('DELETE FROM account_tokens WHERE user_id=? AND purpose=?', (user_id, purpose))
    token = secrets.token_urlsafe(32)
    db.execute('INSERT INTO account_tokens(token_hash,user_id,purpose,expires_at,created_at) VALUES (?,?,?,?,?)',
               (token_hash(token), user_id, purpose, now+ttl, now))
    return token


def consume_token(db, token: str, purpose: str):
    if len(token) > 200:
        raise HTTPException(400, 'Link is invalid or expired')
    row = db.execute('SELECT * FROM account_tokens WHERE token_hash=? AND purpose=?',
                     (token_hash(token), purpose)).fetchone()
    now = int(time.time())
    if not row or row['used_at'] or row['expires_at'] <= now or row['attempts'] >= 5:
        raise HTTPException(400, 'Link is invalid or expired')
    db.execute('UPDATE account_tokens SET attempts=attempts+1 WHERE token_hash=?', (row['token_hash'],))
    return row


class Signup(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=1024)


class EmailBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class TokenBody(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class ResetBody(TokenBody):
    new_password: str = Field(min_length=1, max_length=1024)


@router.get('/config')
def config(request: Request):
    local_demo = mode() == 'demo' and request.client and request.client.host in {'127.0.0.1','::1','testclient'}
    result = {'demo_enabled': bool(local_demo), 'registration_available': mail_ready(),
              'recovery_available': mail_ready()}
    if local_demo:
        result['demo_password'] = 'demo123'
    return result


@router.post('/signup', status_code=202)
def signup(body: Signup, request: Request):
    if not mail_ready():
        raise HTTPException(503, 'Registration is unavailable because email delivery is not configured')
    email = canonical(body.email)
    name = body.name.strip()
    if len(name) < 2:
        raise HTTPException(422, 'Enter your name')
    with connect() as db:
        if throttle(db, request, 'signup', email):
            return {'message': 'If this address can be registered, check your email for a verification link.'}
        db.commit()
        password_policy(body.password)
        row = db.execute('SELECT id,email_verified_at FROM users WHERE email_canonical=?', (email,)).fetchone()
        if row and row['email_verified_at']:
            hash_password(body.password)  # Similar work for existing and new addresses.
            return {'message': 'If this address can be registered, check your email for a verification link.'}
        if row:
            user_id = row['id']
            db.execute('UPDATE users SET name=?,password_hash=? WHERE id=?', (name, hash_password(body.password), user_id))
        else:
            user_id=db.execute('INSERT INTO users(name,email,email_canonical,password_hash,role,department,district,created_at,is_demo) '
                               'VALUES (?,?,?,?,?,?,?,?,?) RETURNING id',
                               (name,email,email,hash_password(body.password),'citizen',None,None,
                                time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),int(mode()=='demo'))).fetchone()[0]
        token = issue_token(db, user_id, 'verify', 1800)
        link = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/') + '/#verify=' + quote(token)
        send_mail(db, email, 'Verify your NagrikOS email', 'Open this link within 30 minutes to verify your email:\n' + link)
    return {'message': 'If this address can be registered, check your email for a verification link.'}


@router.post('/verify-email')
def verify_email(body: TokenBody, request: Request):
    with connect() as db:
        limited=throttle(db,request,'verify-token',token_hash(body.token),10,900)
        db.commit()
        if limited:
            raise HTTPException(429,'Too many attempts. Try again later.')
        row = consume_token(db, body.token, 'verify')
        db.execute('UPDATE users SET email_verified_at=? WHERE id=?', (int(time.time()), row['user_id']))
        db.execute('UPDATE account_tokens SET used_at=? WHERE user_id=? AND purpose=?',
                   (int(time.time()), row['user_id'], 'verify'))
    return {'message': 'Email verified. You can sign in.'}


@router.post('/forgot-password', status_code=202)
def forgot_password(body: EmailBody, request: Request):
    if not mail_ready():
        raise HTTPException(503, 'Recovery is unavailable because email delivery is not configured')
    email = canonical(body.email)
    with connect() as db:
        limited=throttle(db, request, 'forgot', email)
        db.commit()
        if not limited:
            row = db.execute('SELECT id FROM users WHERE email_canonical=? AND email_verified_at IS NOT NULL '
                             'AND (?="demo" OR is_demo=0)', (email,mode())).fetchone()
            if row:
                token = issue_token(db, row['id'], 'reset', 1800)
                link = os.getenv('PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/') + '/#reset=' + quote(token)
                send_mail(db,email,'Reset your NagrikOS password',
                          'Open this link within 30 minutes to reset your password:\n' + link)
    return {'message': 'If an account exists, a password reset link has been sent.'}


@router.post('/reset-password')
def reset_password(body: ResetBody, request: Request, response: Response):
    with connect() as db:
        limited=throttle(db,request,'reset-token',token_hash(body.token),10,900)
        db.commit()
        if limited:
            raise HTTPException(429,'Too many attempts. Try again later.')
        password_policy(body.new_password)
        row = consume_token(db, body.token, 'reset')
        user = db.execute('SELECT email,password_hash FROM users WHERE id=?', (row['user_id'],)).fetchone()
        if verify_password(body.new_password, user['password_hash'], row['user_id'])[0]:
            raise HTTPException(422, 'Choose a different password')
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_password(body.new_password),row['user_id']))
        db.execute('DELETE FROM sessions WHERE user_id=?', (row['user_id'],))
        db.execute('DELETE FROM auth_challenges WHERE user_id=?', (row['user_id'],))
        db.execute('DELETE FROM account_tokens WHERE user_id=?', (row['user_id'],))
        send_mail(db, user['email'], 'Your NagrikOS password was changed',
                  'Your password was reset. If this was not you, contact the service operator immediately.')
    remove_cookies(response)
    return {'message':'Password changed. Sign in again on all devices.'}


@router.get('/dev-mailbox')
def dev_mailbox(request: Request):
    if mode() != 'demo' or not request.client or request.client.host not in {'127.0.0.1','::1','testclient'}:
        raise HTTPException(404, 'Not found')
    with connect() as db:
        return {'messages':[dict(r) for r in db.execute('SELECT * FROM mail_outbox ORDER BY id DESC LIMIT 20')]}


class StaffInvite(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    role: str
    department: str | None = None
    district: str | None = None
    current_password: str


@router.post('/staff-invitations', status_code=202)
def invite_staff(body: StaffInvite, request: Request, admin: dict = Depends(require_admin)):
    from .data import DEPARTMENTS, DISTRICTS
    if body.role not in {'officer','admin'}:
        raise HTTPException(422, 'Invalid staff role')
    if body.role == 'officer' and body.department not in {d['name'] for d in DEPARTMENTS}:
        raise HTTPException(422, 'Select an existing department')
    if body.district and body.district not in DISTRICTS:
        raise HTTPException(422, 'Select an existing district')
    email = canonical(body.email)
    with connect() as db:
        if throttle(db,request,'staff-invite',email,20,3600):
            db.commit()
            raise HTTPException(429,'Too many invitations. Try again later.')
        db.commit()
        attempt_key=token_hash(f'staff-invite-password:{admin["id"]}')
        if db.execute('SELECT COUNT(*) FROM login_attempts WHERE identifier=? AND attempted_at>=?',
                      (attempt_key,int(time.time())-900)).fetchone()[0]>=5:
            raise HTTPException(429,'Too many attempts. Try again later.')
        me = db.execute('SELECT password_hash FROM users WHERE id=?', (admin['id'],)).fetchone()
        if not verify_password(body.current_password,me['password_hash'],admin['id'])[0]:
            db.execute('INSERT INTO login_attempts(identifier,attempted_at) VALUES (?,?)',(attempt_key,int(time.time())))
            db.commit()
            raise HTTPException(403, 'Current password is incorrect')
        db.execute('DELETE FROM login_attempts WHERE identifier=?',(attempt_key,))
        if db.execute('SELECT 1 FROM users WHERE email_canonical=?', (email,)).fetchone():
            raise HTTPException(409, 'Account already exists')
        token = secrets.token_urlsafe(32)
        db.execute('INSERT INTO staff_invitations VALUES (?,?,?,?,?,?,?,?,?)',
                   (token_hash(token), email, body.name.strip(), body.role, body.department, body.district,
                    int(time.time())+86400,None,admin['id']))
        link = os.getenv('PUBLIC_BASE_URL','http://127.0.0.1:8000').rstrip('/') + '/#invite=' + quote(token)
        send_mail(db,email,'NagrikOS staff invitation','Open this link within 24 hours to set your password:\n'+link)
    return {'message':'Invitation sent.'}


class AcceptInvite(TokenBody):
    password: str = Field(min_length=1, max_length=1024)


@router.post('/accept-invitation')
def accept_invitation(body: AcceptInvite, request: Request):
    with connect() as db:
        limited=throttle(db,request,'accept-invite',token_hash(body.token),10,900)
        db.commit()
        if limited:
            raise HTTPException(429,'Too many attempts. Try again later.')
        password_policy(body.password)
        row = db.execute('SELECT * FROM staff_invitations WHERE token_hash=?', (token_hash(body.token),)).fetchone()
        if not row or row['used_at'] or row['expires_at'] <= int(time.time()):
            raise HTTPException(400, 'Invitation is invalid or expired')
        if db.execute('SELECT 1 FROM users WHERE email_canonical=?', (row['email'],)).fetchone():
            raise HTTPException(409, 'Account already exists')
        db.execute('INSERT INTO users(name,email,email_canonical,password_hash,role,department,district,created_at,email_verified_at,is_demo) '
                   'VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (row['name'],row['email'],row['email'],hash_password(body.password),row['role'],row['department'],
                    row['district'],time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),int(time.time()),int(mode()=='demo')))
        db.execute('UPDATE staff_invitations SET used_at=? WHERE token_hash=?', (int(time.time()),row['token_hash']))
    return {'message':'Account ready. Sign in.'}
