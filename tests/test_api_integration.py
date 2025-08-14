import os
import sys
from unittest.mock import patch


import pytest
from jsonschema import validate

BACKEND_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'horary78-main', 'horary77-main', 'horary4', 'backend')
)
sys.path.append(BACKEND_PATH)

import app  # type: ignore  # noqa: E402
import judgment_engine  # type: ignore  # noqa: E402


def stub_geocode(location_string: str, timeout: int = 10):
    return 51.5, -0.1, "London, UK"


def stub_get_timezone(self, lat: float, lon: float):
    return "Europe/London"


@pytest.fixture()
def client():
    with patch.object(judgment_engine, "safe_geocode", stub_geocode), \
         patch.object(judgment_engine.TimezoneManager, "get_timezone_for_location", stub_get_timezone):
        with app.app.test_client() as client:
            yield client


def test_calculate_chart(client):
    payload = {
        "question": "Will I win?",
        "location": "Test Location",
        "date": "2025-01-15",
        "time": "10:30",
        "useCurrentTime": False,
    }
    response = client.post("/api/calculate-chart", json=payload)
    assert response.status_code == 200
    data = response.get_json()

    schema = {
        "type": "object",
        "required": ["reasoning", "chart_data", "moon_aspects"],
        "properties": {
            "reasoning": {"type": "array", "items": {"type": "string"}},
            "chart_data": {
                "type": "object",
                "required": ["houses", "planets"],
                "properties": {
                    "houses": {"type": "array", "minItems": 12, "items": {"type": "number"}},
                    "planets": {"type": "object"},
                },
            },
            "moon_aspects": {"type": "array", "minItems": 1},
        },
    }
    validate(instance=data, schema=schema)

    assert any("Radicality" in item for item in data["reasoning"])
    assert len(data["chart_data"]["houses"]) == 12
    assert data["chart_data"]["planets"]
    assert data["moon_aspects"]
