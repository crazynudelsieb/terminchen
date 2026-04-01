"""Web Push notification service.

Manages push subscriptions and sends notifications via the Web Push protocol
using VAPID authentication. Requires VAPID_PRIVATE_KEY, VAPID_PUBLIC_KEY, and
VAPID_CLAIMS_EMAIL to be set in config / env. Leave VAPID_PRIVATE_KEY empty to
disable push entirely.
"""

import json
import logging

from flask import current_app

from app.database import db
from app.models import PushSubscription

logger = logging.getLogger(__name__)


def is_push_enabled():
    """Return True if VAPID keys are configured."""
    return bool(current_app.config.get('VAPID_PRIVATE_KEY'))


def get_vapid_public_key():
    """Return the VAPID public key (applicationServerKey for the browser)."""
    return current_app.config.get('VAPID_PUBLIC_KEY', '')


def subscribe(calendar_id, endpoint, p256dh, auth, member_id=None):
    """Create or update a push subscription for a calendar.

    If the endpoint already exists, update the keys (browser may rotate them).
    """
    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = p256dh
        existing.auth = auth
        existing.calendar_id = calendar_id
        if member_id:
            existing.member_id = member_id
        db.session.commit()
        logger.info("push.subscription_updated", extra={"calendar_id": str(calendar_id)})
        return existing

    sub = PushSubscription(
        calendar_id=calendar_id,
        endpoint=endpoint,
        p256dh=p256dh,
        auth=auth,
        member_id=member_id,
    )
    db.session.add(sub)
    db.session.commit()
    logger.info("push.subscription_created", extra={"calendar_id": str(calendar_id)})
    return sub


def unsubscribe(endpoint):
    """Remove a push subscription by endpoint URL."""
    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if sub:
        db.session.delete(sub)
        db.session.commit()
        logger.info("push.subscription_removed")
        return True
    return False


def send_notification(calendar, title, body, url=None, tag=None):
    """Send a push notification to all subscribers of a calendar.

    Args:
        calendar: Calendar model instance
        title: Notification title
        body: Notification body text
        url: Optional URL to open when the notification is clicked
        tag: Optional notification tag (for collapsing duplicate notifications)
    """
    if not is_push_enabled():
        return 0

    subscriptions = PushSubscription.query.filter_by(calendar_id=calendar.id).all()
    if not subscriptions:
        return 0

    payload = json.dumps({
        'title': title,
        'body': body,
        'url': url or '/',
        'tag': tag or 'terminchen',
        'icon': '/static/icons/icon-192.png',
        'badge': '/static/icons/icon-96.png',
    })

    private_key = current_app.config['VAPID_PRIVATE_KEY']
    claims_email = current_app.config.get('VAPID_CLAIMS_EMAIL', '')
    vapid_claims = {'sub': f'mailto:{claims_email}'} if claims_email else {}

    sent = 0
    stale = []

    for sub in subscriptions:
        try:
            from pywebpush import webpush, WebPushException
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=vapid_claims,
            )
            sent += 1
        except WebPushException as e:
            # 404/410 = subscription expired → remove it
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code in (404, 410):
                    stale.append(sub)
                    continue
            logger.warning("push.send_failed", extra={"endpoint": sub.endpoint[:60], "error": str(e)})
        except Exception as e:
            logger.warning("push.send_error", extra={"error": str(e)})

    # Clean up stale subscriptions
    for sub in stale:
        db.session.delete(sub)
    if stale:
        db.session.commit()
        logger.info("push.stale_removed", extra={"count": len(stale)})

    logger.info("push.sent", extra={"calendar_id": str(calendar.id), "sent": sent, "total": len(subscriptions)})
    return sent
