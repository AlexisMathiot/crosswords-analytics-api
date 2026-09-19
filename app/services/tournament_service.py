"""Tournament statistics service using Pandas for high performance.

Data model reminders (Symfony API v2, see the entity docblocks there):

- ``tournament_participation`` is the ENTRY of a user into an edition, created
  at the first competitive start. It survives account deletion (``user_id``
  SET NULL, ``user_pseudo`` copied). The Symfony side never counts on it (AD-21):
  ``bracket_size`` and ranks are computed on SUBMISSIONS — we expose both views.
- ``tournament_submission.competitive`` separates competition solves from
  out-of-competition replays on unlocked grids. Competition readers must filter
  ``competitive = true``.
- Access to an edition is granted either by a premium subscription or by a
  ``granted`` ticket. A ``to_refund`` ticket is a payment anomaly (double
  purchase, ...), never an entry right.
- Rounds: ``position`` 1 = qualifying (« 1er tour » on the site), 2..7 = rounds 1..6
  (« 2e tour »…). The calendar always
  holds 7 windows; only ``log2(bracket_size)`` rounds are actually played.
"""

import math
import uuid
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    Grid,
    Tournament,
    TournamentBadge,
    TournamentParticipation,
    TournamentRound,
    TournamentSlot,
    TournamentSubmission,
    TournamentTicket,
    User,
)
from app.services.statistics_service import extract_grid_number

TOURNAMENT_STATUSES = ("draft", "published", "cancelled")
TICKET_STATUSES = ("granted", "to_refund")
SUBMISSION_STATUSES = ("in_progress", "submitted", "cancelled")
SLOT_OUTCOMES = ("victoire", "elimine", "walkover", "exemption")
VACANCY_REASONS = ("adversaire_retire", "double_absence")
BADGE_TYPES = ("participation", "semi_finalist", "finalist", "winner")

QUALIFYING_POSITION = 1
FULL_CALENDAR_SIZE = 7

# Mirror of User::ROLE_PREMIUM_GRANT in the Symfony API
ROLE_PREMIUM_GRANT = "ROLE_PREMIUM_GRANT"

ENTRANTS_NOTE = (
    "Répartition des inscrits par mode d'accès : « ticket » = ticket granted sur "
    "l'édition ; « premium » = abonnement actif AUJOURD'HUI (ou rôle "
    "ROLE_PREMIUM_GRANT) sans ticket ; « other » = ni l'un ni l'autre "
    "aujourd'hui (premium expiré depuis l'inscription, ou compte supprimé). "
    "Le statut premium n'est pas historisé : la répartition est une estimation."
)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested, no database)
# ---------------------------------------------------------------------------


def is_premium_now(
    subscription_status: str | None,
    subscription_end_date: datetime | None,
    roles: list | None,
    now: datetime | None = None,
) -> bool:
    """Mirror of User::hasPremiumAccess() in the Symfony API.

    Premium = status active/past_due, or canceled with an end date still in
    the future, or the manual ROLE_PREMIUM_GRANT role.
    """
    if roles and ROLE_PREMIUM_GRANT in roles:
        return True
    if subscription_status in ("active", "past_due"):
        return True
    if subscription_status == "canceled" and subscription_end_date is not None:
        now = now or datetime.now()
        end = subscription_end_date
        if end.tzinfo is not None:
            end = end.astimezone(timezone.utc).replace(tzinfo=None)
        if now.tzinfo is not None:
            now = now.astimezone(timezone.utc).replace(tzinfo=None)
        return end > now
    return False


def classify_entrant(
    has_ticket: bool,
    subscription_status: str | None,
    subscription_end_date: datetime | None,
    roles: list | None,
    now: datetime | None = None,
) -> str:
    """Classify how an entrant got into an edition: 'ticket', 'premium' or 'other'.

    A granted ticket is a hard fact (payment), so it wins over the premium
    status which is only known as of today.
    """
    if has_ticket:
        return "ticket"
    if is_premium_now(subscription_status, subscription_end_date, roles, now):
        return "premium"
    return "other"


