from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Permission:
    operation: str
    risk_level: RiskLevel
    description: str
    requires_approval: bool = True


class PermissionDeniedError(Exception):
    def __init__(self, operation: str, risk_level: RiskLevel) -> None:
        self.operation = operation
        self.risk_level = risk_level
        super().__init__(
            f"Permission denied for '{operation}' "
            f"(risk: {risk_level.value})"
        )


_REGISTRY: dict[str, Permission] = {}


def register_permission(
    operation: str,
    risk_level: RiskLevel,
    description: str,
) -> None:
    _REGISTRY[operation] = Permission(
        operation=operation,
        risk_level=risk_level,
        description=description,
        requires_approval=risk_level != RiskLevel.LOW,
    )


def get_permission(operation: str) -> Permission | None:
    return _REGISTRY.get(operation)


def list_permissions() -> list[Permission]:
    return list(_REGISTRY.values())


register_permission(
    "connector.sync",
    RiskLevel.LOW,
    "Sync data from a connector",
)
register_permission(
    "memory.purge",
    RiskLevel.HIGH,
    "Delete stored documents and entities",
)
register_permission(
    "memory.purge_all",
    RiskLevel.CRITICAL,
    "Delete ALL stored data",
)
register_permission(
    "connector.scrape_content",
    RiskLevel.MEDIUM,
    "Scrape web page content from URLs",
)
register_permission(
    "audio.live_capture",
    RiskLevel.HIGH,
    "Capture live system audio for transcription",
)
register_permission(
    "enrichment.web_search",
    RiskLevel.LOW,
    "Search the web for entity enrichment",
)
register_permission(
    "enrichment.web_scrape",
    RiskLevel.MEDIUM,
    "Scrape web pages for entity enrichment",
)
register_permission(
    "marketplace.install",
    RiskLevel.MEDIUM,
    "Install a third-party connector package",
)
register_permission(
    "marketplace.uninstall",
    RiskLevel.MEDIUM,
    "Uninstall a connector package",
)


class ApprovalManager:
    def __init__(self, auto_approve_low: bool = True) -> None:
        self._auto_approve_low = auto_approve_low
        self._db: Any = None

    def set_db(self, db: Any) -> None:
        self._db = db

    def is_approved(self, operation: str) -> bool:
        perm = get_permission(operation)
        if perm is None:
            return True

        if perm.risk_level == RiskLevel.LOW and self._auto_approve_low:
            return True

        if self._db:
            return self._db.is_approved(operation)

        return False

    def approve(self, operation: str, ttl_hours: int = 24) -> None:
        if self._db:
            self._db.approve(operation, ttl_hours)

    def revoke(self, operation: str) -> None:
        if self._db:
            self._db.revoke(operation)

    def list_approvals(self) -> list[dict[str, Any]]:
        if self._db:
            return self._db.list_approvals()
        return []

    def check_or_raise(self, operation: str) -> None:
        if not self.is_approved(operation):
            perm = get_permission(operation)
            level = perm.risk_level if perm else RiskLevel.MEDIUM
            raise PermissionDeniedError(operation, level)


_manager = ApprovalManager()


def get_approval_manager() -> ApprovalManager:
    return _manager


def requires_permission(operation: str):
    """Decorator that checks permission before executing."""
    def decorator(func: Any) -> Any:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            mgr = get_approval_manager()
            mgr.check_or_raise(operation)
            return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            mgr = get_approval_manager()
            mgr.check_or_raise(operation)
            return func(*args, **kwargs)

        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator
