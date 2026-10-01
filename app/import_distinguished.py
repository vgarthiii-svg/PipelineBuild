"""
Loader: set up Distinguished Fine Art & Collectibles as the main account and
load its scored target-business ecosystem into the pipeline database.

Run from the repo root:

    python -m app.import_distinguished

Idempotent and safe against an existing database (adds the client alongside
any others). After running, pick "Distinguished Fine Art & Collectibles" in
the dashboard client dropdown to use it as the scoring lens.
"""

from app.database import Base, engine, SessionLocal
from app.importers import import_distinguished


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = import_distinguished(db)
        print(f"[import_distinguished] Done. {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