def played_rounds_count(bracket_size: int | None) -> int | None:
    """Number of bracket rounds actually played for a bracket size (16 → 4, 64 → 6)."""
    if not bracket_size or bracket_size < 2:
        return None
    return int(math.log2(bracket_size))


PRESUMED_BRACKET_SIZE = 64  # tableau présumé tant que la clôture des qualifs n'a rien figé (site : issue #246)
BONUS_LABEL = "Grille bonus"  # fenêtre au-delà du tableau figé (site : issue #237)


def _numbered_round_label(round_number: int) -> str:
    """Site nomenclature: qualifying is the « 1er tour », so bracket round N is « {N+1}e tour »."""
    return f"{round_number + 1}e tour"


def _bracket_round_label(bracket_size: int, round_number: int) -> str:
    """Same rule as the site (TournamentRoundLabeler): named by players remaining."""
    players = bracket_size // (2 ** (round_number - 1))
    if players == 2:
        return "La Grande Finale"
    if players == 4:
        return "Demi-finales"
    if players == 8:
        return "Quarts de finale"
    if players == 16:
        return "Huitièmes de finale"
    return _numbered_round_label(round_number)


def label_round(position: int, bracket_size: int | None) -> dict:
    """Describe a calendar window (position 1..7) for a given bracket size.

    Labels follow the site nomenclature (crosswords-api ``TournamentRoundLabeler``):
    the qualifying window is the « 1er tour », bracket rounds are named by the
    number of players remaining (« 2e tour », « 3e tour », « Huitièmes de finale »,
    « Quarts de finale », « Demi-finales », « La Grande Finale »). While the bracket
    size is unknown (qualifying still open) a bracket of 64 is presumed, as on the
    site; a window beyond a frozen bracket is the « Grille bonus ».

    Returns a dict with:
        - roundNumber: None for qualifying, else 1..6
        - label: human label, identical to the site
        - players: players entering this round (None for qualifying / unknown)
        - played: False when the window is beyond the rounds needed by the
          bracket size (calendar always holds 7 windows), or when the bracket
          size is unknown for a bracket window
    """
    if position == QUALIFYING_POSITION:
        return {
            "roundNumber": None,
            "label": "1er tour",
            "players": None,
            "played": True,
        }

    round_number = position - QUALIFYING_POSITION
    rounds_needed = played_rounds_count(bracket_size)

    if bracket_size is None or rounds_needed is None:
        return {
            "roundNumber": round_number,
            "label": _bracket_round_label(PRESUMED_BRACKET_SIZE, round_number),
            "players": None,
            "played": False,
        }

    if round_number > rounds_needed:
        return {
            "roundNumber": round_number,
            "label": BONUS_LABEL,
            "players": None,
            "played": False,
        }

    return {
        "roundNumber": round_number,
        "label": _bracket_round_label(bracket_size, round_number),
        "players": bracket_size // (2 ** (round_number - 1)),
        "played": True,
    }


def summarize_submissions(df: pd.DataFrame) -> dict:
    """Summarize a DataFrame of tournament submissions (competitive or not).

    Expects columns: status, completion_time, words_found, total_words.
    """
    summary: dict = {
        "total": int(len(df)),
        "byStatus": {status: 0 for status in SUBMISSION_STATUSES},
        "completionTime": None,
        "averageWordsFound": None,
        "averageCompletion": None,
        "fullGridRate": None,
    }
    if df.empty:
        return summary

    status_counts = df["status"].value_counts().to_dict()
    for status in SUBMISSION_STATUSES:
        summary["byStatus"][status] = int(status_counts.get(status, 0))

    submitted = df[df["status"] == "submitted"]
    times = submitted["completion_time"].dropna()
    if len(times) > 0:
        summary["completionTime"] = {
            "mean": float(round(times.mean(), 1)),
            "median": float(times.median()),
            "min": int(times.min()),
            "max": int(times.max()),
        }

    scored = submitted[
        submitted["words_found"].notna() & submitted["total_words"].notna()
    ]
    if len(scored) > 0:
        summary["averageWordsFound"] = float(round(scored["words_found"].mean(), 1))
        valid = scored[scored["total_words"] > 0]
        if len(valid) > 0:
            summary["averageCompletion"] = float(
                round((valid["words_found"] / valid["total_words"]).mean() * 100, 1)
            )
            full = (valid["words_found"] == valid["total_words"]).sum()
            summary["fullGridRate"] = float(round(full / len(valid) * 100, 1))

    return summary


