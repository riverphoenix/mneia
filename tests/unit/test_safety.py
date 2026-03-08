from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from mneia.core.safety import (
    ApprovalManager,
    Permission,
    PermissionDeniedError,
    RiskLevel,
    get_approval_manager,
    get_permission,
    list_permissions,
    register_permission,
    requires_permission,
)


def test_risk_level_values():
    assert RiskLevel.LOW == "low"
    assert RiskLevel.MEDIUM == "medium"
    assert RiskLevel.HIGH == "high"
    assert RiskLevel.CRITICAL == "critical"


def test_permission_dataclass():
    perm = Permission(
        operation="test.op",
        risk_level=RiskLevel.MEDIUM,
        description="Test operation",
    )
    assert perm.operation == "test.op"
    assert perm.requires_approval is True


def test_permission_low_risk_no_approval():
    perm = Permission(
        operation="test.low",
        risk_level=RiskLevel.LOW,
        description="Low risk",
        requires_approval=False,
    )
    assert perm.requires_approval is False


def test_register_and_get_permission():
    register_permission("test.custom", RiskLevel.HIGH, "Custom test op")
    perm = get_permission("test.custom")
    assert perm is not None
    assert perm.risk_level == RiskLevel.HIGH
    assert perm.requires_approval is True


def test_get_permission_not_found():
    assert get_permission("nonexistent.operation.xyz") is None


def test_list_permissions_includes_builtins():
    perms = list_permissions()
    ops = [p.operation for p in perms]
    assert "connector.sync" in ops
    assert "memory.purge" in ops
    assert "memory.purge_all" in ops


def test_permission_denied_error():
    err = PermissionDeniedError("test.op", RiskLevel.HIGH)
    assert err.operation == "test.op"
    assert err.risk_level == RiskLevel.HIGH
    assert "test.op" in str(err)
    assert "high" in str(err)


def test_approval_manager_auto_approve_low():
    mgr = ApprovalManager(auto_approve_low=True)
    assert mgr.is_approved("connector.sync") is True


def test_approval_manager_denies_medium_without_db():
    mgr = ApprovalManager(auto_approve_low=True)
    assert mgr.is_approved("marketplace.install") is False


def test_approval_manager_approves_unknown():
    mgr = ApprovalManager()
    assert mgr.is_approved("totally.unknown.op") is True


def test_approval_manager_with_db():
    mock_db = MagicMock()
    mock_db.is_approved.return_value = True

    mgr = ApprovalManager(auto_approve_low=True)
    mgr.set_db(mock_db)
    assert mgr.is_approved("memory.purge") is True
    mock_db.is_approved.assert_called_with("memory.purge")


def test_approval_manager_check_or_raise():
    mgr = ApprovalManager(auto_approve_low=True)
    mgr.check_or_raise("connector.sync")

    with pytest.raises(PermissionDeniedError):
        mgr.check_or_raise("memory.purge")


def test_approval_manager_approve_delegates():
    mock_db = MagicMock()
    mgr = ApprovalManager()
    mgr.set_db(mock_db)
    mgr.approve("test.op", ttl_hours=48)
    mock_db.approve.assert_called_with("test.op", 48)


def test_approval_manager_revoke_delegates():
    mock_db = MagicMock()
    mgr = ApprovalManager()
    mgr.set_db(mock_db)
    mgr.revoke("test.op")
    mock_db.revoke.assert_called_with("test.op")


def test_approval_manager_list_approvals_empty():
    mgr = ApprovalManager()
    assert mgr.list_approvals() == []


def test_approval_manager_list_approvals_delegates():
    mock_db = MagicMock()
    mock_db.list_approvals.return_value = [
        {"operation": "test.op", "approved_at": "now"},
    ]
    mgr = ApprovalManager()
    mgr.set_db(mock_db)
    result = mgr.list_approvals()
    assert len(result) == 1


async def test_requires_permission_allows():
    mgr = get_approval_manager()
    original_auto = mgr._auto_approve_low
    mgr._auto_approve_low = True

    @requires_permission("connector.sync")
    async def my_func():
        return "ok"

    result = await my_func()
    assert result == "ok"
    mgr._auto_approve_low = original_auto


async def test_requires_permission_denies():
    mgr = get_approval_manager()
    original_db = mgr._db
    mgr._db = None

    @requires_permission("memory.purge")
    async def my_func():
        return "ok"

    with pytest.raises(PermissionDeniedError):
        await my_func()

    mgr._db = original_db


def test_requires_permission_sync():
    mgr = get_approval_manager()
    original_auto = mgr._auto_approve_low
    mgr._auto_approve_low = True

    @requires_permission("connector.sync")
    def my_sync_func():
        return "ok"

    result = my_sync_func()
    assert result == "ok"
    mgr._auto_approve_low = original_auto


def test_get_approval_manager_singleton():
    mgr1 = get_approval_manager()
    mgr2 = get_approval_manager()
    assert mgr1 is mgr2
