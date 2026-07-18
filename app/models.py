"""SQLAlchemy models matching the existing Symfony database schema (PostgreSQL, v2)."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """User entity."""

    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String(180), unique=True, nullable=False)
    pseudo = Column(String(24), unique=True, nullable=False)
    roles = Column(JSON, nullable=False)
    password = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    google_id = Column(String(255), unique=True, nullable=True)
    auth_provider = Column(String(20), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    accepted_terms_at = Column(DateTime, nullable=True)
    cgv_accepted_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_subscription_id = Column(String(255), nullable=True)
    subscription_status = Column(String(20), nullable=True)
    subscription_end_date = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    launch_promo_used = Column(Boolean, default=False, nullable=False)

    # Relationships
    submissions = relationship("Submission", back_populates="user")
    progressions = relationship("Progression", back_populates="user")


class Grid(Base):
    """Grid entity."""

    __tablename__ = "grids"

    id = Column(Integer, primary_key=True)
    parent_grid_id = Column(Integer, nullable=True)
    version = Column(String(255), unique=True, nullable=True)
    grid_rows = Column(Integer, nullable=True)
    grid_cols = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=True)
    published_at = Column(DateTime, nullable=True)
    activated_at = Column(DateTime, nullable=True)
    scheduled_publish_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    is_archived = Column(Boolean, default=False, nullable=False)
    is_revision = Column(Boolean, default=False, nullable=False)
    type = Column(String(10), nullable=False)

    # Relationships
    submissions = relationship("Submission", back_populates="grid")
    progressions = relationship("Progression", back_populates="grid")
    clues = relationship("Clue", back_populates="grid")


class Clue(Base):
    """Clue entity."""

    __tablename__ = "clues"

    id = Column(Integer, primary_key=True)
    grid_id = Column(Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=True)
    position = Column(String(10), nullable=True)

    # Relationships
    grid = relationship("Grid", back_populates="clues")
    words = relationship("Word", back_populates="clue")


class Word(Base):
    """Word entity."""

    __tablename__ = "words"

    id = Column(Integer, primary_key=True)
    clue_id = Column(Integer, ForeignKey("clues.id", ondelete="CASCADE"), nullable=True)
    display_order = Column(SmallInteger, nullable=True)
    clue_text = Column(Text, nullable=True)
    start_position = Column(String(10), nullable=True)
    direction = Column(String(10), nullable=True)
    answer_hash = Column(Text, nullable=True)
    encrypted_answer = Column(Text, nullable=True)
    alternate_answer_hash = Column(Text, nullable=True)
    encrypted_alternate_answer = Column(Text, nullable=True)
    doublette_cell_index = Column(SmallInteger, nullable=True)
    is_long_clue = Column(Boolean, default=False, nullable=False)
    is_subscriber_clue = Column(Boolean, default=False, nullable=False)
    hyphen_positions = Column(JSON, nullable=True)
    is_theme_clue = Column(Boolean, default=False, nullable=False)
    clue_links = Column(JSON, nullable=True)

    # Relationships
    clue = relationship("Clue", back_populates="words")


class Submission(Base):
    """Submission entity."""

    __tablename__ = "submission"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    grid_id = Column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False
    )
    correct_cells = Column(Integer, nullable=False)
    base_score = Column(Float, nullable=False)
    time_bonus = Column(Float, nullable=False)
    joker_penalty = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    completion_time_seconds = Column(Integer, nullable=False)
    words_found = Column(Integer, nullable=False)
    total_words = Column(Integer, nullable=False)
    joker_used = Column(Boolean, default=False, nullable=False)
    submitted_at = Column(DateTime, nullable=False)

    # Relationships
    user = relationship("User", back_populates="submissions")
    grid = relationship("Grid", back_populates="submissions")


class Progression(Base):
    """Progression entity."""

    __tablename__ = "progression"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    grid_id = Column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False
    )
    cells = Column(JSON, nullable=False)
    cell_validations = Column(JSON, nullable=True)
    started_at = Column(DateTime, nullable=False)
    last_saved_at = Column(DateTime, nullable=False)
    joker_used = Column(Boolean, default=False, nullable=False)
    joker_used_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="progressions")
    grid = relationship("Grid", back_populates="progressions")


class DuelMatch(Base):
    """Duel match entity (resolved pairing of two duel submissions)."""

    __tablename__ = "duel_match"

    id = Column(UUID(as_uuid=True), primary_key=True)
    grid_id = Column(Integer, ForeignKey("grids.id"), nullable=False)
    submission1_id = Column(
        UUID(as_uuid=True), ForeignKey("duel_submission.id"), nullable=False
    )
    submission2_id = Column(
        UUID(as_uuid=True), ForeignKey("duel_submission.id"), nullable=False
    )
    winner_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    winner_pseudo = Column(String(255), nullable=True)
    outcome = Column(String(20), nullable=False)  # submission1 | submission2 | draw
    player1_elo_change = Column(Integer, nullable=False)
    player2_elo_change = Column(Integer, nullable=False)
    resolved_at = Column(DateTime, nullable=False)


class DuelSubmission(Base):
    """Duel submission entity (one player's solve of a duel grid)."""

    __tablename__ = "duel_submission"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    grid_id = Column(
        Integer, ForeignKey("grids.id", ondelete="CASCADE"), nullable=False
    )
    answers = Column(JSON, nullable=True)
    words_found = Column(Integer, nullable=True)
    total_words = Column(Integer, nullable=True)
    completion_time = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    status = Column(
        String(20), nullable=False
    )  # in_progress | submitted | matched | expired
    duel_match_id = Column(
        UUID(as_uuid=True), ForeignKey("duel_match.id"), nullable=True
    )
    user_pseudo = Column(String(255), nullable=False)


class EloRating(Base):
    """Elo rating entity (one row per user having played duels)."""

    __tablename__ = "elo_rating"

    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    rating = Column(Integer, default=1200, nullable=False)
    duels_played = Column(Integer, default=0, nullable=False)
    duels_won = Column(Integer, default=0, nullable=False)
    duels_lost = Column(Integer, default=0, nullable=False)


class StripeEventLog(Base):
    """Stripe webhook event log (idempotency journal)."""

    __tablename__ = "stripe_event_log"

    id = Column(UUID(as_uuid=True), primary_key=True)
    stripe_event_id = Column(String(255), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    processed_at = Column(DateTime, nullable=False)