def summarize_slots(df: pd.DataFrame) -> dict:
    """Summarize a DataFrame of bracket slots.

    Expects columns: participation_id, vacancy_reason, outcome.
    """
    summary: dict = {
        "total": int(len(df)),
        "occupied": 0,
        "vacant": 0,
        "vacancyReasons": {reason: 0 for reason in VACANCY_REASONS},
        "outcomes": {outcome: 0 for outcome in SLOT_OUTCOMES},
        "resolved": 0,
        "pending": 0,
    }
    if df.empty:
        return summary

    occupied = df["participation_id"].notna()
    summary["occupied"] = int(occupied.sum())
    summary["vacant"] = int((~occupied).sum())

    vacancy_counts = df["vacancy_reason"].dropna().value_counts().to_dict()
    for reason in VACANCY_REASONS:
        summary["vacancyReasons"][reason] = int(vacancy_counts.get(reason, 0))

    outcome_counts = df["outcome"].dropna().value_counts().to_dict()
    for outcome in SLOT_OUTCOMES:
        summary["outcomes"][outcome] = int(outcome_counts.get(outcome, 0))

    resolved = occupied & df["outcome"].notna()
    summary["resolved"] = int(resolved.sum())
    summary["pending"] = int((occupied & ~resolved).sum())

    return summary


def _to_iso(value) -> str | None:
    """Serialize a datetime / pandas Timestamp (or NaT / None) to ISO 8601."""
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        value = value.to_pydatetime()
    return value.isoformat()


# ---------------------------------------------------------------------------
# Database loaders
# ---------------------------------------------------------------------------


def _load_tournaments(db: Session) -> pd.DataFrame:
    query = db.query(
        Tournament.id,
        Tournament.name,
        Tournament.status,
        Tournament.start_at,
        Tournament.bracket_size,
        Tournament.qualifying_closed_at,
        Tournament.closed_at,
    )
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["id"] = df["id"].astype(str)
    return df


def _load_entrants(db: Session, tournament_id: uuid.UUID | None = None) -> pd.DataFrame:
    """Load participations joined to the user's current premium primitives."""
    query = db.query(
        TournamentParticipation.id,
        TournamentParticipation.tournament_id,
        TournamentParticipation.user_id,
        TournamentParticipation.user_pseudo,
        TournamentParticipation.entered_at,
        TournamentParticipation.qualifying_rank,
        User.subscription_status,
        User.subscription_end_date,
        User.roles,
    ).outerjoin(User, TournamentParticipation.user_id == User.id)
    if tournament_id is not None:
        query = query.filter(TournamentParticipation.tournament_id == tournament_id)
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["id"] = df["id"].astype(str)
        df["tournament_id"] = df["tournament_id"].astype(str)
        df["user_id"] = df["user_id"].map(lambda v: None if pd.isna(v) else str(v))
    return df


def _load_tickets(db: Session, tournament_id: uuid.UUID | None = None) -> pd.DataFrame:
    query = db.query(
        TournamentTicket.tournament_id,
        TournamentTicket.user_id,
        TournamentTicket.status,
        TournamentTicket.paid_at,
        TournamentTicket.created_at,
    )
    if tournament_id is not None:
        query = query.filter(TournamentTicket.tournament_id == tournament_id)
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["tournament_id"] = df["tournament_id"].astype(str)
        df["user_id"] = df["user_id"].astype(str)
    return df


