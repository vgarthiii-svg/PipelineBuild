import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Store data (database + uploaded images) in a stable home-directory folder so
# it survives re-downloading/updating the app. Override with CARD_DATA_DIR.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("CARD_DATA_DIR") or os.path.join(
    os.path.expanduser("~"), "CardTrackerData"
)
IMAGE_DIR = os.path.join(DATA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "cardtracker.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_schema():
    """
    Lightweight forward-only migration for SQLite: create any new tables and
    add any columns that exist on the models but not yet in an existing table.
    Keeps older databases (created before sales/checklist fields were added)
    working without wiping data.
    """
    from sqlalchemy import inspect, text

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue
        have = {c["name"] for c in inspector.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            col_type = col.type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
            default = getattr(col.default, "arg", None)
            if default is not None and not callable(default):
                if isinstance(default, bool):
                    ddl += f" DEFAULT {1 if default else 0}"
                elif isinstance(default, str):
                    ddl += f" DEFAULT '{default}'"
                else:
                    ddl += f" DEFAULT {default}"
            with engine.begin() as conn:
                conn.execute(text(ddl))
