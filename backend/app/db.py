"""SQLite schema and realistic but fully SYNTHETIC demonstration data."""
from __future__ import annotations
import json, os, random, sqlite3, stat
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from .data import DISTRICTS, CATEGORIES, SAMPLE_ISSUES
from .ai import analyze
from .auth import hash_password

DEFAULT_DB = Path(__file__).resolve().parent.parent / 'data' / 'nagrikos.db'


def db_path() -> Path:
    return Path(os.environ.get('DATABASE_PATH', str(DEFAULT_DB))).expanduser()


@contextmanager
def connect():
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == 'posix':
        path.parent.chmod(0o700)
    db = sqlite3.connect(path, timeout=20)
    if os.name == 'posix':
        path.chmod(0o600)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA secure_delete=ON')
    db.execute('PRAGMA busy_timeout=20000')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


SCHEMA = '''
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL, department TEXT, district TEXT, created_at TEXT NOT NULL,
 mfa_secret TEXT, mfa_pending TEXT, mfa_last_counter INTEGER NOT NULL DEFAULT -1
);
CREATE TABLE IF NOT EXISTS complaints (
 id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_no TEXT UNIQUE, title TEXT NOT NULL,
 description TEXT NOT NULL, district TEXT NOT NULL, category TEXT NOT NULL, department TEXT NOT NULL,
 priority TEXT NOT NULL, urgency_score INTEGER NOT NULL, confidence REAL NOT NULL,
 estimated_hours INTEGER NOT NULL, rationale TEXT NOT NULL, language TEXT NOT NULL, tags TEXT NOT NULL,
 status TEXT NOT NULL, channel TEXT NOT NULL, citizen_id INTEGER REFERENCES users(id),
 assigned_to INTEGER REFERENCES users(id), attachment_path TEXT, attachment_description TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, due_at TEXT NOT NULL, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
 actor_id INTEGER REFERENCES users(id), action TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notes (
 id INTEGER PRIMARY KEY AUTOINCREMENT, complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE,
 author_id INTEGER NOT NULL REFERENCES users(id), body TEXT NOT NULL, is_public INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 csrf_hash TEXT NOT NULL, expires_at INTEGER NOT NULL, created_at INTEGER NOT NULL,
 last_seen_at INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS login_attempts (
 identifier TEXT NOT NULL, attempted_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts ON login_attempts(identifier,attempted_at);
CREATE TABLE IF NOT EXISTS attachments (
 filename TEXT PRIMARY KEY, uploaded_by INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 complaint_id INTEGER REFERENCES complaints(id) ON DELETE SET NULL,
 original_name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_created ON complaints(created_at);
CREATE INDEX IF NOT EXISTS idx_complaints_department ON complaints(department);
CREATE INDEX IF NOT EXISTS idx_complaints_district ON complaints(district);
CREATE INDEX IF NOT EXISTS idx_complaints_citizen ON complaints(citizen_id);
CREATE TABLE IF NOT EXISTS account_tokens (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 purpose TEXT NOT NULL, expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 used_at INTEGER, created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_tokens_user ON account_tokens(user_id,purpose);
CREATE TABLE IF NOT EXISTS auth_challenges (
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at INTEGER NOT NULL, attempts INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS recovery_codes (
 code_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS mail_outbox (
 id INTEGER PRIMARY KEY AUTOINCREMENT, recipient TEXT NOT NULL, subject TEXT NOT NULL,
 body TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS staff_invitations (
 token_hash TEXT PRIMARY KEY, email TEXT NOT NULL, name TEXT NOT NULL,
 role TEXT NOT NULL, department TEXT, district TEXT, expires_at INTEGER NOT NULL,
 used_at INTEGER, invited_by INTEGER NOT NULL REFERENCES users(id)
);
'''