def _load_submissions(
    db: Session, tournament_id: uuid.UUID | None = None
) -> pd.DataFrame:
    """Load submissions with their edition (through the participation)."""
    query = db.query(
        TournamentSubmission.grid_id,
        TournamentSubmission.user_id,
        TournamentSubmission.participation_id,
        TournamentSubmission.status,
        TournamentSubmission.competitive,
        TournamentSubmission.started_at,
        TournamentSubmission.submitted_at,
        TournamentSubmission.completion_time,
        TournamentSubmission.words_found,
        TournamentSubmission.total_words,
        TournamentParticipation.tournament_id,
    ).join(
        TournamentParticipation,
        TournamentSubmission.participation_id == TournamentParticipation.id,
    )
    if tournament_id is not None:
        query = query.filter(TournamentParticipation.tournament_id == tournament_id)
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["tournament_id"] = df["tournament_id"].astype(str)
        df["participation_id"] = df["participation_id"].astype(str)
        df["user_id"] = df["user_id"].map(lambda v: None if pd.isna(v) else str(v))
    return df


def _load_badges(db: Session, tournament_id: uuid.UUID | None = None) -> pd.DataFrame:
    query = db.query(
        TournamentBadge.tournament_id,
        TournamentBadge.user_id,
        TournamentBadge.type,
        TournamentBadge.awarded_at,
    )
    if tournament_id is not None:
        query = query.filter(TournamentBadge.tournament_id == tournament_id)
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["tournament_id"] = df["tournament_id"].astype(str)
        df["user_id"] = df["user_id"].astype(str)
    return df


def _load_rounds(db: Session, tournament_id: uuid.UUID) -> pd.DataFrame:
    query = (
        db.query(
            TournamentRound.id,
            TournamentRound.position,
            TournamentRound.grid_id,
            TournamentRound.opens_at,
            TournamentRound.closes_at,
            TournamentRound.opened_at,
            TournamentRound.closed_at,
            Grid.version,
        )
        .outerjoin(Grid, TournamentRound.grid_id == Grid.id)
        .filter(TournamentRound.tournament_id == tournament_id)
        .order_by(TournamentRound.position)
    )
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["id"] = df["id"].astype(str)
    return df


def _load_slots(db: Session, tournament_id: uuid.UUID) -> pd.DataFrame:
    query = (
        db.query(
            TournamentSlot.round_id,
            TournamentSlot.participation_id,
            TournamentSlot.position,
            TournamentSlot.vacancy_reason,
            TournamentSlot.outcome,
            TournamentSlot.resolved_at,
        )
        .join(TournamentRound, TournamentSlot.round_id == TournamentRound.id)
        .filter(TournamentRound.tournament_id == tournament_id)
    )
    df = pd.read_sql(query.statement, db.connection())
    if not df.empty:
        df["round_id"] = df["round_id"].astype(str)
        df["participation_id"] = df["participation_id"].map(
            lambda v: None if pd.isna(v) else str(v)
        )
    return df


# ---------------------------------------------------------------------------
# Shared computations
# ---------------------------------------------------------------------------


def _classify_entrants(
    df_entrants: pd.DataFrame, df_tickets: pd.DataFrame, now: datetime | None = None
) -> pd.DataFrame:
    """Add an ``access`` column ('ticket' | 'premium' | 'other') to entrants."""
    if df_entrants.empty:
        df_entrants["access"] = pd.Series(dtype=str)
        return df_entrants

    granted: set[tuple[str, str]] = set()
    if not df_tickets.empty:
        granted_rows = df_tickets[df_tickets["status"] == "granted"]
        granted = set(zip(granted_rows["tournament_id"], granted_rows["user_id"]))

    now = now or datetime.now()
    df_entrants = df_entrants.copy()
    df_entrants["access"] = [
        classify_entrant(
            (row.tournament_id, row.user_id) in granted if row.user_id else False,
            row.subscription_status,
            None if pd.isna(row.subscription_end_date) else row.subscription_end_date,
            row.roles,
            now,
        )
        for row in df_entrants.itertuples(index=False)
    ]
    return df_entrants


