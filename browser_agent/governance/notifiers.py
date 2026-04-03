"""Notification backends for approval workflows."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class Notifier(ABC):
    """Base class for approval notification backends."""

    @abstractmethod
    async def send_approval_request(self, request) -> bool:
        """Send notification about a new approval request."""

    @abstractmethod
    async def send_resolution(self, request) -> bool:
        """Send notification about a resolved request."""


class WebhookNotifier(Notifier):
    """Generic webhook notifier — POST JSON to a URL."""

    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None,
                 secret: Optional[str] = None):
        self._url = url
        self._headers = headers or {}
        self._secret = secret

    async def send_approval_request(self, request) -> bool:
        payload = {
            "type": "approval_requested",
            "request_id": request.request_id,
            "task_id": request.task_id,
            "description": request.description,
            "status": request.status.value,
            "requested_by": request.requested_by,
            "approvers": request.approvers,
            "expires_at": request.expires_at.isoformat() if request.expires_at else None,
        }
        return await self._post(payload)

    async def send_resolution(self, request) -> bool:
        payload = {
            "type": "approval_resolved",
            "request_id": request.request_id,
            "task_id": request.task_id,
            "status": request.status.value,
            "resolved_by": request.resolved_by,
            "resolution_note": request.resolution_note,
        }
        return await self._post(payload)

    async def _post(self, payload: dict) -> bool:
        try:
            import aiohttp
            headers = {"Content-Type": "application/json", **self._headers}
            async with aiohttp.ClientSession() as session:
                async with session.post(self._url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    return resp.status < 400
        except ImportError:
            # Fallback: use urllib
            import urllib.request
            req = urllib.request.Request(
                self._url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json", **self._headers},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status < 400
            except Exception as e:
                logger.warning("Webhook failed: %s", e)
                return False
        except Exception as e:
            logger.warning("Webhook failed: %s", e)
            return False


class SlackNotifier(Notifier):
    """Slack webhook notifier."""

    def __init__(self, webhook_url: str, channel: Optional[str] = None):
        self._webhook_url = webhook_url
        self._channel = channel

    async def send_approval_request(self, request) -> bool:
        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"⚠️ *Approval Required*\n{request.description}"}},
            {"type": "section", "fields": [
                {"type": "mrkdwn", "text": f"*Task:* `{request.task_id}`"},
                {"type": "mrkdwn", "text": f"*Requested by:* {request.requested_by}"},
            ]},
            {"type": "actions", "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"}, "style": "primary",
                 "value": request.request_id, "action_id": f"approve_{request.request_id}"},
                {"type": "button", "text": {"type": "plain_text", "text": "❌ Deny"}, "style": "danger",
                 "value": request.request_id, "action_id": f"deny_{request.request_id}"},
            ]},
        ]
        payload = {"blocks": blocks}
        if self._channel:
            payload["channel"] = self._channel
        return await self._post_slack(payload)

    async def send_resolution(self, request) -> bool:
        emoji = "✅" if request.status.value == "approved" else "❌"
        text = f"{emoji} *{request.status.value.title()}*\nRequest `{request.request_id}` was {request.status.value}"
        if request.resolved_by:
            text += f" by {request.resolved_by}"
        return await self._post_slack({"text": text})

    async def _post_slack(self, payload: dict) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(
                self._webhook_url,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except Exception as e:
            logger.warning("Slack notification failed: %s", e)
            return False


class TeamsNotifier(Notifier):
    """Microsoft Teams webhook notifier."""

    def __init__(self, webhook_url: str):
        self._webhook_url = webhook_url

    async def send_approval_request(self, request) -> bool:
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": "FF6600",
            "summary": "Approval Required",
            "sections": [{
                "activityTitle": "⚠️ Approval Required",
                "facts": [
                    {"name": "Task", "value": request.task_id},
                    {"name": "Description", "value": request.description},
                    {"name": "Requested by", "value": request.requested_by},
                ],
            }],
        }
        return await self._post_teams(card)

    async def send_resolution(self, request) -> bool:
        color = "00FF00" if request.status.value == "approved" else "FF0000"
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": f"Request {request.status.value}",
            "sections": [{
                "activityTitle": f"Request {request.status.value.title()}",
                "facts": [
                    {"name": "Request ID", "value": request.request_id},
                    {"name": "Resolved by", "value": request.resolved_by or "N/A"},
                ],
            }],
        }
        return await self._post_teams(card)

    async def _post_teams(self, card: dict) -> bool:
        try:
            import urllib.request
            req = urllib.request.Request(
                self._webhook_url,
                data=json.dumps(card).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status < 400
        except Exception as e:
            logger.warning("Teams notification failed: %s", e)
            return False


class EmailNotifier(Notifier):
    """Email notification (SMTP). Logs for now — real SMTP in production config."""

    def __init__(self, smtp_host: str = "", smtp_port: int = 587,
                 from_address: str = "bot@localhost",
                 approver_mapping: Optional[Dict[str, str]] = None):
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._from = from_address
        self._mapping = approver_mapping or {}

    async def send_approval_request(self, request) -> bool:
        logger.info(
            "📧 Approval email: %s for request %s",
            request.description, request.request_id,
        )
        return True

    async def send_resolution(self, request) -> bool:
        logger.info(
            "📧 Resolution email: %s for request %s",
            request.status.value, request.request_id,
        )
        return True


class CompositeNotifier(Notifier):
    """Send to multiple notifiers simultaneously."""

    def __init__(self, notifiers: List[Notifier]):
        self._notifiers = notifiers

    async def send_approval_request(self, request) -> bool:
        results = []
        for n in self._notifiers:
            try:
                results.append(await n.send_approval_request(request))
            except Exception as e:
                logger.warning("Notifier %s failed: %s", type(n).__name__, e)
                results.append(False)
        return any(results)

    async def send_resolution(self, request) -> bool:
        results = []
        for n in self._notifiers:
            try:
                results.append(await n.send_resolution(request))
            except Exception as e:
                logger.warning("Notifier %s failed: %s", type(n).__name__, e)
                results.append(False)
        return any(results)
