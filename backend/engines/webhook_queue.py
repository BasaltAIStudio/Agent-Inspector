"""
Webhook delivery queue with exponential backoff retry and dead-letter queue support.

Retry schedule: 1s, 2s, 4s, 8s, 16s (max) — 5 total attempts including the initial send.
After MAX_RETRIES failed attempts the delivery is moved to the dead-letter queue (DLQ).
A background worker (WebhookQueue.run_worker) polls the queue on a configurable interval
and processes eligible pending deliveries.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import and_

from backend.database import SessionLocal, WebhookDelivery

logger = logging.getLogger("agentinspector.webhook_queue")

MAX_RETRIES = 5
BACKOFF_SECONDS = [1, 2, 4, 8, 16]


class WebhookQueue:

    @staticmethod
    def _calculate_backoff(retry_count: int) -> int:
        idx = min(retry_count, len(BACKOFF_SECONDS) - 1)
        return BACKOFF_SECONDS[idx]

    @staticmethod
    def enqueue(webhook_url: str, payload: Dict[str, Any], db: Any) -> WebhookDelivery:
        now = datetime.now(timezone.utc)
        delivery = WebhookDelivery(
            webhook_url=webhook_url,
            payload=json.dumps(payload),
            status="pending",
            retry_count=0,
            next_retry_at=now,
            created_at=now,
        )
        db.add(delivery)
        db.commit()
        db.refresh(delivery)
        logger.info("Enqueued webhook delivery %s to %s", delivery.id, webhook_url)
        return delivery

    @staticmethod
    def process_next(db: Any) -> Optional[WebhookDelivery]:
        now = datetime.now(timezone.utc)
        delivery = (
            db.query(WebhookDelivery)
            .filter(
                and_(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.next_retry_at <= now,
                )
            )
            .order_by(WebhookDelivery.created_at.asc())
            .first()
        )
        if not delivery:
            return None

        success = WebhookQueue._send_webhook(delivery.webhook_url, delivery.payload)

        if success:
            delivery.status = "delivered"
            db.commit()
            logger.info("Webhook %s delivered successfully", delivery.id)
            return delivery

        delivery.retry_count += 1
        if delivery.retry_count >= MAX_RETRIES:
            delivery.status = "dead_letter"
            delivery.failed_at = now
            db.commit()
            logger.warning(
                "Webhook %s moved to dead-letter queue after %d retries",
                delivery.id,
                delivery.retry_count,
            )
            return delivery

        backoff = WebhookQueue._calculate_backoff(delivery.retry_count)
        delivery.next_retry_at = now + timedelta(seconds=backoff)
        db.commit()
        logger.info(
            "Webhook %s delivery failed, will retry in %ds (attempt %d)",
            delivery.id,
            backoff,
            delivery.retry_count + 1,
        )
        return delivery

    @staticmethod
    def recover_pending(db: Any) -> int:
        now = datetime.now(timezone.utc)
        stuck = (
            db.query(WebhookDelivery)
            .filter(
                and_(
                    WebhookDelivery.status == "pending",
                    WebhookDelivery.next_retry_at.is_(None),
                )
            )
            .all()
        )
        recovered = 0
        for delivery in stuck:
            delivery.next_retry_at = now
            recovered += 1
        if recovered:
            db.commit()
        return recovered

    @staticmethod
    def get_dead_letter(db: Any, limit: int = 100) -> List[WebhookDelivery]:
        return (
            db.query(WebhookDelivery)
            .filter(WebhookDelivery.status == "dead_letter")
            .order_by(WebhookDelivery.failed_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def get_stats(db: Any) -> Dict[str, int]:
        pending = db.query(WebhookDelivery).filter(WebhookDelivery.status == "pending").count()
        delivered = db.query(WebhookDelivery).filter(WebhookDelivery.status == "delivered").count()
        dead_letter = db.query(WebhookDelivery).filter(WebhookDelivery.status == "dead_letter").count()
        return {"pending": pending, "delivered": delivered, "dead_letter": dead_letter}

    @staticmethod
    def _send_webhook(url: str, payload: str) -> bool:
        try:
            payload_dict = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload_dict = {"raw": payload}

        try:
            with httpx.Client(timeout=10) as client:
                response = client.post(url, json=payload_dict)
                if response.status_code < 400:
                    return True
                logger.warning("Webhook delivery returned status %d for %s", response.status_code, url)
                return False
        except Exception as exc:
            logger.warning("Webhook delivery to %s failed: %s", url, exc)
            return False

    @staticmethod
    async def run_worker(poll_interval: float = 5.0) -> None:
        logger.info("Webhook retry worker started (poll_interval=%ds)", poll_interval)
        while True:
            try:
                db = SessionLocal()
                try:
                    recovered = WebhookQueue.recover_pending(db)
                    if recovered:
                        logger.info("Recovered %d stuck webhook deliveries", recovered)
                    delivery = WebhookQueue.process_next(db)
                    if delivery:
                        logger.debug("Processed webhook delivery %s -> %s", delivery.id, delivery.status)
                finally:
                    db.close()
            except Exception:
                logger.exception("Webhook worker iteration failed")
            await asyncio.sleep(poll_interval)
