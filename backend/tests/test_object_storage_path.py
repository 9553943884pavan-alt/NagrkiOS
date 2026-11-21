"""Synthetic, mocked private-storage flow; no S3 service is contacted."""
from __future__ import annotations

import base64
import io
import re
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, object_storage, postgres
from app.db import connect, iso
from app.auth import hash_password

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC')


def login(client, email='citizen@demo.in'):
    response = client.post('/api/auth/login', json={'email': email, 'password': 'demo123'})
    assert response.status_code == 200
    csrf = response.cookies['nagrikos_csrf']
    return {'Cookie': f'nagrikos_session={response.cookies["nagrikos_session"]}; nagrikos_csrf={csrf}',
            'X-CSRF-Token': csrf}


@pytest.fixture
def cloud(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'app.sqlite3'))
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.setattr(main, 'UPLOAD_DIR', tmp_path / 'local_uploads')
    objects = {}
    monkeypatch.setattr(object_storage, 'configured', lambda: True)
    monkeypatch.setattr(object_storage, 'put', lambda key, data, content_type: objects.__setitem__(key, bytes(data)))
    monkeypatch.setattr(object_storage, 'get', lambda key: objects.get(key))
    monkeypatch.setattr(object_storage, 'delete', lambda key: objects.pop(key, None))
    return objects


def test_private_cloud_upload_authorization_and_restart(cloud, monkeypatch):
    with TestClient(main.app) as client:
        citizen = login(client)
        admin = login(client, 'admin@demo.in')
        same_department = login(client, 'officer@demo.in')
        with connect() as db:
            db.execute('INSERT INTO users (id,name,email,email_canonical,email_verified_at,password_hash,role,department,district,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (6, 'Synthetic Other Citizen', 'other@demo.in', 'other@demo.in', 1,
                        hash_password('demo123'), 'citizen', None, 'Lucknow', iso(datetime.now(timezone.utc))))
            db.execute('INSERT INTO users (id,name,email,email_canonical,email_verified_at,password_hash,role,department,district,created_at) VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (7, 'Synthetic Other Officer', 'other-water@demo.in', 'other-water@demo.in', 1,
                        hash_password('demo123'), 'officer', 'Water Supply & Sanitation', 'Lucknow', iso(datetime.now(timezone.utc))))
        other_citizen = login(client, 'other@demo.in')
        other_department = login(client, 'other-water@demo.in')
        upload = client.post('/api/attachments', headers=citizen,
                             files={'file': ('street.png', PNG, 'image/png')})
        assert upload.status_code == 200, upload.text
        body = upload.json()
        assert body['path'] in cloud
        assert client.get(body['url'], headers=citizen).content == cloud[body['path']]
        assert client.get(body['url'], headers=admin).status_code == 404  # Unattached is uploader-private.
        assert client.get(body['url'], headers=other_citizen).status_code == 404
        complaint = {'title': 'Synthetic road complaint', 'description': 'A synthetic road defect is shown in this test.',
                     'district': 'Lucknow', 'channel': 'photo', 'attachment_path': body['path']}
        assert client.post('/api/complaints', headers=citizen, json=complaint).status_code == 201
        assert client.get(body['url'], headers=admin).status_code == 200
        assert client.get(body['url'], headers=same_department).status_code == 200
        assert client.get(body['url'], headers=other_department).status_code == 404
        assert client.get(body['url'], headers=other_citizen).status_code == 404
        original_get = object_storage.get
        monkeypatch.setattr(object_storage, 'get', lambda _key: (_ for _ in ()).throw(TimeoutError()))
        assert client.get(body['url'], headers=citizen).status_code == 503
        assert client.get(body['url'], headers=other_citizen).status_code == 404
        monkeypatch.setattr(object_storage, 'get', original_get)
        assert client.post('/api/complaints', headers=citizen, json=complaint).status_code == 422
        assert not (main.UPLOAD_DIR / body['path']).exists()
    with TestClient(main.app) as restarted:
        citizen = login(restarted)
        assert restarted.get(body['url'], headers=citizen).status_code == 200


