"""Revocable opaque-cookie sessions, Argon2id password hashes, optional TOTP and CSRF checks.

This is *local demo* hardening, not a substitute for external identity verification.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, Response

SESSION_COOKIE = 'nagrikos_session'
CSRF_COOKIE = 'nagrikos_csrf'
SESSION_SECONDS = 12 * 60 * 60
SESSION_IDLE_SECONDS = 30 * 60
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1, hash_len=32, salt_len=16)
def cookie_secure() -> bool:
    return os.getenv('COOKIE_SECURE', 'false').lower() == 'true'


def hash_password(password: str, salt: str | None = None) -> str:
    """Argon2id; salt argument retained for compatibility, never reused."""
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, stored: str, user_id: int) -> tuple[bool, bool]:
    """Verify Argon2id and transparently migrate scrypt / v1 PBKDF2 on login."""
    try:
        if stored.startswith('$argon2id$'):
            valid = PASSWORD_HASHER.verify(stored, password)
            return valid, valid and PASSWORD_HASHER.check_needs_rehash(stored)
        if stored.startswith('scrypt$'):
            _, n, r, p, salt, digest = stored.split('$')
            if (int(n), int(r), int(p)) != (16384, 8, 1):
                return False, False
            expected = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt),
                                      n=16384, r=8, p=1, dklen=32)
            ok = hmac.compare_digest(expected, bytes.fromhex(digest))
            return ok, ok
        if len(stored) == 64:
            old = hashlib.pbkdf2_hmac('sha256', password.encode(),
                                      f'nagrikos-{user_id}'.encode(), 180_000).hex()
            ok = hmac.compare_digest(old, stored)
            return ok, ok
    except (ValueError, TypeError, VerifyMismatchError, VerificationError, InvalidHashError):
        pass
    return False, False


def _mfa_cipher() -> Fernet:
    """Use a separate local key; production deployments should set NAGRIKOS_TOTP_KEY."""
    key = os.getenv('NAGRIKOS_TOTP_KEY', '').strip()
    if key:
        return Fernet(key.encode('ascii'))
    path = Path(os.getenv('NAGRIKOS_TOTP_KEY_FILE', str(Path.home()/'.nagrikos'/'totp.key'))).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix':
        path.parent.chmod(0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, 'wb') as out:
            out.write(Fernet.generate_key())
    if os.name == 'posix':
        path.chmod(0o600)
    return Fernet(path.read_bytes())


def encrypt_totp(secret: str) -> str:
    return _mfa_cipher().encrypt(secret.encode('ascii')).decode('ascii')


def decrypt_totp(secret: str) -> str:
    return _mfa_cipher().decrypt(secret.encode('ascii')).decode('ascii')


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def totp_counter(secret: str, code: str, now: int | None = None, last: int = -1) -> int | None:
    """RFC 6238 TOTP, +/- one step clock skew, never accept a replayed counter."""
    if not (len(code) == 6 and code.isascii() and code.isdigit()):
        return None
    now = int(time.time()) if now is None else now
    secret_bytes = base64.b32decode(secret + '='*((-len(secret))%8), casefold=True)
    for counter in (now//30, now//30-1, now//30+1):
        if counter <= last or counter < 0:
            continue
        digest = hmac.new(secret_bytes, struct.pack('>Q',counter),hashlib.sha1).digest()
        offset = digest[-1] & 0x0f
        otp = (struct.unpack('>I',digest[offset:offset+4])[0] & 0x7fffffff) % 1_000_000
        if hmac.compare_digest(f'{otp:06d}',code):
            return counter
    return None


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def apply_cookies(response: Response, session: str, csrf: str) -> None:
    settings = dict(path='/', samesite='strict', secure=cookie_secure(), max_age=SESSION_SECONDS)
    response.set_cookie(SESSION_COOKIE, session, httponly=True, **settings)
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, **settings)


def remove_cookies(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path='/', samesite='strict', secure=cookie_secure())
    response.delete_cookie(CSRF_COOKIE, path='/', samesite='strict', secure=cookie_secure())


def current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) != 64:
        raise HTTPException(status_code=401, detail='Please sign in')
    from .db import connect
    with connect() as db:
        row = db.execute('''SELECT u.id,u.name,u.email,u.role,u.department,u.district,u.is_demo,u.email_verified_at,
                        s.expires_at,s.last_seen_at FROM sessions s JOIN users u ON u.id=s.user_id
                        WHERE s.token_hash=?''', (token_hash(token),)).fetchone()
    if not row or row['expires_at'] <= int(time.time()) or row['last_seen_at'] <= int(time.time()) - SESSION_IDLE_SECONDS or row['email_verified_at'] is None or (os.getenv('NAGRIKOS_MODE')!='demo' and row['is_demo']):
        raise HTTPException(status_code=401, detail='Session expired; please sign in again')
    if int(time.time()) - row['last_seen_at'] >= 60:
        with connect() as db:
            db.execute('UPDATE sessions SET last_seen_at=? WHERE token_hash=?', (int(time.time()),token_hash(token)))
    return {k: row[k] for k in ('id', 'name', 'email', 'role', 'department', 'district')}


def verify_csrf(request: Request) -> None:
    """Reject forged POST/PATCH/DELETE requests; works with same-origin Vite proxy."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return  # Let the endpoint's auth dependency return 401.
    header = request.headers.get('X-CSRF-Token', '')
    cookie = request.cookies.get(CSRF_COOKIE, '')
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(403, 'Missing or invalid CSRF token')
    from .db import connect
    with connect() as db:
        row = db.execute('SELECT csrf_hash FROM sessions WHERE token_hash=? AND expires_at>? AND last_seen_at>?',
                         (token_hash(token), int(time.time()), int(time.time()) - SESSION_IDLE_SECONDS)).fetchone()
    if not row or not hmac.compare_digest(token_hash(header), row['csrf_hash']):
        raise HTTPException(403, 'Session security check failed')


def require_official(user: dict = Depends(current_user)) -> dict:
    if user['role'] not in ('officer', 'admin'):
        raise HTTPException(403, 'Official access only')
    return user


def require_admin(user: dict = Depends(current_user)) -> dict:
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access only')
    return user


def require_officer(user: dict = Depends(current_user)) -> dict:
    if user['role'] != 'officer':
        raise HTTPException(403, 'Department officer access only')
    return user
