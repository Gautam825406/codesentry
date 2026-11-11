"""Initial schema — mirrors database/models.py (created via Base.metadata)."""
revision = "0001"
down_revision = None

def upgrade():
    from database.models import Base
    from database.session import engine
    Base.metadata.create_all(bind=engine)

def downgrade():
    from database.models import Base
    from database.session import engine
    Base.metadata.drop_all(bind=engine)
