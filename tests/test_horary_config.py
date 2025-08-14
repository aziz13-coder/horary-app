import os
import sys
from pathlib import Path
import textwrap

import pytest

# Skip validation on import so tests can control it
os.environ['HORARY_CONFIG_SKIP_VALIDATION'] = 'true'

# Add backend path to import horary_config
MODULE_PATH = Path(__file__).resolve().parents[1] / "horary78-main" / "horary77-main" / "horary4" / "backend"
sys.path.append(str(MODULE_PATH))

from horary_config import HoraryConfig, HoraryError


def test_load_default_config_and_access_known_key(monkeypatch):
    monkeypatch.delenv('HORARY_CONFIG', raising=False)
    HoraryConfig.reset()
    cfg = HoraryConfig()
    assert cfg.get("timing.default_moon_speed_fallback") == 13.0


def test_validate_required_keys_missing(monkeypatch, tmp_path):
    config_content = textwrap.dedent(
        """
        timing:
          default_moon_speed_fallback: 13.0
        orbs:
          conjunction: 8.0
        moon:
          void_rule: "by_sign"
        confidence:
          base_confidence: 100
          lunar_confidence_caps:
            favorable: 80
        radicality:
          asc_too_early: 3.0
          asc_too_late: 27.0
        """
    )
    config_file = tmp_path / "horary_constants.yaml"
    config_file.write_text(config_content)
    monkeypatch.setenv('HORARY_CONFIG', str(config_file))
    HoraryConfig.reset()
    cfg = HoraryConfig()
    with pytest.raises(HoraryError):
        cfg.validate_required_keys()


def test_invalid_yaml_raises_error(monkeypatch, tmp_path):
    invalid_content = "timing: [unclosed_list"
    config_file = tmp_path / "bad.yaml"
    config_file.write_text(invalid_content)
    monkeypatch.setenv('HORARY_CONFIG', str(config_file))
    HoraryConfig.reset()
    with pytest.raises(HoraryError):
        HoraryConfig()
