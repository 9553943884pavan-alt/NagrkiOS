"""Private S3-compatible attachment bytes; never exposes object URLs.

The bucket's access policy must be verified separately before activation.
Local development keeps the existing filesystem.
"""
from __future__ import annotations

import ipaddress
import os
import re
from functools import lru_cache
from urllib.parse import urlsplit


KEY = re.compile(r'[a-f0-9]{24}\.(?:png|jpg|jpeg|webp)\Z')
BUCKET = re.compile(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]\Z')
HOST = re.compile(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\Z')
REQUIRED = ('OBJECT_STORAGE_ENDPOINT_URL', 'OBJECT_STORAGE_REGION',
            'OBJECT_STORAGE_ACCESS_KEY_ID', 'OBJECT_STORAGE_SECRET_ACCESS_KEY',
            'OBJECT_STORAGE_BUCKET')
NEON_REQUIRED = ('AWS_ENDPOINT_URL_S3', 'AWS_REGION', 'AWS_ACCESS_KEY_ID',
                 'AWS_SECRET_ACCESS_KEY', 'OBJECT_STORAGE_BUCKET')
NEON_ENDPOINTS = {
    'testing': 'https://br-lively-base-azf2mt0j.storage.c-3.ap-southeast-1.aws.neon.tech',
    'production': 'https://br-divine-grass-azierqs7.storage.c-3.ap-southeast-1.aws.neon.tech',
}
NEON_DB_HOSTS = {
    'testing': 'ep-curly-term-a7dqknkk-pooler.ap-southeast-2.aws.neon.tech',
    'production': 'ep-frosty-union-a7d7vufy-pooler.ap-southeast-2.aws.neon.tech',
}
NEON_BUCKET = 'nagrikos-attachments'
MEDIA_TYPES = {'png': 'image/png', 'jpg': 'image/jpeg',
               'jpeg': 'image/jpeg', 'webp': 'image/webp'}


def _backend() -> str:
    backend = os.getenv('OBJECT_STORAGE_BACKEND', '').strip().lower()
    if backend not in {'', 's3', 'neon'}:
        raise RuntimeError('Unsupported object storage backend')
    return backend


def _required() -> tuple[str, ...]:
    return NEON_REQUIRED if _backend() == 'neon' else REQUIRED


def configured() -> bool:
    if _backend() == 'neon' and any(os.getenv(name, '').strip() for name in REQUIRED[:-1]):
        return False
    if _backend() != 'neon' and any(os.getenv(name, '').strip() for name in NEON_REQUIRED[:-1]):
        return False
    return all(os.getenv(name, '').strip() for name in _required())


def validate_config() -> None:
    backend = _backend()
    if backend == 'neon':
        if any(os.getenv(name, '').strip() for name in REQUIRED[:-1]):
            raise RuntimeError('Neon storage cannot mix AWS and legacy object storage settings')
        present = [bool(os.getenv(name, '').strip()) for name in NEON_REQUIRED]
        if not all(present):
            raise RuntimeError('Neon object storage configuration is incomplete')
        endpoint = os.environ['AWS_ENDPOINT_URL_S3']
        stage = next((name for name, expected in NEON_ENDPOINTS.items()
                      if endpoint == expected), None)
        if stage is None:
            raise RuntimeError('Neon object storage endpoint does not match an approved branch')
        if os.environ['AWS_REGION'] != 'ap-southeast-1':
            raise RuntimeError('Neon object storage region must be ap-southeast-1')
        if os.environ['OBJECT_STORAGE_BUCKET'] != NEON_BUCKET:
            raise RuntimeError('Neon object storage bucket does not match the private bucket')
        try:
            db_host = urlsplit(os.environ.get('DATABASE_URL', '')).hostname
        except ValueError as exc:
            raise RuntimeError('Neon storage requires a valid matching Sydney DATABASE_URL') from exc
        if db_host != NEON_DB_HOSTS[stage]:
            raise RuntimeError('Neon storage branch does not match the Sydney database branch')
        for name in ('AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY'):
            if os.environ[name] != os.environ[name].strip():
                raise RuntimeError('Neon storage credentials have surrounding whitespace')
        return
    if any(os.getenv(name, '').strip() for name in NEON_REQUIRED[:-1]):
        raise RuntimeError('Set OBJECT_STORAGE_BACKEND=neon to use AWS storage settings')
    present = [bool(os.getenv(name, '').strip()) for name in REQUIRED]
    if any(present) and not all(present):
        raise RuntimeError('Object storage configuration is incomplete')
    if not all(present):
        return
    value = os.environ['OBJECT_STORAGE_ENDPOINT_URL']
    try:
        endpoint = urlsplit(value)
        host = endpoint.hostname or ''
        port = endpoint.port
    except ValueError as exc:
        raise RuntimeError('Object storage endpoint URL is invalid') from exc
    try:
        ipaddress.ip_address(host)
    except ValueError:
        is_ip = False
    else:
        is_ip = True
    if (value != value.strip() or endpoint.scheme != 'https' or not HOST.fullmatch(host)
            or '.' not in host or host.endswith(('.local', '.internal', '.invalid'))
            or host == 'localhost' or is_ip or endpoint.username or endpoint.password
            or port not in (None, 443) or endpoint.path not in ('', '/')
            or endpoint.query or endpoint.fragment):
        raise RuntimeError('Object storage requires a public DNS HTTPS S3 endpoint without URL credentials')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,62}', os.environ['OBJECT_STORAGE_REGION']):
        raise RuntimeError('Object storage region is invalid')
    if not BUCKET.fullmatch(os.environ['OBJECT_STORAGE_BUCKET']):
        raise RuntimeError('Object storage bucket name is invalid')