def _entrants_breakdown(df_entrants: pd.DataFrame) -> dict:
    """Build the entrants block from a classified entrants DataFrame."""
    breakdown = {
        "total": int(len(df_entrants)),
        "ticket": 0,
        "premium": 0,
        "other": 0,
        "deletedAccounts": 0,
        "qualified": 0,
    }
    if df_entrants.empty:
        return breakdown
    access_counts = df_entrants["access"].value_counts().to_dict()
    for key in ("ticket", "premium", "other"):
        breakdown[key] = int(access_counts.get(key, 0))
    breakdown["deletedAccounts"] = int(df_entrants["user_id"].isna().sum())
    breakdown["qualified"] = int(df_entrants["qualifying_rank"].notna().sum())
    return breakdown


def _tickets_breakdown(df_tickets: pd.DataFrame) -> dict:
    breakdown = {
        "total": int(len(df_tickets)),
        "granted": 0,
        "toRefund": 0,
        "anomalyRate": 0.0,
    }
    if df_tickets.empty:
        return breakdown
    counts = df_tickets["status"].value_counts().to_dict()
    breakdown["granted"] = int(counts.get("granted", 0))
    breakdown["toRefund"] = int(counts.get("to_refund", 0))
    breakdown["anomalyRate"] = float(
        round(breakdown["toRefund"] / len(df_tickets) * 100, 1)
    )
    return breakdown


def _badges_breakdown(df_badges: pd.DataFrame) -> dict:
    counts = df_badges["type"].value_counts().to_dict() if not df_badges.empty else {}
    return {badge_type: int(counts.get(badge_type, 0)) for badge_type in BADGE_TYPES}


