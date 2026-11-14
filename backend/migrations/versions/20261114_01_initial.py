"""Initial PostgreSQL schema matching the additive SQLite auth v5 schema.

Revision ID: 20261114_01
Revises:
"""
from alembic import op

# Frozen DDL for this revision. Later model edits must use a new revision.
SCHEMA_SQL = [
    "\nCREATE TABLE login_attempts (\n\tidentifier TEXT NOT NULL, \n\tattempted_at INTEGER NOT NULL\n)\n\n",
    "CREATE INDEX idx_attempts ON login_attempts (identifier, attempted_at)",
    "\nCREATE TABLE mail_outbox (\n\tid SERIAL NOT NULL, \n\trecipient TEXT NOT NULL, \n\tsubject TEXT NOT NULL, \n\tbody TEXT NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tPRIMARY KEY (id)\n)\n\n",
    "\nCREATE TABLE users (\n\tid SERIAL NOT NULL, \n\tname TEXT NOT NULL, \n\temail TEXT NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\trole TEXT NOT NULL, \n\tdepartment TEXT, \n\tdistrict TEXT, \n\tcreated_at TEXT NOT NULL, \n\tmfa_secret TEXT, \n\tmfa_pending TEXT, \n\tmfa_last_counter INTEGER DEFAULT '-1' NOT NULL, \n\temail_canonical TEXT, \n\temail_verified_at INTEGER, \n\tis_demo INTEGER DEFAULT '0' NOT NULL, \n\tmfa_pending_expires_at INTEGER, \n\tmfa_pending_attempts INTEGER DEFAULT '0' NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (email)\n)\n\n",
    "CREATE UNIQUE INDEX idx_users_email_canonical ON users (email_canonical)",
    "\nCREATE TABLE account_tokens (\n\ttoken_hash TEXT NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tpurpose TEXT NOT NULL, \n\texpires_at INTEGER NOT NULL, \n\tattempts INTEGER DEFAULT '0' NOT NULL, \n\tused_at INTEGER, \n\tcreated_at INTEGER NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n",
    "CREATE INDEX idx_account_tokens_user ON account_tokens (user_id, purpose)",
    "\nCREATE TABLE auth_challenges (\n\ttoken_hash TEXT NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\texpires_at INTEGER NOT NULL, \n\tattempts INTEGER DEFAULT '0' NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n",
    "\nCREATE TABLE complaints (\n\tid SERIAL NOT NULL, \n\tticket_no TEXT, \n\ttitle TEXT NOT NULL, \n\tdescription TEXT NOT NULL, \n\tdistrict TEXT NOT NULL, \n\tcategory TEXT NOT NULL, \n\tdepartment TEXT NOT NULL, \n\tpriority TEXT NOT NULL, \n\turgency_score INTEGER NOT NULL, \n\tconfidence FLOAT NOT NULL, \n\testimated_hours INTEGER NOT NULL, \n\trationale TEXT NOT NULL, \n\tlanguage TEXT NOT NULL, \n\ttags TEXT NOT NULL, \n\tstatus TEXT NOT NULL, \n\tchannel TEXT NOT NULL, \n\tcitizen_id INTEGER, \n\tassigned_to INTEGER, \n\tattachment_path TEXT, \n\tattachment_description TEXT, \n\tcreated_at TEXT NOT NULL, \n\tupdated_at TEXT NOT NULL, \n\tdue_at TEXT NOT NULL, \n\tresolved_at TEXT, \n\tPRIMARY KEY (id), \n\tUNIQUE (ticket_no), \n\tFOREIGN KEY(citizen_id) REFERENCES users (id), \n\tFOREIGN KEY(assigned_to) REFERENCES users (id)\n)\n\n",
    "CREATE INDEX idx_complaints_citizen_id ON complaints (citizen_id)",
    "CREATE INDEX idx_complaints_created_at ON complaints (created_at)",
    "CREATE INDEX idx_complaints_department ON complaints (department)",
    "CREATE INDEX idx_complaints_district ON complaints (district)",
    "CREATE INDEX idx_complaints_status ON complaints (status)",
    "\nCREATE TABLE recovery_codes (\n\tcode_hash TEXT NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tPRIMARY KEY (code_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n",
    "\nCREATE TABLE sessions (\n\ttoken_hash TEXT NOT NULL, \n\tuser_id INTEGER NOT NULL, \n\tcsrf_hash TEXT NOT NULL, \n\texpires_at INTEGER NOT NULL, \n\tcreated_at INTEGER NOT NULL, \n\tlast_seen_at INTEGER DEFAULT '0' NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE\n)\n\n",
    "CREATE INDEX idx_sessions_expiry ON sessions (expires_at)",
    "CREATE INDEX idx_sessions_user ON sessions (user_id)",
    "\nCREATE TABLE staff_invitations (\n\ttoken_hash TEXT NOT NULL, \n\temail TEXT NOT NULL, \n\tname TEXT NOT NULL, \n\trole TEXT NOT NULL, \n\tdepartment TEXT, \n\tdistrict TEXT, \n\texpires_at INTEGER NOT NULL, \n\tused_at INTEGER, \n\tinvited_by INTEGER NOT NULL, \n\tPRIMARY KEY (token_hash), \n\tFOREIGN KEY(invited_by) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE attachments (\n\tfilename TEXT NOT NULL, \n\tuploaded_by INTEGER NOT NULL, \n\tcomplaint_id INTEGER, \n\toriginal_name TEXT NOT NULL, \n\tcreated_at TEXT NOT NULL, \n\tPRIMARY KEY (filename), \n\tFOREIGN KEY(uploaded_by) REFERENCES users (id) ON DELETE CASCADE, \n\tFOREIGN KEY(complaint_id) REFERENCES complaints (id) ON DELETE SET NULL\n)\n\n",
    "\nCREATE TABLE history (\n\tid SERIAL NOT NULL, \n\tcomplaint_id INTEGER NOT NULL, \n\tactor_id INTEGER, \n\taction TEXT NOT NULL, \n\tdetails TEXT NOT NULL, \n\tcreated_at TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(complaint_id) REFERENCES complaints (id) ON DELETE CASCADE, \n\tFOREIGN KEY(actor_id) REFERENCES users (id)\n)\n\n",
    "\nCREATE TABLE notes (\n\tid SERIAL NOT NULL, \n\tcomplaint_id INTEGER NOT NULL, \n\tauthor_id INTEGER NOT NULL, \n\tbody TEXT NOT NULL, \n\tis_public INTEGER DEFAULT '0' NOT NULL, \n\tcreated_at TEXT NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(complaint_id) REFERENCES complaints (id) ON DELETE CASCADE, \n\tFOREIGN KEY(author_id) REFERENCES users (id)\n)\n\n",
]

revision = '20261114_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in SCHEMA_SQL:
        op.execute(statement)


def downgrade():
    # Data-bearing schema removal is intentionally not automated.
    raise RuntimeError('Restore a Neon branch snapshot instead of dropping NagrikOS data')
