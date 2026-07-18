"""SQLAlchemy models matching the existing Symfony database schema (PostgreSQL, v2)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    """User entity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str] = mapped_column(String(180), unique=True)
    pseudo: Mapped[str] = mapped_column(String(24), unique=True)
    roles: Mapped[list] = mapped_column(JSON)
    password: Mapped[str | None] = mapped_column(String(255))
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    google_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    auth_provider: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime)
    cgv_accepted_at: Mapped[datetime | None] = mapped_column(DateTime)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255))
    subscription_status: Mapped[str | None] = mapped_column(String(20))
    subscription_end_date: Mapped[datetime | None] = mapped_column(DateTime)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)
    launch_promo_used: Mapped[bool] = mapped_column(Boolean, default=False)

    # Relationships
    submissions: Mapped[list["Submission"]] = relationship(back_populates="user")
    progressions: Mapped[list["Progression"]] = relationship(back_populates="user")


class Grid(Base):
    """Grid entity."""

    __tablename__ = "grids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_grid_id: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[str | None] = mapped_column(String(255), unique=True)
    grid_rows: Mapped[int | None] = mapped_column(Integer)
    grid_cols: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(DateTime)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime)
    scheduled_publish_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_revision: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[str] = mapped_column(String(10))

    # Relationships
    submissions: Mapped[list["Submission"]] = relationship(back_populates="grid")
    progressions: Mapped[list["Progression"]] = relationship(back_populates="grid")
    clues: Mapped[list["Clue"]] = relationship(back_populates="grid")


class Clue(Base):
    """Clue entity."""

    __tablename__ = "clues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    grid_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE")
    )
    position: Mapped[str | None] = mapped_column(String(10))

    # Relationships
    grid: Mapped["Grid | None"] = relationship(back_populates="clues")
    words: Mapped[list["Word"]] = relationship(back_populates="clue")


class Word(Base):
    """Word entity."""

    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    clue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("clues.id", ondelete="CASCADE")
    )
    display_order: Mapped[int | None] = mapped_column(SmallInteger)
    clue_text: Mapped[str | None] = mapped_column(Text)
    start_position: Mapped[str | None] = mapped_column(String(10))
    direction: Mapped[str | None] = mapped_column(String(10))
    answer_hash: Mapped[str | None] = mapped_column(Text)
    encrypted_answer: Mapped[str | None] = mapped_column(Text)
    alternate_answer_hash: Mapped[str | None] = mapped_column(Text)
    encrypted_alternate_answer: Mapped[str | None] = mapped_column(Text)
    doublette_cell_index: Mapped[int | None] = mapped_column(SmallInteger)
    is_long_clue: Mapped[bool] = mapped_column(Boolean, default=False)
    is_subscriber_clue: Mapped[bool] = mapped_column(Boolean, default=False)
    hyphen_positions: Mapped[dict | None] = mapped_column(JSON)
    is_theme_clue: Mapped[bool] = mapped_column(Boolean, default=False)
    clue_links: Mapped[dict | None] = mapped_column(JSON)

    # Relationships
    clue: Mapped["Clue | None"] = relationship(back_populates="words")


class Submission(Base):
    """Submission entity."""

    __tablename__ = "submission"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    grid_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE")
    )
    correct_cells: Mapped[int] = mapped_column(Integer)
    base_score: Mapped[float]
    time_bonus: Mapped[float]
    joker_penalty: Mapped[float]
    final_score: Mapped[float]
    completion_time_seconds: Mapped[int] = mapped_column(Integer)
    words_found: Mapped[int] = mapped_column(Integer)
    total_words: Mapped[int] = mapped_column(Integer)
    joker_used: Mapped[bool] = mapped_column(Boolean, default=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="submissions")
    grid: Mapped["Grid"] = relationship(back_populates="submissions")


class Progression(Base):
    """Progression entity."""

    __tablename__ = "progression"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    grid_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE")
    )
    cells: Mapped[dict] = mapped_column(JSON)
    cell_validations: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    last_saved_at: Mapped[datetime] = mapped_column(DateTime)
    joker_used: Mapped[bool] = mapped_column(Boolean, default=False)
    joker_used_at: Mapped[datetime | None] = mapped_column(DateTime)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="progressions")
    grid: Mapped["Grid"] = relationship(back_populates="progressions")


class DuelMatch(Base):
    """Duel match entity (resolved pairing of two duel submissions)."""

    __tablename__ = "duel_match"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    grid_id: Mapped[int] = mapped_column(Integer, ForeignKey("grids.id"))
    submission1_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("duel_submission.id")
    )
    submission2_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("duel_submission.id")
    )
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    winner_pseudo: Mapped[str | None] = mapped_column(String(255))
    outcome: Mapped[str] = mapped_column(String(20))  # submission1 | submission2 | draw
    player1_elo_change: Mapped[int] = mapped_column(Integer)
    player2_elo_change: Mapped[int] = mapped_column(Integer)
    resolved_at: Mapped[datetime] = mapped_column(DateTime)


class DuelSubmission(Base):
    """Duel submission entity (one player's solve of a duel grid)."""

    __tablename__ = "duel_submission"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    grid_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE")
    )
    answers: Mapped[dict | None] = mapped_column(JSON)
    words_found: Mapped[int | None] = mapped_column(Integer)
    total_words: Mapped[int | None] = mapped_column(Integer)
    completion_time: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(
        String(20)
    )  # in_progress | submitted | matched | expired
    duel_match_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("duel_match.id")
    )
    user_pseudo: Mapped[str] = mapped_column(String(255))


class EloRating(Base):
    """Elo rating entity (one row per user having played duels)."""

    __tablename__ = "elo_rating"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    rating: Mapped[int] = mapped_column(Integer, default=1200)
    duels_played: Mapped[int] = mapped_column(Integer, default=0)
    duels_won: Mapped[int] = mapped_column(Integer, default=0)
    duels_lost: Mapped[int] = mapped_column(Integer, default=0)


class StripeEventLog(Base):
    """Stripe webhook event log (idempotency journal)."""

    __tablename__ = "stripe_event_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    stripe_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    processed_at: Mapped[datetime] = mapped_column(DateTime)
