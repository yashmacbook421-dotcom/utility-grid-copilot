"""Pushes a message to a Slack incoming webhook so a surge event is actually
paged to a human, not just left sitting in a dashboard nobody may be looking
at. Best-effort: a failed notification never blocks surge detection or the
approval flow — it's a convenience channel, not a source of truth.
"""

import logging

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


def notify_slack(text: str) -> tuple[bool, str | None]:
    """Returns (sent, error) — `sent=False, error=None` means no webhook is
    configured (not a failure, just inactive); `sent=False, error=<msg>`
    means it was configured but the request actually failed. Callers that
    want to track notification success/failure (surge_watcher.py) use this
    instead of just firing and forgetting.
    """
    settings = get_settings()
    if not settings.slack_webhook_url:
        return False, None

    try:
        response = requests.post(settings.slack_webhook_url, json={"text": text}, timeout=10)
        response.raise_for_status()
        return True, None
    except requests.RequestException as exc:
        logger.exception("Failed to send Slack notification")
        return False, str(exc)


def notify_sms(text: str) -> tuple[bool, str | None]:
    """Same contract as notify_slack: (sent, error). Uses Twilio's REST API
    directly over HTTP (Basic Auth with the account SID/auth token) rather
    than the `twilio` SDK — one dependency-free `requests` call, consistent
    with how notify_slack talks to its webhook.
    """
    settings = get_settings()
    if not (settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_from_number and settings.twilio_to_number):
        return False, None

    url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
    try:
        response = requests.post(
            url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            data={"To": settings.twilio_to_number, "From": settings.twilio_from_number, "Body": text},
            timeout=10,
        )
        response.raise_for_status()
        return True, None
    except requests.RequestException as exc:
        logger.exception("Failed to send SMS notification")
        return False, str(exc)
