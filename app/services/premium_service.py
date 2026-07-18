"""Premium subscription statistics service.

Refunds are NOT persisted in the database: a Stripe refund arrives as an
immediate cancellation (status 'canceled' with subscription_end_date set to
the cancellation instant instead of a period end). They are therefore only
estimated, by checking whether the end date falls on a natural billing
boundary (subscription anchor + n months).
"""

from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta
from sqlalchemy.orm import Session

from app.models import StripeEventLog, User

SUBSCRIPTION_STATUSES = ("active", "past_due", "canceled", "unpaid", "incomplete")

REFUND_ESTIMATE_METHOD = (
    "Abonnés 'canceled' dont la date de fin ne tombe pas à ±3 jours d'un "
    "multiple de mois après la souscription (ancre : date d'acceptation des "
    "CGV au checkout). Estimation — les remboursements ne sont pas "
    "persistés en base."
)

TIMELINE_NOTE = (
    "Source : journal des webhooks Stripe (depuis sa mise en place). "
    "Compte des événements, pas des utilisateurs uniques."
)


def classify_probable_refund(
    end_date: datetime | None,
    anchor: datetime | None,
    tolerance_days: int = 3,
) -> str:
    """Classify a cancelled subscription as probable refund or natural end.

    A natural cancellation ends at the anchor date + n whole months (Stripe
    bills on the subscription creation anchor). An end date far from any
    monthly boundary suggests an admin refund (immediate cancellation).

    Args:
        end_date: subscription_end_date of the cancelled user
        anchor: Subscription start anchor (cgv_accepted_at)
        tolerance_days: Allowed distance from a natural boundary, in days

    Returns:
        str: 'probable_refund', 'natural_end' or 'unknown'
    """
    if end_date is None or anchor is None:
        return "unknown"

    delta_days = (end_date - anchor).days
    if delta_days < 0:
        return "unknown"

    # Candidate month counts around the observed duration
    n_guess = round(delta_days / 30.44)
    for n in (n_guess - 1, n_guess, n_guess + 1):
        if n < 1:
            continue
        boundary = anchor + relativedelta(months=n)
        if abs((end_date - boundary).days) <= tolerance_days:
            return "natural_end"

    return "probable_refund"


def get_premium_stats(db: Session) -> dict:
    """Get premium subscription statistics.

    Args:
        db: Database session

    Returns:
        dict: Status breakdown, premium count, pending cancellations,
            launch promo usage, estimated refunds and subscription timeline
    """
    users_query = db.query(
        User.subscription_status,
        User.subscription_end_date,
        User.cancel_at_period_end,
        User.launch_promo_used,
        User.cgv_accepted_at,
    )
    df = pd.read_sql(users_query.statement, db.connection())

    by_status = {status: 0 for status in SUBSCRIPTION_STATUSES}
    by_status["none"] = 0
    by_status["other"] = 0
    premium_users = 0
    pending_cancellations = 0
    launch_promo_used = 0
    estimated_refunds = {
        "isEstimate": True,
        "probableRefunds": 0,
        "naturalCancellations": 0,
        "unknown": 0,
        "method": REFUND_ESTIMATE_METHOD,
    }

    if not df.empty:
        status = df["subscription_status"]
        for value, count in status.value_counts(dropna=False).items():
            # Non-str covers NULL statuses (None/NaN)
            if not isinstance(value, str):
                by_status["none"] += int(count)
            elif value in SUBSCRIPTION_STATUSES:
                by_status[value] = int(count)
            else:
                by_status["other"] += int(count)

        # Mirror of User::isPremium in the Symfony API: active or past_due,
        # or cancelled with an end date still in the future
        now = pd.Timestamp.now()
        end_date = pd.to_datetime(df["subscription_end_date"])
        premium_mask = status.isin(["active", "past_due"]) | (
            (status == "canceled") & end_date.notna() & (end_date > now)
        )
        premium_users = int(premium_mask.sum())

        pending_cancellations = int(
            ((df["cancel_at_period_end"]) & (status == "active")).sum()
        )
        launch_promo_used = int(df["launch_promo_used"].sum())

        cancelled = df[status == "canceled"]
        for _, row in cancelled.iterrows():
            end = row["subscription_end_date"]
            anchor = row["cgv_accepted_at"]
            classification = classify_probable_refund(
                end if pd.notna(end) else None,
                anchor if pd.notna(anchor) else None,
            )
            if classification == "probable_refund":
                estimated_refunds["probableRefunds"] += 1
            elif classification == "natural_end":
                estimated_refunds["naturalCancellations"] += 1
            else:
                estimated_refunds["unknown"] += 1

    return {
        "byStatus": by_status,
        "premiumUsers": premium_users,
        "pendingCancellations": pending_cancellations,
        "launchPromoUsed": launch_promo_used,
        "estimatedRefunds": estimated_refunds,
        "timeline": _build_subscription_timeline(db),
        "timelineNote": TIMELINE_NOTE,
    }


def _build_subscription_timeline(db: Session) -> list[dict]:
    """Build a monthly timeline of new subscriptions vs cancellations.

    Based on the Stripe webhook event log (exists since the webhook was
    deployed; counts events, not unique users).
    """
    events_query = db.query(
        StripeEventLog.event_type, StripeEventLog.processed_at
    ).filter(
        StripeEventLog.event_type.in_(
            ["checkout.session.completed", "customer.subscription.deleted"]
        )
    )
    df = pd.read_sql(events_query.statement, db.connection())

    if df.empty:
        return []

    df["period"] = pd.to_datetime(df["processed_at"]).dt.to_period("M")
    pivot = (
        df.groupby(["period", "event_type"]).size().unstack(fill_value=0).sort_index()
    )

    return [
        {
            "period": str(period),
            "newSubscriptions": int(row.get("checkout.session.completed", 0)),
            "cancellations": int(row.get("customer.subscription.deleted", 0)),
        }
        for period, row in pivot.iterrows()
    ]