@lru_cache(maxsize=4)
def _client_for(endpoint: str, region: str, access_key: str, secret_key: str):
    import boto3
    from botocore.config import Config
    return boto3.client(
        's3', endpoint_url=endpoint, region_name=region,
        aws_access_key_id=access_key, aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4', s3={'addressing_style': 'path'},
                      connect_timeout=5, read_timeout=15, retries={'max_attempts': 3, 'mode': 'standard'}),
    )


def _client():
    validate_config()
    if not configured():
        raise RuntimeError('Private object storage is not configured')
    neon = _backend() == 'neon'
    return _client_for(
        os.environ['AWS_ENDPOINT_URL_S3' if neon else 'OBJECT_STORAGE_ENDPOINT_URL'],
        os.environ['AWS_REGION' if neon else 'OBJECT_STORAGE_REGION'],
        os.environ['AWS_ACCESS_KEY_ID' if neon else 'OBJECT_STORAGE_ACCESS_KEY_ID'],
        os.environ['AWS_SECRET_ACCESS_KEY' if neon else 'OBJECT_STORAGE_SECRET_ACCESS_KEY'],
    )


_client.cache_clear = _client_for.cache_clear


def _key(filename: str) -> str:
    if not KEY.fullmatch(filename):
        raise ValueError('Invalid attachment object key')
    return filename  # The existing attachments.filename primary key is the object key.


def put(filename: str, data: bytes, content_type: str) -> None:
    if len(data) > 5 * 1024 * 1024:
        raise ValueError('Processed image exceeds 5 MB')
    key = _key(filename)
    if content_type != MEDIA_TYPES[key.rsplit('.', 1)[1]]:
        raise ValueError('Content type does not match attachment key')
    _client().put_object(Bucket=os.environ['OBJECT_STORAGE_BUCKET'],
                         Key=key, Body=data, ContentType=content_type,
                         CacheControl='private, no-store')


def get(filename: str) -> bytes | None:
    try:
        response = _client().get_object(Bucket=os.environ['OBJECT_STORAGE_BUCKET'], Key=_key(filename))
    except Exception as exc:
        if getattr(exc, 'response', {}).get('Error', {}).get('Code') in {'NoSuchKey', '404'}:
            return None
        raise
    body = response['Body']
    try:
        data = body.read(5 * 1024 * 1024 + 1)
    finally:
        body.close()
    if len(data) > 5 * 1024 * 1024:
        raise ValueError('Stored attachment exceeds size limit')
    return data


def delete(filename: str) -> None:
    # S3 DeleteObject is idempotent. A failed cleanup can be retried by a
    # protected reconciliation job after comparing keys with DB metadata.
    _client().delete_object(Bucket=os.environ['OBJECT_STORAGE_BUCKET'], Key=_key(filename))


def list_attachment_keys() -> set[str]:
    """Read-only reconciliation input; never expose a public listing route."""
    client = _client()
    bucket = os.environ['OBJECT_STORAGE_BUCKET']
    keys: set[str] = set()
    token = None
    seen_tokens: set[str] = set()
    while True:
        arguments = {'Bucket': bucket, 'MaxKeys': 1000}
        if token:
            arguments['ContinuationToken'] = token
        page = client.list_objects_v2(**arguments)
        keys.update(item['Key'] for item in page.get('Contents', []) if KEY.fullmatch(item['Key']))
        if not page.get('IsTruncated'):
            return keys
        token = page.get('NextContinuationToken')
        if not token:
            raise RuntimeError('Incomplete private object listing')
        if token in seen_tokens:
            raise RuntimeError('Repeated private object listing token')
        seen_tokens.add(token)


