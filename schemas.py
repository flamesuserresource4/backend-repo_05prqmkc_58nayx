"""
Database Schemas for Study Assistant

Each Pydantic model represents a collection in MongoDB. The collection
name equals the lowercase class name.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Deck(BaseModel):
    name: str = Field(..., description="Deck name")
    description: Optional[str] = Field(None, description="What this deck covers")

class Card(BaseModel):
    deck_id: str = Field(..., description="Parent deck id (stringified ObjectId)")
    front: str = Field(..., description="Question / prompt")
    back: str = Field(..., description="Answer / explanation")
    # Spaced repetition metadata (SM-2 simplified)
    ease_factor: float = Field(2.5, description="Ease factor")
    interval: int = Field(0, description="Interval in days")
    repetitions: int = Field(0, description="Successful repetition count")
    next_review: Optional[datetime] = Field(None, description="Next review timestamp (UTC)")
    last_reviewed: Optional[datetime] = Field(None, description="Last reviewed timestamp (UTC)")

class StudySession(BaseModel):
    deck_id: str
    reviewed: int = 0
    correct: int = 0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