def _monthly_timeline(
    series: dict[str, pd.Series],
) -> list[dict]:
    """Build a monthly timeline from named datetime Series (counts per month)."""
    parts = []
    for name, values in series.items():
        values = values.dropna()
        if len(values) == 0:
            continue
        counts = pd.to_datetime(values).dt.to_period("M").value_counts().sort_index()
        parts.append(counts.rename(name))

    if not parts:
        return []

    timeline = pd.concat(parts, axis=1).fillna(0).sort_index()
    for name in series:
        if name not in timeline.columns:
            timeline[name] = 0

    return [
        {"period": str(period), **{name: int(row[name]) for name in series}}
        for period, row in timeline.iterrows()
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_tournament_overview(db: Session) -> dict:
    """Get platform-wide tournament statistics, with one row per edition.

    Args:
        db: Database session

    Returns:
        dict: Edition counts, entrants, tickets, badges, monthly timeline and
            a per-edition summary (most recent first)
    """
    df_tournaments = _load_tournaments(db)
    df_entrants = _classify_entrants(_load_entrants(db), _load_tickets(db))
    df_tickets = _load_tickets(db)
    df_subs = _load_submissions(db)
    df_badges = _load_badges(db)

    status_counts = (
        df_tournaments["status"].value_counts().to_dict()
        if not df_tournaments.empty
        else {}
    )

    competitive = df_subs[df_subs["competitive"]] if not df_subs.empty else df_subs
    out_of_competition = (
        df_subs[~df_subs["competitive"]] if not df_subs.empty else df_subs
    )

    overview: dict = {
        "totalEditions": int(len(df_tournaments)),
        "editionsByStatus": {
            status: int(status_counts.get(status, 0)) for status in TOURNAMENT_STATUSES
        },
        "entrants": _entrants_breakdown(df_entrants),
        "uniqueEntrants": int(df_entrants["user_id"].dropna().nunique())
        if not df_entrants.empty
        else 0,
        "returningEntrants": 0,
        "tickets": _tickets_breakdown(df_tickets),
        "uniqueBuyers": 0,
        "competitiveSubmissions": summarize_submissions(competitive),
        "outOfCompetitionSubmissions": int(len(out_of_competition)),
        "badges": _badges_breakdown(df_badges),
        "timeline": [],
        "editions": [],
        "entrantsNote": ENTRANTS_NOTE,
    }

    if not df_entrants.empty:
        per_user = df_entrants.dropna(subset=["user_id"]).groupby("user_id").size()
        overview["returningEntrants"] = int((per_user >= 2).sum())

    if not df_tickets.empty:
        granted = df_tickets[df_tickets["status"] == "granted"]
        overview["uniqueBuyers"] = int(granted["user_id"].nunique())

    overview["timeline"] = _monthly_timeline(
        {
            "entrants": df_entrants["entered_at"]
            if not df_entrants.empty
            else pd.Series(dtype="datetime64[ns]"),
            "tickets": df_tickets[df_tickets["status"] == "granted"]["paid_at"]
            if not df_tickets.empty
            else pd.Series(dtype="datetime64[ns]"),
        }
    )

    overview["editions"] = _build_editions_summary(
        df_tournaments, df_entrants, df_tickets, competitive, df_badges
    )

    return overview


def _build_editions_summary(
    df_tournaments: pd.DataFrame,
    df_entrants: pd.DataFrame,
    df_tickets: pd.DataFrame,
    df_competitive: pd.DataFrame,
    df_badges: pd.DataFrame,
) -> list[dict]:
    """One summary row per edition, most recent first."""
    if df_tournaments.empty:
        return []

    winners: dict[str, str | None] = {}
    if not df_badges.empty and not df_entrants.empty:
        winner_badges = df_badges[df_badges["type"] == "winner"]
        pseudo_by_key = {
            (row.tournament_id, row.user_id): row.user_pseudo
            for row in df_entrants.dropna(subset=["user_id"]).itertuples(index=False)
        }
        for row in winner_badges.itertuples(index=False):
            winners[row.tournament_id] = pseudo_by_key.get(
                (row.tournament_id, row.user_id)
            )

    editions = []
    for t in df_tournaments.sort_values("start_at", ascending=False).itertuples(
        index=False
    ):
        entrants = (
            df_entrants[df_entrants["tournament_id"] == t.id]
            if not df_entrants.empty
            else df_entrants
        )
        tickets = (
            df_tickets[df_tickets["tournament_id"] == t.id]
            if not df_tickets.empty
            else df_tickets
        )
        competitive = (
            df_competitive[df_competitive["tournament_id"] == t.id]
            if not df_competitive.empty
            else df_competitive
        )
        submitted = (
            competitive[competitive["status"] == "submitted"]
            if not competitive.empty
            else competitive
        )
        editions.append(
            {
                "id": t.id,
                "name": t.name,
                "status": t.status,
                "startAt": _to_iso(t.start_at),
                "bracketSize": None if pd.isna(t.bracket_size) else int(t.bracket_size),
                "qualifyingClosedAt": _to_iso(t.qualifying_closed_at),
                "closedAt": _to_iso(t.closed_at),
                "entrants": _entrants_breakdown(entrants),
                "tickets": _tickets_breakdown(tickets),
                "competitiveSubmissions": int(len(submitted)),
                "winnerPseudo": winners.get(t.id),
            }
        )
    return editions


def get_tournament_detail(db: Session, tournament_id: uuid.UUID) -> dict:
    """Get detailed statistics for one tournament edition.

    Args:
        db: Database session
        tournament_id: Edition UUID

    Returns:
        dict: Edition info, entrants (with access mode), tickets (with purchase
            timeline), qualifying stats, per-round stats (submissions, slots,
            outcomes), out-of-competition activity and badges

    Raises:
        ValueError: If the edition does not exist
    """
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if tournament is None:
        raise ValueError(f"Tournament {tournament_id} not found")

    df_tickets = _load_tickets(db, tournament_id)
    df_entrants = _classify_entrants(_load_entrants(db, tournament_id), df_tickets)
    df_subs = _load_submissions(db, tournament_id)
    df_rounds = _load_rounds(db, tournament_id)
    df_slots = _load_slots(db, tournament_id)
    df_badges = _load_badges(db, tournament_id)

    competitive = df_subs[df_subs["competitive"]] if not df_subs.empty else df_subs
    out_of_competition = (
        df_subs[~df_subs["competitive"]] if not df_subs.empty else df_subs
    )

    detail: dict = {
        "id": str(tournament.id),
        "name": tournament.name,
        "status": tournament.status,
        "prize": tournament.prize,
        "startAt": _to_iso(tournament.start_at),
        "bracketSize": tournament.bracket_size,
        "roundsPlayed": played_rounds_count(tournament.bracket_size),
        "qualifyingClosedAt": _to_iso(tournament.qualifying_closed_at),
        "closedAt": _to_iso(tournament.closed_at),
        "entrants": _entrants_breakdown(df_entrants),
        "tickets": {
            **_tickets_breakdown(df_tickets),
            "purchaseTimeline": _build_purchase_timeline(df_tickets),
        },
        "entriesTimeline": _build_daily_timeline(
            df_entrants["entered_at"] if not df_entrants.empty else None, "entrants"
        ),
        "competitiveSubmissions": summarize_submissions(competitive),
        "outOfCompetition": {
            "submissions": summarize_submissions(out_of_competition),
            "uniquePlayers": int(out_of_competition["user_id"].dropna().nunique())
            if not out_of_competition.empty
            else 0,
        },
        "rounds": _build_rounds(
            df_rounds, df_slots, competitive, tournament.bracket_size
        ),
        "badges": _badges_breakdown(df_badges),
        "winnerPseudo": None,
        "entrantsNote": ENTRANTS_NOTE,
    }

    if not df_badges.empty and not df_entrants.empty:
        winner = df_badges[df_badges["type"] == "winner"]
        if not winner.empty:
            winner_user = winner.iloc[0]["user_id"]
            match = df_entrants[df_entrants["user_id"] == winner_user]
            if not match.empty:
                detail["winnerPseudo"] = str(match.iloc[0]["user_pseudo"])

    return detail


def _build_purchase_timeline(df_tickets: pd.DataFrame) -> list[dict]:
    """Daily count and cumulative count of granted tickets (by payment date)."""
    if df_tickets.empty:
        return []
    granted = df_tickets[df_tickets["status"] == "granted"]
    return _build_daily_timeline(granted["paid_at"], "tickets", cumulative=True)


def _build_daily_timeline(
    values: pd.Series | None, name: str, cumulative: bool = False
) -> list[dict]:
    """Daily timeline of a datetime Series, optionally with a running total."""
    if values is None:
        return []
    values = values.dropna()
    if len(values) == 0:
        return []
    daily = pd.to_datetime(values).dt.normalize().value_counts().sort_index()
    running = daily.cumsum()
    return [
        {
            "date": day.date().isoformat(),
            name: int(count),
            **({"cumulative": int(running[day])} if cumulative else {}),
        }
        for day, count in daily.items()
    ]


def _build_rounds(
    df_rounds: pd.DataFrame,
    df_slots: pd.DataFrame,
    df_competitive: pd.DataFrame,
    bracket_size: int | None,
) -> list[dict]:
    """Per-window statistics: qualifying then rounds 1..6, in calendar order."""
    if df_rounds.empty:
        return []

    rounds = []
    for r in df_rounds.itertuples(index=False):
        grid_id = None if pd.isna(r.grid_id) else int(r.grid_id)
        subs = (
            df_competitive[df_competitive["grid_id"] == grid_id]
            if grid_id is not None and not df_competitive.empty
            else df_competitive.iloc[0:0]
        )
        slots = (
            df_slots[df_slots["round_id"] == r.id] if not df_slots.empty else df_slots
        )
        entry = {
            "position": int(r.position),
            **label_round(int(r.position), bracket_size),
            "gridId": grid_id,
            "gridNumber": extract_grid_number(r.version),
            "gridVersion": r.version if isinstance(r.version, str) else None,
            "opensAt": _to_iso(r.opens_at),
            "closesAt": _to_iso(r.closes_at),
            "openedAt": _to_iso(r.opened_at),
            "closedAt": _to_iso(r.closed_at),
            "submissions": summarize_submissions(subs),
            "slots": summarize_slots(slots)
            if r.position != QUALIFYING_POSITION
            else None,
        }
        rounds.append(entry)

    return rounds
