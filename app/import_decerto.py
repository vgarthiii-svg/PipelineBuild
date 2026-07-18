"""
One-time loader: put the Decerto client, criteria, and 52 scored carrier
accounts into the pipeline database so they show up in the dashboard.

Run from the repo root:

    python -m app.import_decerto

Safe to run against an existing (already-seeded) database - it adds Decerto
alongside Tivly and is idempotent (re-running updates in place).
"""

from app.database import Base, engine, SessionLocal
from app.importers import import_decerto


def main():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        result = import_decerto(db)
        print(f"[import_decerto] Done. {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
