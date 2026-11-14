"""Relational schema used by Alembic for PostgreSQL."""
from sqlalchemy import Column, Float, ForeignKey, Index, Integer, MetaData, Table, Text

metadata = MetaData()

users = Table('users', metadata,
    Column('id', Integer, primary_key=True), Column('name', Text, nullable=False),
    Column('email', Text, nullable=False, unique=True), Column('password_hash', Text, nullable=False),
    Column('role', Text, nullable=False), Column('department', Text), Column('district', Text),
    Column('created_at', Text, nullable=False), Column('mfa_secret', Text), Column('mfa_pending', Text),
    Column('mfa_last_counter', Integer, nullable=False, server_default='-1'),
    Column('email_canonical', Text), Column('email_verified_at', Integer),
    Column('is_demo', Integer, nullable=False, server_default='0'),
    Column('mfa_pending_expires_at', Integer),
    Column('mfa_pending_attempts', Integer, nullable=False, server_default='0'))
Index('idx_users_email_canonical', users.c.email_canonical, unique=True)

complaints = Table('complaints', metadata,
    Column('id', Integer, primary_key=True), Column('ticket_no', Text, unique=True),
    Column('title', Text, nullable=False), Column('description', Text, nullable=False),
    Column('district', Text, nullable=False), Column('category', Text, nullable=False),
    Column('department', Text, nullable=False), Column('priority', Text, nullable=False),
    Column('urgency_score', Integer, nullable=False), Column('confidence', Float, nullable=False),
    Column('estimated_hours', Integer, nullable=False), Column('rationale', Text, nullable=False),
    Column('language', Text, nullable=False), Column('tags', Text, nullable=False),
    Column('status', Text, nullable=False), Column('channel', Text, nullable=False),
    Column('citizen_id', Integer, ForeignKey('users.id')),
    Column('assigned_to', Integer, ForeignKey('users.id')),
    Column('attachment_path', Text), Column('attachment_description', Text),
    Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False),
    Column('due_at', Text, nullable=False), Column('resolved_at', Text))
for name in ('status', 'created_at', 'department', 'district', 'citizen_id'):
    Index(f'idx_complaints_{name}', complaints.c[name])

history = Table('history', metadata,
    Column('id', Integer, primary_key=True),
    Column('complaint_id', Integer, ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False),
    Column('actor_id', Integer, ForeignKey('users.id')),
    Column('action', Text, nullable=False), Column('details', Text, nullable=False),
    Column('created_at', Text, nullable=False))
notes = Table('notes', metadata,
    Column('id', Integer, primary_key=True),
    Column('complaint_id', Integer, ForeignKey('complaints.id', ondelete='CASCADE'), nullable=False),
    Column('author_id', Integer, ForeignKey('users.id'), nullable=False),
    Column('body', Text, nullable=False), Column('is_public', Integer, nullable=False, server_default='0'),
    Column('created_at', Text, nullable=False))
sessions = Table('sessions', metadata,
    Column('token_hash', Text, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('csrf_hash', Text, nullable=False), Column('expires_at', Integer, nullable=False),
    Column('created_at', Integer, nullable=False), Column('last_seen_at', Integer, nullable=False, server_default='0'))
Index('idx_sessions_user', sessions.c.user_id)
Index('idx_sessions_expiry', sessions.c.expires_at)
login_attempts = Table('login_attempts', metadata,
    Column('identifier', Text, nullable=False), Column('attempted_at', Integer, nullable=False))
Index('idx_attempts', login_attempts.c.identifier, login_attempts.c.attempted_at)
attachments = Table('attachments', metadata,
    Column('filename', Text, primary_key=True),
    Column('uploaded_by', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('complaint_id', Integer, ForeignKey('complaints.id', ondelete='SET NULL')),
    Column('original_name', Text, nullable=False), Column('created_at', Text, nullable=False))
account_tokens = Table('account_tokens', metadata,
    Column('token_hash', Text, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('purpose', Text, nullable=False), Column('expires_at', Integer, nullable=False),
    Column('attempts', Integer, nullable=False, server_default='0'),
    Column('used_at', Integer), Column('created_at', Integer, nullable=False))
Index('idx_account_tokens_user', account_tokens.c.user_id, account_tokens.c.purpose)
auth_challenges = Table('auth_challenges', metadata,
    Column('token_hash', Text, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('expires_at', Integer, nullable=False),
    Column('attempts', Integer, nullable=False, server_default='0'))
recovery_codes = Table('recovery_codes', metadata,
    Column('code_hash', Text, primary_key=True),
    Column('user_id', Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
    Column('created_at', Integer, nullable=False))
mail_outbox = Table('mail_outbox', metadata,
    Column('id', Integer, primary_key=True), Column('recipient', Text, nullable=False),
    Column('subject', Text, nullable=False), Column('body', Text, nullable=False),
    Column('created_at', Integer, nullable=False))
staff_invitations = Table('staff_invitations', metadata,
    Column('token_hash', Text, primary_key=True), Column('email', Text, nullable=False),
    Column('name', Text, nullable=False), Column('role', Text, nullable=False),
    Column('department', Text), Column('district', Text),
    Column('expires_at', Integer, nullable=False), Column('used_at', Integer),
    Column('invited_by', Integer, ForeignKey('users.id'), nullable=False))
