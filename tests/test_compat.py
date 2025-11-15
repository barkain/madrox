"""Tests for Python compatibility layer."""

import sys
from datetime import datetime, timezone

import pytest

from orchestrator.compat import UTC


class TestUTCCompat:
    """Test UTC constant compatibility across Python versions."""

    def test_utc_exists(self):
        """Test that UTC constant is available."""
        assert UTC is not None

    def test_utc_is_timezone_utc(self):
        """Test that UTC is equivalent to timezone.utc."""
        assert UTC == timezone.utc

    def test_utc_with_datetime_now(self):
        """Test that UTC works with datetime.now()."""
        now = datetime.now(UTC)
        assert now.tzinfo == timezone.utc
        assert now.tzinfo is not None

    def test_utc_with_datetime_fromtimestamp(self):
        """Test that UTC works with datetime.fromtimestamp()."""
        timestamp = 1234567890
        dt = datetime.fromtimestamp(timestamp, UTC)
        assert dt.tzinfo == timezone.utc

    def test_utc_replace(self):
        """Test that UTC works with datetime.replace()."""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        dt_utc = dt.replace(tzinfo=UTC)
        assert dt_utc.tzinfo == timezone.utc

    @pytest.mark.skipif(
        sys.version_info < (3, 11),
        reason="datetime.UTC only available in Python 3.11+",
    )
    def test_utc_is_native_in_py311_plus(self):
        """Test that UTC is the native datetime.UTC in Python 3.11+."""
        if sys.version_info >= (3, 11):
            from datetime import UTC as NativeUTC

            assert UTC is NativeUTC

    @pytest.mark.skipif(
        sys.version_info >= (3, 11),
        reason="timezone.utc fallback only used in Python 3.10",
    )
    def test_utc_is_timezone_utc_in_py310(self):
        """Test that UTC is timezone.utc in Python 3.10."""
        assert UTC is timezone.utc


class TestUTCUsage:
    """Test UTC constant in real-world usage patterns."""

    def test_datetime_now_utc(self):
        """Test getting current UTC time."""
        now = datetime.now(UTC)
        # Should be timezone-aware
        assert now.tzinfo is not None
        # Should be in UTC
        assert now.utcoffset().total_seconds() == 0

    def test_datetime_comparison_with_utc(self):
        """Test comparing datetime objects with UTC timezone."""
        dt1 = datetime.now(UTC)
        dt2 = datetime.now(UTC)
        # Should be able to compare
        assert dt1 <= dt2

    def test_datetime_arithmetic_with_utc(self):
        """Test arithmetic operations with UTC datetime objects."""
        from datetime import timedelta

        dt = datetime.now(UTC)
        future = dt + timedelta(hours=1)
        assert future > dt
        assert future.tzinfo == UTC

    def test_utc_serialization(self):
        """Test that UTC datetime can be serialized."""
        dt = datetime.now(UTC)
        iso_str = dt.isoformat()
        assert "+" in iso_str or "Z" in iso_str  # Has timezone info
        # Should be able to parse back
        parsed = datetime.fromisoformat(iso_str)
        assert parsed.tzinfo is not None
