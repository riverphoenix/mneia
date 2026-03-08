from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger(__name__)


def install_connector(package_name: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            logger.info(f"Installed {package_name}")
            return True
        logger.error(f"pip install failed: {result.stderr}")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"Installation timed out for {package_name}")
        return False
    except Exception as e:
        logger.error(f"Installation failed: {e}")
        return False


def uninstall_connector(package_name: str) -> bool:
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", package_name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info(f"Uninstalled {package_name}")
            return True
        logger.error(f"pip uninstall failed: {result.stderr}")
        return False
    except Exception as e:
        logger.error(f"Uninstall failed: {e}")
        return False


def is_installed(package_name: str) -> bool:
    try:
        from importlib.metadata import distribution
        distribution(package_name)
        return True
    except Exception:
        return False