def test_private_object_keys_are_random_and_anonymous_access_is_denied(cloud):
    with TestClient(main.app) as client:
        citizen = login(client)
        first = client.post('/api/attachments', headers=citizen,
                            files={'file': ('street.png', PNG, 'image/png')})
        second = client.post('/api/attachments', headers=citizen,
                             files={'file': ('street.png', PNG, 'image/png')})
        assert first.status_code == second.status_code == 200
        keys = {first.json()['path'], second.json()['path']}
        assert len(keys) == 2
        assert all(re.fullmatch(r'[a-f0-9]{24}\.png', key) for key in keys)
        with TestClient(main.app) as anonymous:
            for key in keys:
                assert anonymous.get(f'/api/attachments/{key}').status_code == 401
                assert client.get(f'/api/attachments/{key}', headers=citizen).content == PNG
        assert client.get('/api/attachments/../private').status_code in (404, 422)


def test_mocked_put_failure_and_invalid_upload_leave_no_metadata(cloud, monkeypatch):
    with TestClient(main.app) as client:
        citizen = login(client)
        assert client.post('/api/attachments', headers=citizen,
                           files={'file': ('bad.txt', b'bad', 'text/plain')}).status_code == 400
        assert client.post('/api/attachments', headers=citizen,
                           files={'file': ('big.png', b'\x89PNG\r\n\x1a\n' + b'x' * (5 * 1024 * 1024), 'image/png')}).status_code == 413
        monkeypatch.setattr(object_storage, 'put', lambda *_args: (_ for _ in ()).throw(TimeoutError()))
        response = client.post('/api/attachments', headers=citizen,
                               files={'file': ('street.png', PNG, 'image/png')})
        assert response.status_code == 503
        assert not cloud
        def interrupted_put(key, data, _content_type):
            cloud[key] = bytes(data)
            raise TimeoutError('synthetic interrupted response after remote write')
        monkeypatch.setattr(object_storage, 'put', interrupted_put)
        response = client.post('/api/attachments', headers=citizen,
                               files={'file': ('street.png', PNG, 'image/png')})
        assert response.status_code == 503
        assert not cloud
        with connect() as db:
            assert db.execute('SELECT count(*) FROM attachments').fetchone()[0] == 0


def test_metadata_failure_cleans_new_object(cloud, monkeypatch):
    with TestClient(main.app, raise_server_exceptions=False) as client:
        citizen = login(client)
        @contextmanager
        def broken_db():
            raise RuntimeError('synthetic DB failure')
            yield
        monkeypatch.setattr(main, 'connect', broken_db)
        response = client.post('/api/attachments', headers=citizen,
                               files={'file': ('street.png', PNG, 'image/png')})
        assert response.status_code == 500
        assert not cloud


def test_failed_remote_cleanup_leaves_detectable_orphan_without_metadata(cloud, monkeypatch):
    with TestClient(main.app) as client:
        citizen = login(client)
        def interrupted_put(key, data, _content_type):
            cloud[key] = bytes(data)
            raise TimeoutError('synthetic timeout after remote write')
        monkeypatch.setattr(object_storage, 'put', interrupted_put)
        monkeypatch.setattr(object_storage, 'delete', lambda _key: (_ for _ in ()).throw(TimeoutError()))
        response = client.post('/api/attachments', headers=citizen,
                               files={'file': ('street.png', PNG, 'image/png')})
        assert response.status_code == 503
        with connect() as db:
            assert db.execute('SELECT COUNT(*) FROM attachments').fetchone()[0] == 0
        assert len(cloud) == 1  # A timed-out delete needs protected reconciliation.
        assert set(cloud).issubset({key for key in cloud if object_storage.KEY.fullmatch(key)})