USERS = [
 (1,'Ananya Sharma','admin@demo.in','admin','General Administration','Lucknow'),
 (2,'Rahul Verma','officer@demo.in','officer','Public Works Department','Prayagraj'),
 (3,'Priya Singh','water@demo.in','officer','Water Supply & Sanitation','Varanasi'),
 (4,'Aarav Kumar','citizen@demo.in','citizen',None,'Prayagraj'),
 (5,'Sana Ali','health@demo.in','officer','Health & Family Welfare','Lucknow'),
]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def seed_database(db: sqlite3.Connection, count: int = 520) -> None:
    rng = random.Random(1076)
    now = datetime.now(timezone.utc)
    for user_id, name, email, role, dept, district in USERS:
        db.execute('INSERT INTO users (id,name,email,password_hash,role,department,district,created_at,email_canonical,email_verified_at,is_demo) VALUES (?,?,?,?,?,?,?,?,?,?,?)', (
            user_id, name, email, hash_password('demo123'), role, dept, district, iso(now), email, int(now.timestamp()), 1))
    major = ['Lucknow','Prayagraj','Varanasi','Kanpur Nagar','Gorakhpur','Agra','Ghaziabad','Meerut','Ayodhya','Jhansi']
    for i in range(count):
        description, expected = rng.choice(SAMPLE_ISSUES)
        district = rng.choice(major) if rng.random() < .54 else rng.choice(DISTRICTS)
        title = {
            'Roads & Infrastructure':'Road repair and infrastructure complaint',
            'Water Supply':'Water supply disruption reported',
            'Electricity':'Power service disruption reported',
            'Sanitation & Waste':'Sanitation service complaint',
            'Healthcare':'Public health facility complaint',
            'Education':'School facilities complaint',
            'Women & Child Services':'Anganwadi services complaint',
            'Land & Revenue':'Land record grievance',
            'Public Safety':'Community safety concern',
            'Social Benefits':'Social benefit payment complaint',
        }[expected]
        ai = analyze(description, title)
        # Some complaints intentionally remain newly filed to give officers a meaningful queue.
        age_days = rng.randint(0, 195)
        created = now - timedelta(days=age_days, hours=rng.randint(0,23))
        status = rng.choices(['new','in_progress','escalated','resolved'], weights=[23,34,11,32])[0]
        if age_days < 2 and status == 'resolved': status = 'new'
        if age_days < 5 and status == 'escalated': status = 'in_progress'
        resolved = created + timedelta(hours=rng.randint(12, ai['estimated_hours'] * 2)) if status == 'resolved' else None
        if resolved and resolved > now: resolved = now - timedelta(hours=1)
        assigned_to = 2 if ai['department'] == 'Public Works Department' else (3 if ai['department']=='Water Supply & Sanitation' else (5 if ai['department']=='Health & Family Welfare' else None))
        if status == 'new': assigned_to = None
        citizen_id = 4 if i % 28 == 0 else None
        due = created + timedelta(hours=ai['estimated_hours'])
        db.execute('''INSERT INTO complaints (ticket_no,title,description,district,category,department,
          priority,urgency_score,confidence,estimated_hours,rationale,language,tags,status,channel,
          citizen_id,assigned_to,attachment_path,attachment_description,created_at,updated_at,due_at,resolved_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (
            f'UP-{created.year}-{i+1:06d}', title, description, district, ai['category'], ai['department'],
            ai['priority'], ai['urgency_score'], ai['confidence'], ai['estimated_hours'],ai['rationale'],
            ai['language'], json.dumps(ai['tags']), status, rng.choice(['web','web','voice','photo']),
            citizen_id, assigned_to, None, None, iso(created), iso(resolved or min(now, created + timedelta(days=rng.randint(0,4)))),
            iso(due), iso(resolved) if resolved else None))
        complaint_id = db.execute('SELECT last_insert_rowid()').fetchone()[0]
        db.execute('INSERT INTO history(complaint_id,actor_id,action,details,created_at) VALUES (?,?,?,?,?)',
                   (complaint_id,None,'created','Demo complaint imported from synthetic seed data.',iso(created)))
        if status != 'new':
            db.execute('INSERT INTO history(complaint_id,actor_id,action,details,created_at) VALUES (?,?,?,?,?)',
                       (complaint_id, assigned_to, 'status_changed', f'Status set to {status.replace("_", " ")}.',
                        iso(resolved or min(now, created + timedelta(days=2)))))


def initialize() -> None:
    with connect() as db:
        db.executescript(SCHEMA)
        # v2/v3 upgrades must preserve accounts and submitted cases.
        user_cols = {r['name'] for r in db.execute('PRAGMA table_info(users)')}
        legacy_email_state = 'email_verified_at' not in user_cols
        session_cols = {r['name'] for r in db.execute('PRAGMA table_info(sessions)')}
        for name, definition in [('mfa_secret','TEXT'),('mfa_pending','TEXT'),('mfa_last_counter','INTEGER NOT NULL DEFAULT -1'),
                                 ('email_canonical','TEXT'),('email_verified_at','INTEGER'),('is_demo','INTEGER NOT NULL DEFAULT 0'),
                                 ('mfa_pending_expires_at','INTEGER'),('mfa_pending_attempts','INTEGER NOT NULL DEFAULT 0')]:
            if name not in user_cols: db.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        db.execute('UPDATE users SET email_canonical=lower(trim(email)) WHERE email_canonical IS NULL')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_canonical ON users(email_canonical)')
        if legacy_email_state:
            db.execute("UPDATE users SET email_verified_at=CAST(strftime('%s',created_at) AS INTEGER) WHERE email_verified_at IS NULL")
        # Classify legacy seed identities once; newly provisioned accounts remain independent.
        if legacy_email_state:
            db.executemany('UPDATE users SET is_demo=1 WHERE id=? AND email_canonical=?', [(r[0],r[2]) for r in USERS])
        if 'last_seen_at' not in session_cols:
            db.execute('ALTER TABLE sessions ADD COLUMN last_seen_at INTEGER NOT NULL DEFAULT 0')
            db.execute('UPDATE sessions SET last_seen_at=created_at WHERE last_seen_at=0')
        if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0 and os.getenv('NAGRIKOS_MODE') == 'demo':
            seed_database(db)


def reset_demo() -> None:
    if os.getenv('NAGRIKOS_MODE') != 'demo':
        raise ValueError('Demo reset is available only in explicit demo mode')
    with connect() as db:
        db.execute('DELETE FROM notes')
        db.execute('DELETE FROM history')
        db.execute('DELETE FROM complaints')
        db.execute('DELETE FROM attachments')
        db.execute('DELETE FROM sessions')
        db.execute('DELETE FROM login_attempts')
        db.execute('DELETE FROM users')
        db.execute('DELETE FROM sqlite_sequence WHERE name IN ("complaints","history","notes")')
        seed_database(db)
