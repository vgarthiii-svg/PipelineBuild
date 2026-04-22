"""Infer types and behavior profiles for prospects that came from the Pipeline Book import.

For each prospect linked to a `pipeline_book` relationship:
  1. If prospect.type is blank, run type_inference.infer_type(name=...) to set it.
  2. If prospect.type is in TYPE_BEHAVIOR_MAP and no BehaviorProfile exists, create one.
Types already set on prospects (from HubSpot) are respected, not overwritten.
"""
import os
import sys
from datetime import datetime
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models import Prospect, Relationship, BehaviorProfile
from app.routers.behavior import TYPE_BEHAVIOR_MAP
from app.services import type_inference


def run():
    db = SessionLocal()
    try:
        imported_ids = {
            r.prospect_id
            for r in db.query(Relationship.prospect_id)
            .filter(Relationship.source == "pipeline_book")
            .distinct()
            .all()
        }
        prospects = db.query(Prospect).filter(Prospect.id.in_(imported_ids)).all()

        types_set = 0
        types_already = 0
        type_dist = Counter()

        for p in prospects:
            if not p.type:
                inferred = type_inference.infer_type(
                    name=p.name, description=p.description or "", domain=p.domain or ""
                )
                if inferred:
                    p.type = inferred
                    types_set += 1
            else:
                types_already += 1
            type_dist[p.type or "<none>"] += 1

        db.flush()

        profiles_created = 0
        profiles_skipped_existing = 0
        profiles_skipped_unmapped_type = 0

        for p in prospects:
            existing = (
                db.query(BehaviorProfile)
                .filter(BehaviorProfile.prospect_id == p.id)
                .first()
            )
            if existing:
                profiles_skipped_existing += 1
                continue
            if not p.type or p.type not in TYPE_BEHAVIOR_MAP:
                profiles_skipped_unmapped_type += 1
                continue
            defaults = TYPE_BEHAVIOR_MAP[p.type]
            db.add(
                BehaviorProfile(
                    prospect_id=p.id,
                    assessed_by="heuristic_bulk_infer",
                    assessed_at=datetime.utcnow(),
                    partnership_history=(
                        f"Auto-inferred from type: {p.type}. Edit via Behavior tab for accuracy."
                    ),
                    **defaults,
                )
            )
            profiles_created += 1

        db.commit()

        print("=== Type inference ===")
        print(f"  types_set (were blank): {types_set}")
        print(f"  types_already_set:      {types_already}")
        print("  type distribution after:")
        for t, n in sorted(type_dist.items(), key=lambda x: -x[1]):
            in_map = " (in map)" if t in TYPE_BEHAVIOR_MAP else ""
            print(f"    {n:>3}  {t}{in_map}")
        print()
        print("=== Behavior profiles ===")
        print(f"  created:                   {profiles_created}")
        print(f"  skipped (already had one): {profiles_skipped_existing}")
        print(f"  skipped (unmapped type):   {profiles_skipped_unmapped_type}")
        print(f"  total imported prospects:  {len(prospects)}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
