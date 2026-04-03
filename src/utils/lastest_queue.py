"""Backward-compatible import shim.

This module name contains a historical typo (`lastest_queue`).
New code should import `LatestValueQueue` from `src.utils.latest_queue`.
"""

from src.utils.latest_queue import LatestValueQueue
