"""pgvector migration (Postgres only).

Adds the pgvector extension and a `vector(128)` column alongside the JSON
embedding column. The v1 application reads/writes the JSON column (which
works on SQLite and Postgres alike); the vector column is the documented
scale path — a future release can switch retrieval to it without a data
migration. On SQLite this migration is a no-op (guarded by dialect check).
"""
revision = "0002"
down_revision = "0001"

def upgrade():
    from sqlalchemy import text
    from database.session import engine
    if engine.dialect.name != "postgresql":
        print("0002 pgvector: skipped (not Postgres)")
        return
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text("ALTER TABLE symbols ADD COLUMN IF NOT EXISTS embedding_vector vector(128)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_symbols_embedding_vector "
                          "ON symbols USING ivfflat (embedding_vector vector_cosine_ops)"))

def downgrade():
    from sqlalchemy import text
    from database.session import engine
    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX IF EXISTS ix_symbols_embedding_vector"))
        conn.execute(text("ALTER TABLE symbols DROP COLUMN IF EXISTS embedding_vector"))
