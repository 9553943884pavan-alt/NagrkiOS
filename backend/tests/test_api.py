"""API contract and role-based workflow tests. No network and no ML downloads."""
import base64
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH',str(tmp_path/'test.sqlite3'))
    with TestClient(app) as client:
        yield client


def auth(client, role='admin'):
    emails={'admin':'admin@demo.in','officer':'officer@demo.in','citizen':'citizen@demo.in'}
    response=client.post('/api/auth/login',json={'email':emails[role],'password':'demo123'})
    assert response.status_code==200, response.text
    csrf = response.cookies['nagrikos_csrf']
    session = response.cookies['nagrikos_session']
    return {'Cookie': f'nagrikos_session={session}; nagrikos_csrf={csrf}', 'X-CSRF-Token': csrf}


def test_health_meta_and_demo_seed(client):
    assert client.get('/api/health').json()['status']=='ok'
    meta=client.get('/api/meta').json()
    assert len(meta['districts'])==75
    assert len(meta['departments'])==11
    dashboard=client.get('/api/dashboard',headers=auth(client)).json()
    assert dashboard['stats']['total']==520
    assert dashboard['monthly']
    assert dashboard['by_department']
    assert dashboard['by_district']


def test_auth_and_permissions(client):
    assert client.get('/api/dashboard').status_code==401
    assert client.post('/api/auth/login',json={'email':'admin@demo.in','password':'wrong'}).status_code==401
    citizen=auth(client,'citizen')
    assert client.get('/api/dashboard',headers=citizen).status_code==403
    assert client.get('/api/departments',headers=citizen).status_code==403
    assert client.get('/api/insights',headers=citizen).status_code==403
    assert client.get('/api/export/complaints.csv',headers=citizen).status_code==403
    assert client.post('/api/admin/reset-demo',json={},headers=auth(client,'officer')).status_code==403


def test_routing_hindi_and_critical_safety(client):
    admin=auth(client)
    sample=client.post('/api/ai/analyze',headers=admin,json={
        'title':'अंगनवाड़ी भवन अधूरा है',
        'description':'हमारे गांव में आंगनवाड़ी भवन का निर्माण अधूरा है और बच्चों को परेशानी है।',
        'district':'Prayagraj'})
    assert sample.status_code==200
    assert sample.json()['category']=='Women & Child Services'
    wire=client.post('/api/ai/analyze',headers=admin,json={
        'title':'Electric wire danger','description':'Exposed live wire caused an electrocution in the street.',
        'district':'Lucknow'}).json()
    assert wire['priority']=='critical'
    assert wire['requires_human_review']
    assert wire['model_version']=='mock-rules-v1'
    assert client.post('/api/ai/analyze',headers=admin,json={'title':'x','description':'water issue','district':'Atlantis'}).status_code==422


def test_citizen_create_officer_update_and_public_note(client):
    citizen=auth(client,'citizen')
    officer=auth(client,'officer')
    created=client.post('/api/complaints',headers=citizen,json={
        'title':'Water pipeline damaged outside home',
        'description':'Water pipeline damaged and no drinking water for three days.',
        'district':'Prayagraj','channel':'web'})
    assert created.status_code==201, created.text
    case=created.json()
    assert case['category']=='Water Supply'
    assert case['status']=='new'
    assert case['citizen_id']==4
    assert case['ticket_no'].startswith('UP-')
    assert client.get(f"/api/complaints/{case['id']}",headers=citizen).status_code==200
    assert client.get('/api/complaints?status=new',headers=citizen).status_code==200
    assert client.patch(f"/api/complaints/{case['id']}",headers=citizen,json={'status':'resolved'}).status_code==403
    updated=client.patch(f"/api/complaints/{case['id']}",headers=auth(client,'admin'),json={
        'status':'in_progress','priority':'high','assigned_to':3})
    assert updated.status_code==200
    assert updated.json()['status']=='in_progress'
    assert updated.json()['assigned_to']==3
    assert client.post(f"/api/complaints/{case['id']}/notes",headers=auth(client,'admin'),json={
        'body':'Officer visited site and requested inspection.','is_public':True}).status_code==201
    assert client.post(f"/api/complaints/{case['id']}/notes",headers=auth(client,'admin'),json={
        'body':'Internal supervisor review needed.','is_public':False}).status_code==201
    details=client.get(f"/api/complaints/{case['id']}",headers=citizen).json()
    assert len(details['notes'])==1
    assert 'Officer visited' in details['notes'][0]['body']
    full=client.get(f"/api/complaints/{case['id']}",headers=auth(client,'admin')).json()
    assert len(full['notes'])==2
    assert len(full['history'])>=5
    done=client.patch(f"/api/complaints/{case['id']}",headers=auth(client,'admin'),json={'status':'resolved'}).json()
    assert done['resolved_at'] is not None


