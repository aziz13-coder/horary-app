import sys
import types
from pathlib import Path

# Ensure backend package is importable
BACKEND_DIR = Path(__file__).resolve().parents[1] / 'horary78-main' / 'horary77-main' / 'horary4' / 'backend'
sys.path.append(str(BACKEND_DIR))

# Stub Swiss Ephemeris with deterministic values
stub_swe = types.ModuleType('swisseph')
stub_swe.SUN = 0
stub_swe.MOON = 1
stub_swe.MERCURY = 2
stub_swe.VENUS = 3
stub_swe.MARS = 4
stub_swe.JUPITER = 5
stub_swe.SATURN = 6
stub_swe.FLG_SWIEPH = 0
stub_swe.FLG_SPEED = 0
stub_swe.PLANET_LONGITUDES = {}


def set_ephe_path(path):
    return None


def calc_ut(jd, planet, flags):
    lon = stub_swe.PLANET_LONGITUDES.get(planet, 0.0)
    return [lon, 0.0, 0.0, 0.0], 0


stub_swe.set_ephe_path = set_ephe_path
stub_swe.calc_ut = calc_ut
sys.modules['swisseph'] = stub_swe

from calculator import EnhancedTraditionalAstrologicalCalculator
from models import Planet, Sign, PlanetPosition, SolarCondition


def _make_pos(planet, lon):
    return PlanetPosition(planet=planet, longitude=lon, latitude=0.0, house=1, sign=Sign.ARIES, dignity_score=0)


def test_cazimi():
    calc = EnhancedTraditionalAstrologicalCalculator()
    sun = _make_pos(Planet.SUN, 228.75)  # 2019-11-11 Mercury transit across Sun (~18° Scorpio)
    mercury = _make_pos(Planet.MERCURY, 228.75)
    analysis = calc._analyze_enhanced_solar_condition(Planet.MERCURY, mercury, sun, 0.0, 0.0, 0.0)
    assert analysis.condition == SolarCondition.CAZIMI


def test_combustion_with_exception(monkeypatch):
    calc = EnhancedTraditionalAstrologicalCalculator()
    monkeypatch.setattr(calc, '_check_enhanced_combustion_exception', lambda *args, **kwargs: True)
    sun = _make_pos(Planet.SUN, 100.0)
    mercury = _make_pos(Planet.MERCURY, 105.0)  # Within combustion orb
    analysis = calc._analyze_enhanced_solar_condition(Planet.MERCURY, mercury, sun, 0.0, 0.0, 0.0)
    assert analysis.condition == SolarCondition.FREE
    assert analysis.traditional_exception is True


def test_under_beams():
    calc = EnhancedTraditionalAstrologicalCalculator()
    sun = _make_pos(Planet.SUN, 100.0)
    mars = _make_pos(Planet.MARS, 112.0)  # Beyond combustion (8.5°) but within 15° under-beams
    analysis = calc._analyze_enhanced_solar_condition(Planet.MARS, mars, sun, 0.0, 0.0, 0.0)
    assert analysis.condition == SolarCondition.UNDER_BEAMS
