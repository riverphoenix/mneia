from __future__ import annotations

from unittest.mock import MagicMock, patch

from mneia.marketplace.installer import install_connector, is_installed, uninstall_connector


def test_is_installed_not_found():
    with patch("importlib.metadata.distribution", side_effect=Exception("not found")):
        assert is_installed("mneia-connector-fake") is False


def test_install_connector_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("mneia.marketplace.installer.subprocess.run", return_value=mock_result):
        assert install_connector("mneia-connector-test") is True


def test_install_connector_failure():
    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Could not find package"
    with patch("mneia.marketplace.installer.subprocess.run", return_value=mock_result):
        assert install_connector("mneia-connector-test") is False


def test_uninstall_connector_success():
    mock_result = MagicMock()
    mock_result.returncode = 0
    with patch("mneia.marketplace.installer.subprocess.run", return_value=mock_result):
        assert uninstall_connector("mneia-connector-test") is True
