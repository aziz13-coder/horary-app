import sys
import datetime
from pathlib import Path
import pytz
import pytest

# Add backend directory to path to import judgment_engine
BACKEND_DIR = Path(__file__).resolve().parents[1] / 'horary78-main' / 'horary77-main' / 'horary4' / 'backend'
sys.path.append(str(BACKEND_DIR))

import judgment_engine
from judgment_engine import TimezoneManager

NY_LAT = 40.7128
NY_LON = -74.0060


def test_ambiguous_fall_back_time(monkeypatch):
    # Force use of pytz to trigger AmbiguousTimeError handling
    monkeypatch.setattr(judgment_engine, 'ZoneInfo', None)
    tm = TimezoneManager()
    local_dt, utc_dt, tz_used = tm.parse_datetime_with_timezone(
        '2021-11-07', '01:30', lat=NY_LAT, lon=NY_LON
    )
    assert tz_used == 'America/New_York'
    assert local_dt.tzname() == 'EST'
    assert local_dt.utcoffset() == datetime.timedelta(hours=-5)
    assert (utc_dt.hour, utc_dt.minute) == (6, 30)


def test_nonexistent_spring_forward_adjustment(monkeypatch):
    # Force use of pytz and simulate NonExistentTimeError
    monkeypatch.setattr(judgment_engine, 'ZoneInfo', None)

    real_tz = pytz.timezone('America/New_York')

    class DummyTZ:
        def localize(self, dt, is_dst=False):
            if dt == datetime.datetime(2021, 3, 14, 2, 30):
                raise pytz.NonExistentTimeError()
            return real_tz.localize(dt, is_dst=is_dst)

    monkeypatch.setattr(judgment_engine.pytz, 'timezone', lambda _: DummyTZ())

    tm = TimezoneManager()
    local_dt, utc_dt, tz_used = tm.parse_datetime_with_timezone(
        '2021-03-14', '02:30', lat=NY_LAT, lon=NY_LON
    )
    assert tz_used == 'America/New_York'
    assert (local_dt.hour, local_dt.minute) == (3, 30)
    assert local_dt.utcoffset() == datetime.timedelta(hours=-4)
    assert (utc_dt.hour, utc_dt.minute) == (7, 30)


def test_roundtrip_local_to_utc(monkeypatch):
    monkeypatch.setattr(judgment_engine, 'ZoneInfo', None)
    tm = TimezoneManager()
    local_dt, utc_dt, tz_used = tm.parse_datetime_with_timezone(
        '2021-06-01', '12:00', lat=NY_LAT, lon=NY_LON
    )
    assert tz_used == 'America/New_York'
    assert local_dt.utcoffset() == datetime.timedelta(hours=-4)
    assert utc_dt == local_dt.astimezone(pytz.UTC)
