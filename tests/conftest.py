import os
import sys
from unittest.mock import patch

import pytest

# Add backend directory to path for importing the Flask app
BACKEND_PATH = os.path.join(
    os.path.dirname(__file__),
    '..',
    'horary78-main',
    'horary77-main',
    'horary4',
    'backend',
)
sys.path.append(os.path.abspath(BACKEND_PATH))

from app import app as flask_app


@pytest.fixture
def app():
    """Flask application configured for testing."""
    flask_app.config.update({'TESTING': True})

    with patch('_horary_math.safe_geocode') as geocode_mock, \
         patch('judgment_engine.TimezoneManager.get_timezone_for_location') as tz_mock:
        geocode_mock.return_value = (51.5074, -0.1278, 'London, UK')
        tz_mock.return_value = 'Europe/London'
        yield flask_app


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def sample_chart_data():
    """Sample chart request data."""
    return {
        'question': 'Will I get the job?',
        'date': '2024-01-01',
        'time': '12:00',
        'location': 'London, UK',
        'timezone': 'Europe/London',
    }
