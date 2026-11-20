"""Versioned, transactional local migrations. Run: python -m app.migrations.

Only migrate an independent database copy. SQLite is the supported local database.
Existing watch rows and their IDs are preserved when replacing invalid uniqueness.
"""
from sqlalchemy import inspect, text
from .database import engine, Base
from . import models  # noqa


def migrate():
    if engine.dialect.name != 'sqlite':
        raise RuntimeError('This migration runner supports SQLite. Supply reviewed database-specific migrations before using another database.')
    Base.metadata.create_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql("BEGIN IMMEDIATE")
        c.execute(text('CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)'))
        constraints = inspect(c).get_unique_constraints('watch_progress')
        indexes = inspect(c).get_indexes('watch_progress')
        bad = any(x.get('unique', True) and x['column_names'] in [['user_id'], ['lecture_id']] for x in constraints + indexes)
        if bad:
            c.execute(text('CREATE TABLE watch_progress_new (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE, lecture_id INTEGER NOT NULL REFERENCES lectures(id) ON DELETE CASCADE, seconds FLOAT NOT NULL, updated_at DATETIME NOT NULL, UNIQUE(user_id, lecture_id))'))
            c.execute(text('INSERT INTO watch_progress_new SELECT id,user_id,lecture_id,seconds,updated_at FROM watch_progress'))
            c.execute(text('DROP TABLE watch_progress'))
            c.execute(text('ALTER TABLE watch_progress_new RENAME TO watch_progress'))
            c.execute(text('CREATE INDEX ix_watch_progress_user_id ON watch_progress(user_id)'))
            c.execute(text('CREATE INDEX ix_watch_progress_lecture_id ON watch_progress(lecture_id)'))
        c.execute(text('INSERT OR IGNORE INTO schema_versions(version) VALUES (1)'))
        cols={x['name'] for x in inspect(c).get_columns('doubts')}
        for name,definition in [('due_date','VARCHAR(10)'),('priority',"VARCHAR(12) NOT NULL DEFAULT 'normal'"),('history',"JSON NOT NULL DEFAULT '[]'")]:
            if name not in cols:
                c.execute(text(f'ALTER TABLE doubts ADD COLUMN {name} {definition}'))
        c.execute(text('INSERT OR IGNORE INTO schema_versions(version) VALUES (2)'))
        if 'reason' not in {x['name'] for x in inspect(c).get_columns('study_tasks')}:
            c.execute(text("ALTER TABLE study_tasks ADD COLUMN reason VARCHAR(500) NOT NULL DEFAULT ''"))
        c.execute(text('INSERT OR IGNORE INTO schema_versions(version) VALUES (3)'))
        if 'resume_seconds' not in {x['name'] for x in inspect(c).get_columns('watch_progress')}:
            c.execute(text('ALTER TABLE watch_progress ADD COLUMN resume_seconds FLOAT NOT NULL DEFAULT 0'))
            c.execute(text('UPDATE watch_progress SET resume_seconds=seconds'))
        c.execute(text('INSERT OR IGNORE INTO schema_versions(version) VALUES (4)'))
        c.execute(text("UPDATE revision_sessions SET status='superseded' WHERE status='active' AND id NOT IN (SELECT MIN(id) FROM revision_sessions WHERE status='active' GROUP BY user_id)"))
        c.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_active_revision_user ON revision_sessions(user_id) WHERE status='active'"))
        c.execute(text('INSERT OR IGNORE INTO schema_versions(version) VALUES (5)'))


if __name__ == '__main__':
    migrate()
    print('ORAYA schema versions 1–5 applied.')
