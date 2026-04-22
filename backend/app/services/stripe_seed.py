from __future__ import annotations

import os

try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None


PLANS = [
    {
        "code": "basic",
        "name": "Basic",
        "description": "Core docket alerts and hearing monitoring",
        "monthly_price_cents": 9900,
        "yearly_price_cents": 99000,
    },
    {
        "code": "pro",
        "name": "Pro",
        "description": "Charge changes, custody events, probation and motion tracking",
        "monthly_price_cents": 29900,
        "yearly_price_cents": 299000,
    },
    {
        "code": "premium",
        "name": "Premium",
        "description": "Advanced analytics and anomaly detection",
        "monthly_price_cents": 79900,
        "yearly_price_cents": 799000,
    },
]

METERS = [
    {"key": "alerts_sent", "display_name": "Alerts Sent", "event_name": "alerts_sent"},
    {"key": "monitored_cases", "display_name": "Monitored Cases", "event_name": "monitored_cases"},
]


def seed_catalog() -> dict[str, int]:
    if stripe is None:
        raise RuntimeError("stripe package is not installed. Run: pip install stripe")

    api_key = os.getenv("STRIPE_API_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_API_KEY is required")

    stripe.api_key = api_key

    # This function is intentionally conservative scaffold code.
    # It returns plan/meter counts so callers can add id persistence later.
    return {
        "plans": len(PLANS),
        "meters": len(METERS),
    }
