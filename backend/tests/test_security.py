"""Privacy, CSRF, session, role and upload regression tests for v2."""
import base64
import os
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import connect, iso
from app.auth import hash_password, token_hash
from datetime import datetime, timezone

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path/'private'/'db.sqlite3'))
    monkeypatch.setattr('app.main.UPLOAD_DIR', tmp_path/'private'/'uploads')
    monkeypatch.setenv('MAILJET_API_KEY', 'test-only-key')
    monkeypatch.setenv('MAILJET_SECRET_KEY', 'test-only-secret')
    monkeypatch.setenv('MAIL_FROM', 'security@example.org')
    monkeypatch.setattr('app.account.send_mail', lambda *_args: None)
    with TestClient(app) as c:
        yield c

def login(c, email='admin@demo.in', password='demo123'):
    r = c.post('/api/auth/login', json={'email':email,'password':password})
    assert r.status_code == 200, r.text
    csrf = r.cookies['nagrikos_csrf']
    cookie = f'nagrikos_session={r.cookies["nagrikos_session"]}; nagrikos_csrf={csrf}'
    return {'Cookie':cookie,'X-CSRF-Token':csrf}

def test_opaque_session_http_only_expiry_and_csrf(client):
    admin = login(client)
    assert 'access_token' not in client.get('/api/auth/me',headers=admin).json()
    cookies = client.post('/api/auth/login',json={'email':'citizen@demo.in','password':'demo123'})
    assert 'httponly' in cookies.headers['set-cookie'].lower()
    assert 'samesite=strict' in cookies.headers['set-cookie'].lower()
    assert client.get('/api/dashboard',headers=admin).status_code == 200
    without_csrf = {'Cookie':admin['Cookie']}
    assert client.post('/api/admin/reset-demo',headers=without_csrf,json={}).status_code == 403
    forged = dict(admin, **{'X-CSRF-Token':'fake-csrf'})
    assert client.post('/api/admin/reset-demo',headers=forged,json={}).status_code == 403
    assert client.get('/api/dashboard',headers={'Authorization':'Bearer pretend', 'Cookie':''}).status_code == 401
    assert client.post('/api/auth/logout',headers=admin,json={}).status_code == 200
    assert client.get('/api/dashboard',headers=admin).status_code == 401

def test_expired_session_and_login_throttling(client):
    admin=login(client)
    assert client.post('/api/auth/forgot-password',headers={'Cookie':admin['Cookie']},
                       json={'email':'admin@demo.in'}).status_code==403
    token=admin['Cookie'].split(';')[0].split('=',1)[1]
    with connect() as db:
        db.execute('UPDATE sessions SET expires_at=? WHERE token_hash=?', (int(time.time())-1,token_hash(token)))
    assert client.get('/api/auth/me',headers=admin).status_code==401
    assert client.post('/api/auth/forgot-password',headers={'Cookie':admin['Cookie']},
                       json={'email':'admin@demo.in'}).status_code==202
    assert client.post('/api/admin/reset-demo',headers={'Cookie':admin['Cookie']},json={}).status_code==401
    for i in range(8):
        assert client.post('/api/auth/login',json={'email':'unknown@demo.in','password':'bad'}).status_code==401
    assert client.post('/api/auth/login',json={'email':'unknown@demo.in','password':'bad'}).status_code==429
    assert client.post('/api/auth/login',json={'email':'admin@demo.in','password':'demo123'}).status_code==429

def test_role_isolation_on_reads_and_mutations(client):
    admin=login(client,'admin@demo.in')
    officer=login(client,'officer@demo.in')
    citizen=login(client,'citizen@demo.in')
    assert client.get('/api/dashboard',headers=officer).status_code==403
    assert client.get('/api/insights',headers=officer).status_code==403
    assert client.get('/api/departments',headers=officer).status_code==403
    assert client.get('/api/export/complaints.csv',headers=officer).status_code==403
    assert client.get('/api/officer/overview',headers=citizen).status_code==403
    assert client.get('/api/officer/overview',headers=admin).status_code==403
    desk=client.get('/api/officer/overview',headers=officer)
    assert desk.status_code==200 and desk.json()['department']=='Public Works Department'
    assert all(c['department']=='Public Works Department' for c in desk.json()['queue'])
    items=client.get('/api/complaints?page_size=100',headers=officer).json()['items']
    assert items and all(c['department']=='Public Works Department' for c in items)
    other=client.get('/api/complaints?page_size=100',headers=admin).json()['items']
    elsewhere=next(c for c in other if c['department']!='Public Works Department')
    assert client.get(f"/api/complaints/{elsewhere['id']}",headers=officer).status_code==404
    assert client.patch(f"/api/complaints/{elsewhere['id']}",headers=officer,json={'status':'resolved'}).status_code==404
    own=items[0]
    assert client.patch(f"/api/complaints/{own['id']}",headers=officer,json={
        'department':'Water Supply & Sanitation'}).status_code==403
    assert client.patch(f"/api/complaints/{own['id']}",headers=officer,json={
        'assigned_to':3}).status_code==422
    assert client.patch(f"/api/complaints/{own['id']}",headers=officer,json={
        'priority':'high'}).status_code==200
    assert client.post('/api/complaints',headers=officer,json={
        'title':'A new complaint', 'description':'Water stopped for three days',
        'district':'Lucknow'}).status_code==403