def test_storage_config_validation_and_neon_pooling(monkeypatch):
    for key in object_storage.REQUIRED:
        monkeypatch.delenv(key, raising=False)
    object_storage.validate_config()
    monkeypatch.setenv('OBJECT_STORAGE_ENDPOINT_URL', 'http://example.invalid')
    with pytest.raises(RuntimeError, match='incomplete'):
        object_storage.validate_config()
    for key, value in {
        'OBJECT_STORAGE_ENDPOINT_URL': 'https://example-account.r2.cloudflarestorage.com',
        'OBJECT_STORAGE_REGION': 'auto', 'OBJECT_STORAGE_ACCESS_KEY_ID': 'synthetic-key',
        'OBJECT_STORAGE_SECRET_ACCESS_KEY': 'synthetic-secret',
        'OBJECT_STORAGE_BUCKET': 'synthetic-private-bucket',
    }.items():
        monkeypatch.setenv(key, value)
    object_storage.validate_config()
    monkeypatch.setenv('OBJECT_STORAGE_REGION', 'bad region')
    with pytest.raises(RuntimeError, match='region is invalid'):
        object_storage.validate_config()
    monkeypatch.setenv('OBJECT_STORAGE_REGION', 'auto')
    for bad_endpoint in ('http://example.com', 'https://localhost', 'https://127.0.0.1',
                         'https://user:password@example.com', 'https://example.com/path',
                         'https://example.invalid'):
        monkeypatch.setenv('OBJECT_STORAGE_ENDPOINT_URL', bad_endpoint)
        with pytest.raises(RuntimeError, match='HTTPS S3 endpoint'):
            object_storage.validate_config()
    monkeypatch.setenv('OBJECT_STORAGE_ENDPOINT_URL', 'https://example.com:bad')
    with pytest.raises(RuntimeError, match='endpoint URL is invalid'):
        object_storage.validate_config()
    with pytest.raises(RuntimeError, match='pooled endpoint'):
        postgres._url('postgresql://role:secret@ep-test.region.aws.neon.tech/app?sslmode=require')


def test_s3_adapter_uses_signed_private_client_without_network(monkeypatch):
    from botocore.stub import Stubber
    for key, value in {
        'OBJECT_STORAGE_ENDPOINT_URL': 'https://example-account.r2.cloudflarestorage.com',
        'OBJECT_STORAGE_REGION': 'auto', 'OBJECT_STORAGE_ACCESS_KEY_ID': 'synthetic-key',
        'OBJECT_STORAGE_SECRET_ACCESS_KEY': 'synthetic-secret',
        'OBJECT_STORAGE_BUCKET': 'synthetic-private-bucket',
    }.items():
        monkeypatch.setenv(key, value)
    object_storage._client.cache_clear()
    client = object_storage._client()
    assert client.meta.config.signature_version == 's3v4'
    assert client.meta.config.s3['addressing_style'] == 'path'
    assert client.meta.endpoint_url == 'https://example-account.r2.cloudflarestorage.com'
    key = 'a' * 24 + '.png'
    bucket = 'synthetic-private-bucket'
    with Stubber(client) as stub:
        stub.add_response('put_object', {}, {'Bucket': bucket, 'Key': key, 'Body': PNG,
                                             'ContentType': 'image/png', 'CacheControl': 'private, no-store'})
        stub.add_response('get_object', {'Body': io.BytesIO(PNG)}, {'Bucket': bucket, 'Key': key})
        stub.add_response('delete_object', {}, {'Bucket': bucket, 'Key': key})
        object_storage.put(key, PNG, 'image/png')
        assert object_storage.get(key) == PNG
        object_storage.delete(key)
        stub.assert_no_pending_responses()
    object_storage._client.cache_clear()


def neon_settings(monkeypatch, endpoint='testing', database='testing'):
    testing_storage = 'https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech'
    production_storage = 'https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech'
    testing_database = 'ep-curly-term-a7dqknkk-pooler.ap-southeast-2.aws.neon.tech'
    production_database = 'ep-frosty-union-a7d7vufy-pooler.ap-southeast-2.aws.neon.tech'
    for name in object_storage.REQUIRED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('OBJECT_STORAGE_BACKEND', 'neon')
    monkeypatch.setenv('AWS_ACCESS_KEY_ID', 'synthetic-access-key')
    monkeypatch.setenv('AWS_SECRET_ACCESS_KEY', 'synthetic-secret-key')
    monkeypatch.setenv('AWS_ENDPOINT_URL_S3', testing_storage if endpoint == 'testing' else production_storage)
    monkeypatch.setenv('AWS_REGION', 'ap-southeast-1')
    monkeypatch.setenv('OBJECT_STORAGE_BUCKET', 'nagrikos-attachments')
    host = testing_database if database == 'testing' else production_database
    monkeypatch.setenv('DATABASE_URL', f'postgresql://dummy:password@{host}/dummy?sslmode=require')


