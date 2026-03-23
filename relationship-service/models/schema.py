"""
SQLAlchemy ORM models for the Relationship Service.

RelationshipScore is owned by this service.
User and Message are defined in the shared DB — declared here as read-only
references so SQLAlchemy can join across them without managing their lifecycle.
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Float,
    ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Read-only reference to the shared users table."""

    __tablename__ = "users"

    id = Column(String(16), primary_key=True)
    telegram_id = Column(BigInteger, nullable=True)
    first_name = Column(String(128), nullable=True)
    onboarding_complete = Column(Boolean, default=False)
    last_active_at = Column(DateTime(timezone=True))

    relationship_score = relationship(
        "RelationshipScore", back_populates="user", uselist=False
    )


class Message(Base):
    """Read-only reference to the shared messages table."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(16), ForeignKey("users.id"), index=True)
    role = Column(String(16))
    content = Column(Text)
    is_proactive = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RelationshipScore(Base):
    """Owned by this service — tracks affinity score per user."""

    __tablename__ = "relationship_scores"

    user_id = Column(String(16), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    score = Column(Float, default=0.10)
    total_interactions = Column(Integer, default=0)
    positive_interactions = Column(Integer, default=0)
    negative_interactions = Column(Integer, default=0)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_decay_at = Column(DateTime(timezone=True), nullable=True)
    last_scored_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="relationship_score")


class ScoreHistory(Base):
    """Owned by this service — records each scoring event per user."""

    __tablename__ = "score_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(16), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    delta = Column(Float, nullable=False)
    new_score = Column(Float, nullable=False)
    sentiment = Column(String(16), nullable=True)
    intensity = Column(String(16), nullable=True)
    reasoning = Column(Text, nullable=True)
    reason = Column(String(32), nullable=False)  # session_scored | inactivity_decay | manual_update
    scored_at = Column(DateTime(timezone=True), server_default=func.now())