def test_citizen_privacy_search_and_export(client):
    citizen=auth(client,'citizen');admin=auth(client)
    cases=client.get('/api/complaints?page_size=100',headers=citizen).json()
    assert all(c['citizen_id']==4 for c in cases['items'])
    someone_else=client.get('/api/complaints?page_size=100',headers=admin).json()['items']
    restricted=next(c for c in someone_else if c['citizen_id'] is None)
    assert client.get(f"/api/complaints/{restricted['id']}",headers=citizen).status_code==404
    invalid_search=client.get('/api/complaints?search=%27%20OR%201%3D1%20--',headers=admin)
    assert invalid_search.status_code==200
    csv_data=client.get('/api/export/complaints.csv',headers=admin)
    assert csv_data.status_code==200
    assert csv_data.text.startswith('ticket_no,title,description')
    assert 'UP-' in csv_data.text


def test_attachment_upload_and_validation(client):
    citizen=auth(client,'citizen')
    assert client.post('/api/attachments',headers=citizen,files={'file':('evil.txt',b'malicious','text/plain')}).status_code==400
    # Valid 1x1 PNG, no image inference takes place.
    image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')
    response=client.post('/api/attachments',headers=citizen,files={'file':('pothole.png',image,'image/png')})
    assert response.status_code==200, response.text
    payload=response.json()
    assert payload['description'].startswith('Filename hint:')
    assert client.get(payload['url'],headers=citizen).content==image
    assert client.post('/api/complaints',headers=citizen,json={'title':'Road issue with attached photograph',
        'description':'Deep pothole in the busy market road.','district':'Prayagraj',
        'channel':'photo','attachment_path':payload['path']}).status_code==201


def test_settings_and_reset(client):
    admin=auth(client)
    officers=client.get('/api/users/officers',headers=admin).json()
    assert len(officers)>=3
    assert client.get('/api/insights',headers=admin).json()['clusters']
    assert client.get('/api/departments',headers=admin).json()
    client.post('/api/complaints',headers=admin,json={'title':'Additional road issue',
        'description':'Broken road near community market requires repair.','district':'Lucknow'})
    assert client.get('/api/dashboard',headers=admin).json()['stats']['total']==521
    assert client.post('/api/admin/reset-demo',headers=admin,json={}).status_code==200
    assert client.get('/api/dashboard',headers=auth(client)).json()['stats']['total']==520


def test_lite_frontend_routes_and_assets(client):
    root = client.get('/')
    assert root.status_code == 200
    assert 'No-install Preview' in root.text
    css = client.get('/lite/style.css')
    js = client.get('/lite/app.js')
    assert css.status_code == 200 and '.sidebar' in css.text
    assert js.status_code == 200 and 'Mock analysis complete' in js.text
    assert client.get('/lite/private.env').status_code == 404


def test_attachment_filename_hint_consistent_preview_and_submission(client):
    citizen = auth(client, 'citizen')
    payload = {
        'title': 'Please inspect and repair public facility',
        'description': 'The site requires urgent inspection and a completion schedule.',
        'district': 'Prayagraj', 'image_hint': 'anganwadi_site_photo.jpg'
    }
    preview = client.post('/api/ai/analyze', headers=citizen, json=payload).json()
    assert preview['category'] == 'Women & Child Services'
    # Filename hints are only used when there is a real uploaded attachment.
    fake = client.post('/api/complaints', headers=citizen, json={
        **payload, 'attachment_path': '000000000000000000000000.jpg', 'channel': 'photo'
    })
    assert fake.status_code == 422
    image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')
    up = client.post('/api/attachments', headers=citizen,
                     files={'file': ('anganwadi_site_photo.png', image, 'image/png')}).json()
    record = client.post('/api/complaints', headers=citizen,
                         json={**payload, 'channel':'photo', 'attachment_path':up['path']})
    assert record.status_code == 201
    assert record.json()['category'] == preview['category']
    assert record.json()['attachment_description'].startswith('Filename hint:')


def test_null_status_validation_and_department_filter(client):
    admin = auth(client, 'admin')
    one = client.get('/api/complaints?page_size=1', headers=admin).json()['items'][0]
    bad = client.patch(f"/api/complaints/{one['id']}", headers=admin, json={'status':None})
    assert bad.status_code == 422
    dept = one['department']
    response = client.get('/api/complaints', headers=admin, params={'department':dept,'page_size':100})
    assert response.status_code == 200
    assert all(x['department'] == dept for x in response.json()['items'])
