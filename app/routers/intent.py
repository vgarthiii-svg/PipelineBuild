import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models import IntentSignal, Prospect, PipelineEntry
from app.schemas import IntentSignalCreate, IntentSignalOut
from app.scoring import calculate_intent_multiplier

router = APIRouter(prefix="/api/intent", tags=["intent"])


@router.get("/{prospect_id}", response_model=List[IntentSignalOut])
def list_intent_signals(prospect_id: int, db: Session = Depends(get_db)):
    return (
        db.query(IntentSignal)
        .filter(IntentSignal.prospect_id == prospect_id)
        .order_by(IntentSignal.created_at.desc())
        .all()
    )


@router.post("/{prospect_id}", response_model=IntentSignalOut)
def add_intent_signal(prospect_id: int, data: IntentSignalCreate, db: Session = Depends(get_db)):
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    signal = IntentSignal(prospect_id=prospect_id, **data.dict())
    db.add(signal)
    db.commit()
    db.refresh(signal)

    # Recalculate intent multiplier for pipeline entries
    _update_intent_multiplier(prospect_id, db)

    return signal


@router.delete("/{signal_id}")
def delete_intent_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = db.query(IntentSignal).filter(IntentSignal.id == signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    prospect_id = signal.prospect_id
    db.delete(signal)
    db.commit()

    # Recalculate
    _update_intent_multiplier(prospect_id, db)

    return {"status": "deleted"}


@router.post("/{prospect_id}/research")
def research_intent(prospect_id: int, force: bool = False, db: Session = Depends(get_db)):
    """Research intent signals via Claude API. Requires approval unless force=True."""
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospect not found")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail="Claude API key not configured")

    # Cost gate: queue for approval unless forced
    if not force:
        from app.routers.notifications import create_pending_action
        action = create_pending_action(
            db,
            action_type="research_intent",
            description=f"Research intent signals for {prospect.name} using Claude AI. Will search for hiring, expansion, funding, and partnership signals.",
            params={"prospect_id": prospect_id},
            estimated_cost="$0.02-0.04",
        )
        return {
            "status": "pending_approval",
            "action_id": action.id,
            "message": f"Intent research for {prospect.name} requires your approval. Check the notification bar.",
        }

    return _do_research_intent(prospect_id, db)


def _do_research_intent(prospect_id, db):
    """Actually execute the intent research via Claude API."""
    prospect = db.query(Prospect).filter(Prospect.id == prospect_id).first()
    if not prospect:
        return {"error": "Prospect not found"}

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "API key not set"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        resp = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1500,
            system="""You are a B2B sales intelligence researcher for the insurance industry.
Research the company and identify current intent signals. Return ONLY a JSON array.
Each item: {"signal_type": "hiring|expansion|funding|partnership_announcement|strategic_statement|product_launch", "signal_detail": "1-2 sentences", "signal_date": "YYYY-MM-DD or null", "urgency": "high|moderate|low", "source_url": "url or null"}
If no signals found, return []. Do not fabricate signals.""",
            messages=[{
                "role": "user",
                "content": f"Research intent signals for {prospect.name} ({prospect.website or prospect.domain or ''}). Industry: {prospect.industry_vertical or prospect.type or 'insurance'}."
            }],
        )

        text = resp.content[0].text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        signals_data = json.loads(text.strip())
        created = []

        for s in signals_data:
            sig = IntentSignal(
                prospect_id=prospect_id,
                signal_type=s.get("signal_type", "strategic_statement"),
                signal_detail=s.get("signal_detail", ""),
                signal_date=s.get("signal_date"),
                urgency=s.get("urgency", "moderate"),
                source_url=s.get("source_url"),
            )
            db.add(sig)
            db.flush()
            created.append(sig)

        db.commit()
        _update_intent_multiplier(prospect_id, db)

        return {"signals_found": len(created), "prospect": prospect.name}

    except Exception as e:
        return {"error": f"Research failed: {str(e)}"}


def _update_intent_multiplier(prospect_id: int, db: Session):
    """Recalculate intent multiplier for all pipeline entries with this prospect."""
    signals = db.query(IntentSignal).filter(IntentSignal.prospect_id == prospect_id).all()
    multiplier = calculate_intent_multiplier(signals)

    entries = db.query(PipelineEntry).filter(PipelineEntry.prospect_id == prospect_id).all()
    for entry in entries:
        entry.intent_multiplier = multiplier

    db.commit()