def test_admin_department_transfer_clears_old_assignment(client):
    admin=login(client)
    officer=login(client,'officer@demo.in')
    own=client.get('/api/complaints?page_size=100',headers=officer).json()['items'][0]
    client.patch(f"/api/complaints/{own['id']}",headers=admin,json={'assigned_to':2})
    moved=client.patch(f"/api/complaints/{own['id']}",headers=admin,json={'department':'Water Supply & Sanitation'})
    assert moved.status_code==200, moved.text
    assert moved.json()['assigned_to'] is None
    assert client.get(f"/api/complaints/{own['id']}",headers=officer).status_code==404

def test_photo_owner_access_and_one_use_reference(client):
    admin=login(client)
    citizen=login(client,'citizen@demo.in')
    with connect() as db:
        db.execute('INSERT INTO users (id,name,email,email_canonical,email_verified_at,password_hash,role,department,district,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (6,'Other Citizen','other@demo.in','other@demo.in',int(time.time()),hash_password('demo123'),'citizen',None,'Lucknow',iso(datetime.now(timezone.utc))))
    other=login(client,'other@demo.in')
    upload=client.post('/api/attachments',headers=citizen,files={'file':('street.png',PNG,'image/png')})
    assert upload.status_code==200,upload.text
    body=upload.json()
    assert client.get(body['url'],headers=citizen).status_code==200
    assert client.get(body['url'],headers=other).status_code==404
    assert client.get(body['url'],headers=admin).status_code==404  # Unattached uploads are uploader-private.
    complaint={'title':'Broken street sewer pipe','description':'The road is flooding near homes for several days.',
               'district':'Prayagraj','channel':'photo','attachment_path':body['path']}
    assert client.post('/api/complaints',headers=other,json=complaint).status_code==422
    created=client.post('/api/complaints',headers=citizen,json=complaint)
    assert created.status_code==201,created.text
    assert client.get(body['url'],headers=admin).status_code==200
    assert client.get(body['url'],headers=other).status_code==404
    assert client.post('/api/complaints',headers=citizen,json=complaint).status_code==422
    assert not client.get(body['url'],headers=citizen).headers['content-type'].startswith('text/html')

def test_reset_revokes_sessions_and_photo_bytes(client):
    admin=login(client)
    citizen=login(client,'citizen@demo.in')
    photo=client.post('/api/attachments',headers=citizen,files={'file':('street.png',PNG,'image/png')}).json()
    assert client.post('/api/admin/reset-demo',headers=admin,json={}).status_code==200
    assert client.get('/api/auth/me',headers=admin).status_code==401
    assert client.get('/api/auth/me',headers=citizen).status_code==401
    assert client.get(photo['url'],headers=citizen).status_code==401
    assert not (Path(os.environ['DATABASE_PATH']).parent/'uploads'/photo['path']).exists()

def test_request_origin_and_validation(client):
    admin=login(client)
    assert client.post('/api/admin/reset-demo',headers={**admin,'Origin':'https://untrusted.example'},json={}).status_code==403
    assert client.post('/api/auth/login',headers={'Origin':'https://untrusted.example'},
                       json={'email':'admin@demo.in','password':'demo123'}).status_code==403
    assert client.post('/api/auth/login',json={'email':'admin@demo.in','password':'x'*2000}).status_code==422
    assert client.get('/api/export/complaints.csv',headers=admin).headers['cache-control']=='no-store'
    assert client.get('/api/meta').headers['x-content-type-options']=='nosniff'


def test_existing_v1_account_hash_upgrades_at_login(client):
    import hashlib
    legacy = hashlib.pbkdf2_hmac('sha256', b'demo123', b'nagrikos-1', 180_000).hex()
    with connect() as db:
        db.execute('UPDATE users SET password_hash=? WHERE id=1', (legacy,))
    login(client)
    with connect() as db:
        updated = db.execute('SELECT password_hash FROM users WHERE id=1').fetchone()['password_hash']
    assert updated.startswith('$argon2id$')
    assert updated != legacy


def test_server_owned_photo_hint_cannot_be_spoofed(client):
    citizen=login(client,'citizen@demo.in')
    photo=client.post('/api/attachments',headers=citizen,files={'file':('road_pothole.png',PNG,'image/png')}).json()
    created=client.post('/api/complaints',headers=citizen,json={
        'title':'Damage at public facility',
        'description':'There is a problem near our public site that must be inspected.',
        'district':'Prayagraj','attachment_path':photo['path'],'channel':'photo',
        'image_hint':'anganwadi_building_photo.png'
    })
    assert created.status_code==201
    result=created.json()
    # The saved hint must reflect the validated upload name, not forged client text.
    assert 'road, pothole' in result['attachment_description']
    assert 'anganwadi_building_photo.png' not in result['attachment_description']
