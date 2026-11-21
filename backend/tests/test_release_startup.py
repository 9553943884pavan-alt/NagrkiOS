"""Public configuration boots without touching a production database or bucket."""
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import main


def test_synthetic_public_startup_is_offline(tmp_path, monkeypatch):
    settings = {
        'NAGRIKOS_MODE': 'public',
        'COOKIE_SECURE': 'true',
        'NAGRIKOS_REQUIRE_POSTGRES': 'true',
        'NAGRIKOS_REQUIRE_DURABLE_STORAGE': 'true',
        'DATABASE_URL': ('postgresql://synthetic:synthetic@'
                         'ep-frosty-union-a7d7vufy-pooler.ap-southeast-2.aws.neon.tech/'
                         'synthetic?sslmode=require'),
        'OBJECT_STORAGE_BACKEND': 'neon',
        'OBJECT_STORAGE_BUCKET': 'nagrikos-attachments',
        'AWS_ENDPOINT_URL_S3': 'https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech',
        'AWS_REGION': 'ap-southeast-1',
        'AWS_ACCESS_KEY_ID': 'synthetic-access',
        'AWS_SECRET_ACCESS_KEY': 'synthetic-secret',
        'MAILJET_API_KEY': 'synthetic-public',
        'MAILJET_SECRET_KEY': 'synthetic-private',
        'MAIL_FROM': 'sender@example.org',
        'NAGRIKOS_TOTP_KEY': Fernet.generate_key().decode(),
        'PUBLIC_BASE_URL': 'https://nagrikos.example.org',
        'CORS_ORIGINS': 'https://nagrikos.example.org',
    }
    for key, value in settings.items():
        monkeypatch.setenv(key, value)
    for key in ('DIRECT_URL', 'OBJECT_STORAGE_ENDPOINT_URL', 'OBJECT_STORAGE_REGION',
                'OBJECT_STORAGE_ACCESS_KEY_ID', 'OBJECT_STORAGE_SECRET_ACCESS_KEY'):
        monkeypatch.delenv(key, raising=False)
    calls = []
    monkeypatch.setattr(main, 'initialize', lambda: calls.append('validated_startup'))
    monkeypatch.setattr(main, 'connect', lambda: (_ for _ in ()).throw(AssertionError('database access')))
    monkeypatch.setattr(main, 'UPLOAD_DIR', tmp_path / 'uploads')
    with TestClient(main.app) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json() == {'status': 'ok'}
        assert response.headers['cache-control'] == 'no-store'
        assert calls == ['validated_startup']
