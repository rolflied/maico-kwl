"""Tests for the HA-free register helpers."""

from datetime import datetime

import pytest

from custom_components.maico_kwl import registers as r


def test_codecs() -> None:
    """Signed tenths, u32 and their inverse."""
    assert r.S16_TENTHS.decode([0xFFCE]) == -5.0
    assert r.S16_TENTHS.encode(-5.0) == [0xFFCE]
    assert r.S16_TENTHS.encode(21.5) == [215]
    assert r.U32.decode([1, 2315]) == 67851
    assert r.U32.encode(67851) == [1, 2315]
    with pytest.raises(ValueError):
        r.U16.encode(-1)


def test_read_value_missing_word() -> None:
    """A missing word gives None."""
    assert r.read_value({858: 1}, 858, r.U32) is None


def test_active_bits() -> None:
    """Bits map to slugs, unknown bits to bit_<n>."""
    assert r.active_bits((1 << 9) | (1 << 15), r.NOTICE_BITS) == ["device_filter_due", "bit_15"]


def test_identity() -> None:
    """Out-of-range values or no values are rejected."""
    assert r.identity_problem({550: 1, 554: 3}) is None
    assert "550" in r.identity_problem({550: 9})
    assert r.identity_problem({}) is not None


def test_clock() -> None:
    """Clock registers round-trip; invalid dates give None."""
    data = dict(
        zip(range(100, 106), r.encode_clock(datetime(2026, 10, 11, 14, 30, 5)), strict=True)
    )
    assert r.decode_clock(data) == datetime(2026, 10, 11, 14, 30, 5)
    data[101] = 13
    assert r.decode_clock(data) is None


def test_heat_recovery() -> None:
    """Efficiency is clamped and skipped for small spans."""
    assert r.heat_recovery_efficiency(-5.0, 17.0, 22.0) == 81.5
    assert r.heat_recovery_efficiency(20.0, 21.0, 21.5) is None
    assert r.heat_recovery_efficiency(0.0, 30.0, 20.0) == 100.0
    assert r.heat_recovery_power(160, -5.0, 17.0) == pytest.approx(1179.2, abs=0.1)