def test_neon_testing_s3_client_is_signed_and_path_style_without_network(monkeypatch):
    neon_settings(monkeypatch)
    object_storage.validate_config()
    assert object_storage.configured()
    object_storage._client.cache_clear()
    try:
        client = object_storage._client()
        assert client.meta.endpoint_url == 'https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech'
        assert client.meta.config.signature_version == 's3v4'
        assert client.meta.config.s3['addressing_style'] == 'path'
        from botocore.stub import Stubber
        key = 'b' * 24 + '.webp'
        with Stubber(client) as stub:
            stub.add_response('put_object', {}, {'Bucket': 'nagrikos-attachments', 'Key': key,
                                                 'Body': b'synthetic', 'ContentType': 'image/webp',
                                                 'CacheControl': 'private, no-store'})
            object_storage.put(key, b'synthetic', 'image/webp')
            stub.assert_no_pending_responses()
    finally:
        object_storage._client.cache_clear()


def test_neon_production_pair_is_valid_with_dummy_credentials_only(monkeypatch):
    neon_settings(monkeypatch, endpoint='production', database='production')
    object_storage.validate_config()
    assert object_storage.configured()


@pytest.mark.parametrize('endpoint,database', [
    ('testing', 'production'), ('production', 'testing'),
])
def test_neon_storage_and_database_branch_pairing_rejects_mixed_environment(monkeypatch, endpoint, database):
    neon_settings(monkeypatch, endpoint, database)
    with pytest.raises(RuntimeError):
        object_storage.validate_config()


@pytest.mark.parametrize('missing', ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
                                     'AWS_ENDPOINT_URL_S3', 'AWS_REGION', 'OBJECT_STORAGE_BUCKET'])
def test_neon_storage_rejects_missing_credentials_or_target(monkeypatch, missing):
    neon_settings(monkeypatch)
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError):
        object_storage.validate_config()


def test_neon_storage_rejects_legacy_credential_mixing(monkeypatch):
    neon_settings(monkeypatch)
    monkeypatch.setenv('OBJECT_STORAGE_ACCESS_KEY_ID', 'different-synthetic-key')
    with pytest.raises(RuntimeError):
        object_storage.validate_config()


@pytest.mark.parametrize('name,value', [
    ('AWS_ENDPOINT_URL_S3', 'https://unapproved.storage.c-3.ap-southeast-1.aws.neon.tech'),
    ('AWS_ENDPOINT_URL_S3', 'http://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech'),
    ('AWS_REGION', 'ap-southeast-2'),
    ('OBJECT_STORAGE_BUCKET', 'other-private-bucket'),
    ('AWS_ACCESS_KEY_ID', ' synthetic-access-key '),
    ('AWS_SECRET_ACCESS_KEY', 'synthetic-secret-key '),
])
def test_neon_storage_rejects_unknown_target_or_whitespace_credentials(monkeypatch, name, value):
    neon_settings(monkeypatch)
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        object_storage.validate_config()


def test_public_mode_refuses_local_photo_upload_and_required_storage_startup(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'app.sqlite3'))
    monkeypatch.setattr(object_storage, 'configured', lambda: False)
    with TestClient(main.app) as client:
        citizen = login(client)
        monkeypatch.setattr(main, 'mode', lambda: 'public')
        response = client.post('/api/attachments', headers=citizen,
                               files={'file': ('street.png', PNG, 'image/png')})
        assert response.status_code == 503
        denied = client.post('/api/complaints', headers=citizen, json={
            'title': 'Synthetic road complaint', 'description': 'A synthetic road defect is shown in this test.',
            'district': 'Lucknow', 'channel': 'photo', 'attachment_path': 'a' * 24 + '.png'})
        assert denied.status_code == 503
    monkeypatch.setenv('NAGRIKOS_REQUIRE_DURABLE_STORAGE', 'true')
    monkeypatch.setattr(main, 'validate_config', lambda: None)
    with pytest.raises(RuntimeError, match='private durable object storage'):
        with TestClient(main.app):
            pass


def test_private_reconciliation_listing_has_no_public_route(monkeypatch):
    class Client:
        def list_objects_v2(self, **kwargs):
            assert kwargs['Bucket'] == 'synthetic-private-bucket'
            return {'IsTruncated': False, 'Contents': [
                {'Key': 'a' * 24 + '.png'}, {'Key': 'unrelated/private-note.txt'}]}
    monkeypatch.setenv('OBJECT_STORAGE_BUCKET', 'synthetic-private-bucket')
    monkeypatch.setattr(object_storage, '_client', lambda: Client())
    assert object_storage.list_attachment_keys() == {'a' * 24 + '.png'}
