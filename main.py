import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Deck, Card, StudySession

app = FastAPI(title="Study Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Helpers
class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return str(v)
        if isinstance(v, str):
            try:
                ObjectId(v)
                return v
            except Exception:
                raise ValueError("Invalid ObjectId string")
        raise ValueError("Invalid id")


class CardReview(BaseModel):
    card_id: str
    quality: int  # 0-5 (SM-2 quality score)


@app.get("/")
def root():
    return {"message": "Study Assistant Backend Running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Connected & Working"
            response["database_url"] = "✅ Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            response["collections"] = db.list_collection_names()[:10]
        else:
            response["database"] = "❌ Not Available"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# Deck endpoints
@app.post("/api/decks")
def create_deck(deck: Deck):
    deck_id = create_document("deck", deck)
    return {"id": deck_id}


@app.get("/api/decks")
def list_decks():
    items = get_documents("deck")
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items


# Card endpoints
@app.post("/api/cards")
def create_card(card: Card):
    # validate deck exists
    if db["deck"].count_documents({"_id": ObjectId(card.deck_id)}) == 0:
        raise HTTPException(status_code=404, detail="Deck not found")
    card_id = create_document("card", card)
    return {"id": card_id}


@app.get("/api/cards")
def list_cards(deck_id: Optional[str] = None, due_only: bool = False):
    q = {}
    if deck_id:
        q["deck_id"] = deck_id
    items = get_documents("card", q)
    now = datetime.now(timezone.utc)
    result = []
    for it in items:
        it["id"] = str(it.pop("_id"))
        if due_only:
            next_review = it.get("next_review")
            if next_review is None or next_review <= now:
                result.append(it)
        else:
            result.append(it)
    return result


# Review logic (SM-2 simplified)
@app.post("/api/review")
def review_card(payload: CardReview):
    doc = db["card"].find_one({"_id": ObjectId(payload.card_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Card not found")

    quality = max(0, min(5, payload.quality))
    ease = float(doc.get("ease_factor", 2.5))
    reps = int(doc.get("repetitions", 0))
    interval = int(doc.get("interval", 0))

    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = int(round(interval * ease)) or 1
        ease = ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        ease = max(1.3, ease)
        reps += 1

    next_review = datetime.now(timezone.utc) + timedelta(days=interval)

    db["card"].update_one(
        {"_id": ObjectId(payload.card_id)},
        {"$set": {
            "ease_factor": ease,
            "repetitions": reps,
            "interval": interval,
            "last_reviewed": datetime.now(timezone.utc),
            "next_review": next_review
        }}
    )
    return {
        "id": payload.card_id,
        "ease_factor": ease,
        "repetitions": reps,
        "interval": interval,
        "next_review": next_review
    }


# Study sessions (basic analytics)
@app.post("/api/sessions")
def start_session(session: StudySession):
    session_id = create_document("studysession", session)
    return {"id": session_id}


@app.get("/api/sessions")
def list_sessions(deck_id: Optional[str] = None):
    q = {"deck_id": deck_id} if deck_id else {}
    items = get_documents("studysession", q)
    for it in items:
        it["id"] = str(it.pop("_id"))
    return items


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
