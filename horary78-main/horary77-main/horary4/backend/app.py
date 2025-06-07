# -*- coding: utf-8 -*-

"""

Enhanced Traditional Horary Astrology Flask API with All New Features

UPDATED to use Enhanced Engine with Solar Conditions and New Features



Created on Wed May 28 11:10:58 2025

Updated with enhanced engine and all new capabilities



@author: sabaa (enhanced)

"""



from flask import Flask, request, jsonify

from flask_cors import CORS

import json

import traceback

import time

import logging

from datetime import datetime, timezone

from functools import wraps

from collections import defaultdict



# UPDATED IMPORT: Use the new enhanced engine

from horary_engine import HoraryEngine, LocationError, serialize_planet_with_solar



# Configure logging

logging.basicConfig(

    level=logging.INFO,

    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',

    handlers=[

        logging.FileHandler('horary_api.log'),

        logging.StreamHandler()

    ]

)



logger = logging.getLogger(__name__)



app = Flask(__name__)

CORS(app)  # Enable CORS for all routes



# UPDATED: Initialize the enhanced horary engine

horary_engine = HoraryEngine()



# Simple metrics collection

class SimpleMetrics:

    def __init__(self):

        self.request_count = defaultdict(int)

        self.error_count = defaultdict(int)

        self.response_times = defaultdict(list)

    

    def record_request(self, endpoint):

        self.request_count[endpoint] += 1

    

    def record_error(self, endpoint, error_type):

        self.error_count[f"{endpoint}_{error_type}"] += 1

    

    def record_response_time(self, endpoint, duration):

        self.response_times[endpoint].append(duration)

        # Keep only last 100 response times per endpoint

        if len(self.response_times[endpoint]) > 100:

            self.response_times[endpoint] = self.response_times[endpoint][-100:]

    

    def get_stats(self):

        stats = {

            'requests': dict(self.request_count),

            'errors': dict(self.error_count),

            'avg_response_times': {}

        }

        

        for endpoint, times in self.response_times.items():

            if times:

                stats['avg_response_times'][endpoint] = sum(times) / len(times)

        

        return stats



metrics = SimpleMetrics()



def timing_decorator(endpoint_name):

    """Decorator to time API endpoints"""

    def decorator(func):

        @wraps(func)

        def wrapper(*args, **kwargs):

            metrics.record_request(endpoint_name)

            start_time = time.time()

            

            try:

                result = func(*args, **kwargs)

                duration = time.time() - start_time

                metrics.record_response_time(endpoint_name, duration)

                

                logger.info(f"{endpoint_name} completed in {duration:.2f}s")

                return result

                

            except Exception as e:

                duration = time.time() - start_time

                metrics.record_response_time(endpoint_name, duration)

                metrics.record_error(endpoint_name, type(e).__name__)

                

                logger.error(f"{endpoint_name} failed after {duration:.2f}s: {str(e)}")

                raise

        

        return wrapper

    return decorator



@app.route('/api/health', methods=['GET'])

@timing_decorator('health')

def health_check():

    """Enhanced health check with service validation"""

    

    health_status = {

        'status': 'healthy',

        'timestamp': datetime.now(timezone.utc).isoformat(),

        'version': '2.0.0',  # UPDATED: Enhanced version

        'services': {},

        'metrics': metrics.get_stats(),

        'enhanced_features': {  # NEW: Show enhanced capabilities

            'future_retrograde_frustration': True,

            'directional_sign_exit': True,

            'translation_sequence_enforcement': True,

            'refranation_abscission_detection': True,

            'enhanced_reception_weighting': True,

            'venus_mercury_combustion_exceptions': True,

            'variable_moon_speed_timing': True,

            'fail_fast_geocoding': True,

            'optional_override_flags': True

        }

    }

    

    # Test timezone finder

    try:

        from timezonefinder import TimezoneFinder

        tf = TimezoneFinder()

        test_tz = tf.timezone_at(lat=51.5074, lng=-0.1278)  # London

        health_status['services']['timezone_finder'] = {

            'status': 'healthy' if test_tz else 'degraded',

            'test_result': test_tz

        }

    except Exception as e:

        health_status['services']['timezone_finder'] = {

            'status': 'unhealthy',

            'error': str(e)

        }

    

    # Test Swiss Ephemeris

    try:

        import swisseph as swe

        jd = swe.julday(2025, 5, 29, 12.0)

        sun_pos = swe.calc_ut(jd, swe.SUN)

        health_status['services']['swiss_ephemeris'] = {

            'status': 'healthy',

            'test_calculation': f"Sun at {sun_pos[0][0]:.2f}°"

        }

    except Exception as e:

        health_status['services']['swiss_ephemeris'] = {

            'status': 'unhealthy',

            'error': str(e)

        }

    

    # Test geocoding with enhanced error handling

    try:

        from geopy.geocoders import Nominatim

        geolocator = Nominatim(user_agent="enhanced_health_check")

        location = geolocator.geocode("London, UK", timeout=5)

        health_status['services']['geocoding'] = {

            'status': 'healthy' if location else 'degraded',

            'test_result': location.address if location else None

        }

    except Exception as e:

        health_status['services']['geocoding'] = {

            'status': 'unhealthy',

            'error': str(e)

        }

    

    # Test computational helpers

    try:

        from _horary_math import calculate_elongation, normalize_longitude

        test_elongation = calculate_elongation(120.0, 90.0)

        test_normalize = normalize_longitude(380.0)

        health_status['services']['computational_helpers'] = {

            'status': 'healthy',

            'test_calculations': {

                'elongation_120_90': f"{test_elongation:.2f}°",

                'normalize_380': f"{test_normalize:.2f}°"

            }

        }

    except Exception as e:

        health_status['services']['computational_helpers'] = {

            'status': 'unhealthy',

            'error': str(e)

        }

    

    # Overall status determination

    service_statuses = [s['status'] for s in health_status['services'].values()]

    if 'unhealthy' in service_statuses:

        health_status['status'] = 'unhealthy'

        return jsonify(health_status), 503

    elif 'degraded' in service_statuses:

        health_status['status'] = 'degraded'

        return jsonify(health_status), 200

    

    return jsonify(health_status), 200



@app.route('/api/get-timezone', methods=['POST'])

@timing_decorator('get_timezone')

def get_timezone():

    """Get timezone information for a given location with enhanced error handling"""

    try:

        data = request.get_json()

        

        if not data:

            return jsonify({'error': 'No JSON data provided', 'success': False}), 400

        

        location = data.get('location', '').strip()

        

        if not location:

            return jsonify({'error': 'Location is required', 'success': False}), 400

        

        logger.info(f"Getting timezone for location: {location}")

        

        # ENHANCED: Use fail-fast geocoding

        try:

            from _horary_math import safe_geocode

            lat, lon, full_location = safe_geocode(location)

            

            # Get timezone using enhanced timezone manager

            from horary_engine import TimezoneManager

            timezone_manager = TimezoneManager()

            timezone_str = timezone_manager.get_timezone_for_location(lat, lon)

            

            result = {

                'location': full_location,

                'latitude': lat,

                'longitude': lon,

                'timezone': timezone_str,

                'success': True,

                'enhanced_geocoding': True  # NEW: Indicate enhanced processing

            }

            

            logger.info(f"Enhanced timezone detection successful: {timezone_str} for {full_location}")

            return jsonify(result)

            

        except LocationError as e:

            # ENHANCED: Proper location error handling

            error_msg = str(e)

            logger.warning(f"Location error: {error_msg}")

            return jsonify({

                'error': error_msg,

                'success': False,

                'error_type': 'LocationError'

            }), 404

            

        except Exception as e:

            error_msg = f'Error getting timezone for {location}: {str(e)}'

            logger.error(error_msg)

            return jsonify({

                'error': error_msg,

                'success': False

            }), 500

            

    except Exception as e:

        logger.error(f"Unexpected error in get_timezone: {str(e)}")

        return jsonify({

            'error': f'Internal server error: {str(e)}',

            'success': False

        }), 500



@app.route('/api/current-time', methods=['POST'])

@timing_decorator('current_time')

def get_current_time():

    """Get current time for a specific location with enhanced processing"""

    try:

        data = request.get_json()

        

        if not data:

            return jsonify({'error': 'No JSON data provided', 'success': False}), 400

        

        location = data.get('location', '').strip()

        

        if not location:

            return jsonify({'error': 'Location is required', 'success': False}), 400

        

        logger.info(f"Getting current time for location: {location}")

        

        # ENHANCED: Use fail-fast geocoding

        try:

            from _horary_math import safe_geocode

            lat, lon, full_location = safe_geocode(location)

            

            # Get current time using enhanced timezone manager

            from horary_engine import TimezoneManager

            timezone_manager = TimezoneManager()

            dt_local, dt_utc, timezone_used = timezone_manager.get_current_time_for_location(lat, lon)

            

            result = {

                'location': full_location,

                'latitude': lat,

                'longitude': lon,

                'local_time': dt_local.isoformat(),

                'utc_time': dt_utc.isoformat(),

                'timezone': timezone_used,

                'utc_offset': dt_local.strftime("%z") if hasattr(dt_local, 'strftime') else "Unknown",

                'success': True,

                'enhanced_processing': True  # NEW: Indicate enhanced processing

            }

            

            logger.info(f"Enhanced current time retrieval successful for {full_location}: {dt_local}")

            return jsonify(result)

            

        except LocationError as e:

            # ENHANCED: Proper location error handling

            error_msg = str(e)

            logger.warning(f"Location error: {error_msg}")

            return jsonify({

                'error': error_msg,

                'success': False,

                'error_type': 'LocationError'

            }), 404

            

        except Exception as e:

            error_msg = f'Error getting current time for {location}: {str(e)}'

            logger.error(error_msg)

            return jsonify({

                'error': error_msg,

                'success': False

            }), 500

            

    except Exception as e:

        logger.error(f"Unexpected error in get_current_time: {str(e)}")

        return jsonify({

            'error': f'Internal server error: {str(e)}',

            'success': False

        }), 500



@app.route('/api/calculate-chart', methods=['POST'])

@timing_decorator('calculate_chart')

def calculate_chart():

    """

    ENHANCED: Calculate horary chart with all new features

    Now includes future retrograde, directional motion, enhanced reception, and more

    """

    try:

        data = request.get_json()

        

        if not data:

            return jsonify({

                'error': 'No JSON data provided',

                'judgment': 'ERROR',

                'confidence': 0,

                'reasoning': ['No JSON data provided']

            }), 400

        

        # Extract basic parameters

        question = data.get('question', '').strip()

        location = data.get('location', 'London, UK').strip()

        date_str = data.get('date')

        time_str = data.get('time')

        timezone_str = data.get('timezone')

        use_current_time = data.get('useCurrentTime', True)

        manual_houses = data.get('manualHouses')

        

        # NEW: Extract enhanced parameters

        ignore_radicality = data.get('ignoreRadicality', False)

        ignore_void_moon = data.get('ignoreVoidMoon', False)

        ignore_combustion = data.get('ignoreCombustion', False)

        ignore_saturn_7th = data.get('ignoreSaturn7th', False)

        exaltation_confidence_boost = data.get('exaltationConfidenceBoost', 15.0)

        

        logger.info(f"ENHANCED chart calculation request:")

        logger.info(f"  Question: {question[:100]}..." if len(question) > 100 else f"  Question: {question}")

        logger.info(f"  Location: {location}")

        logger.info(f"  Date: {date_str}")

        logger.info(f"  Time: {time_str}")

        logger.info(f"  Timezone: {timezone_str}")

        logger.info(f"  Use current time: {use_current_time}")

        

        # NEW: Log enhanced parameters

        if any([ignore_radicality, ignore_void_moon, ignore_combustion, ignore_saturn_7th]):

            logger.info(f"  Override flags: radicality={ignore_radicality}, void_moon={ignore_void_moon}, combustion={ignore_combustion}, saturn_7th={ignore_saturn_7th}")

        if exaltation_confidence_boost != 15.0:

            logger.info(f"  Enhanced reception boost: {exaltation_confidence_boost}%")

        

        # Validate required fields

        if not question:

            return jsonify({

                'error': 'Question is required',

                'judgment': 'ERROR',

                'confidence': 0,

                'reasoning': ['No horary question provided']

            }), 400

        

        if not location:

            return jsonify({

                'error': 'Location is required',

                'judgment': 'ERROR', 

                'confidence': 0,

                'reasoning': ['No location provided']

            }), 400

        

        # Validate manual time inputs

        if not use_current_time:

            if not date_str or not time_str:

                return jsonify({

                    'error': 'Date and time are required when not using current time',

                    'judgment': 'ERROR',

                    'confidence': 0,

                    'reasoning': ['Date and time must be provided for manual time entry']

                }), 400

        

        # Convert manual houses if provided

        houses_list = None

        if manual_houses:

            try:

                houses_list = [int(h.strip()) for h in manual_houses.split(',') if h.strip()]

                if len(houses_list) < 2:

                    return jsonify({

                        'error': 'Manual houses must include at least querent and quesited houses (e.g., "1,7")',

                        'judgment': 'ERROR',

                        'confidence': 0,

                        'reasoning': ['Invalid manual house specification']

                    }), 400

            except ValueError:

                return jsonify({

                    'error': 'Manual houses must be numbers separated by commas (e.g., "1,7")',

                    'judgment': 'ERROR',

                    'confidence': 0,

                    'reasoning': ['Invalid manual house format']

                }), 400

        

        # ENHANCED: Calculate chart using new enhanced engine with all features

        start_time = time.time()

        

        try:

            settings = {

                "location": location,

                "date": date_str,

                "time": time_str,

                "timezone": timezone_str,

                "use_current_time": use_current_time,

                "manual_houses": houses_list,

                # NEW: Enhanced features

                "ignore_radicality": ignore_radicality,

                "ignore_void_moon": ignore_void_moon,

                "ignore_combustion": ignore_combustion,

                "ignore_saturn_7th": ignore_saturn_7th,

                "exaltation_confidence_boost": exaltation_confidence_boost

            }

            

            result = horary_engine.judge(question, settings)

            

        except LocationError as e:

            # ENHANCED: Proper location error handling

            logger.error(f"Location error: {str(e)}")

            return jsonify({

                'error': str(e),

                'judgment': 'LOCATION_ERROR',

                'confidence': 0,

                'reasoning': [f'Location error: {str(e)}'],

                'error_type': 'LocationError'

            }), 400

        

        calculation_time = time.time() - start_time

        logger.info(f"ENHANCED chart calculation completed in {calculation_time:.2f} seconds")

        

        # Check for calculation errors

        if result.get('error'):

            logger.error(f"Chart calculation error: {result['error']}")

            return jsonify(result), 500

        

        # ENHANCED: Add enhanced calculation metadata

        result['calculation_metadata'] = {

            'calculation_time_seconds': calculation_time,

            'timestamp': datetime.now(timezone.utc).isoformat(),

            'api_version': '2.0.0',  # Enhanced version

            'engine_version': 'Enhanced Traditional Horary 2.0',

            'enhanced_features_used': {

                'future_retrograde_checks': True,

                'directional_motion_awareness': True,

                'sequence_enforcement': True,

                'enhanced_denial_conditions': True,

                'reception_weighting_nuance': True,

                'solar_condition_enhancements': True,

                'variable_moon_timing': True,

                'fail_fast_geocoding': True

            },

            'override_flags_applied': {

                'ignore_radicality': ignore_radicality,

                'ignore_void_moon': ignore_void_moon,

                'ignore_combustion': ignore_combustion,

                'ignore_saturn_7th': ignore_saturn_7th

            },

            'enhanced_parameters': {

                'exaltation_confidence_boost': exaltation_confidence_boost

            }

        }

        

        logger.info(f"ENHANCED chart calculation successful - Judgment: {result.get('judgment')} (Confidence: {result.get('confidence')}%)")

        

        # NEW: Log enhanced solar factors if present

        solar_factors = result.get('solar_factors', {})

        if solar_factors.get('significant'):

            logger.info(f"Enhanced solar factors: {solar_factors.get('summary', 'None')}")

            if solar_factors.get('cazimi_count', 0) > 0:

                logger.info(f"Cazimi planets detected: {solar_factors['cazimi_count']}")

            if solar_factors.get('combustion_count', 0) > 0:

                logger.info(f"Combusted planets detected: {solar_factors['combustion_count']}")

        

        # NEW: Log enhanced features if they affected judgment

        traditional_factors = result.get('traditional_factors', {})

        if traditional_factors.get('perfection_type'):

            logger.info(f"Perfection type: {traditional_factors['perfection_type']}")

        

        return jsonify(result)

        

    except Exception as e:

        error_msg = f"Error calculating enhanced chart: {str(e)}"

        logger.error(error_msg)

        logger.error(traceback.format_exc())

        

        return jsonify({

            'error': error_msg,

            'judgment': 'ERROR',

            'confidence': 0,

            'reasoning': [f'Enhanced calculation error: {str(e)}'],

            'calculation_metadata': {

                'timestamp': datetime.now(timezone.utc).isoformat(),

                'api_version': '2.0.0'

            }

        }), 500



@app.route('/api/moon-debug', methods=['POST'])

@timing_decorator('moon_debug')

def moon_debug():

    """Get detailed Moon void of course debug information"""

    try:

        data = request.get_json()

        

        if not data:

            return jsonify({'error': 'No JSON data provided'}), 400

        

        return jsonify({

            'message': 'Enhanced Moon debug information is included in chart calculation results',

            'instructions': 'Check the moon_aspects field in the calculate-chart response',

            'enhanced_features': {

                'variable_moon_speed': 'Real-time Moon speed from ephemeris',

                'directional_sign_exit': 'Motion-aware sign boundary calculations',

                'enhanced_void_detection': 'Improved future aspect calculations',

                'solar_conditions': 'Check response.solar_factors for detailed analysis'

            },

            'example_usage': {

                'endpoint': '/api/calculate-chart',

                'moon_debug_location': 'response.moon_aspects',

                'solar_analysis_location': 'response.solar_factors'

            },

            'new_override_options': {

                'ignore_void_moon': 'Set to true to bypass void Moon restrictions',

                'ignore_combustion': 'Set to true to ignore solar condition penalties'

            }

        })

        

    except Exception as e:

        logger.error(f"Error in enhanced moon_debug endpoint: {str(e)}")

        return jsonify({'error': str(e)}), 500



@app.route('/api/metrics', methods=['GET'])

@timing_decorator('metrics')

def get_metrics():

    """Get enhanced API performance metrics"""

    try:

        return jsonify({

            'status': 'success',

            'metrics': metrics.get_stats(),

            'enhanced_engine_stats': {

                'version': '2.0.0',

                'features_enabled': 9,  # Count of major enhanced features

                'classical_sources_implemented': 5

            },

            'timestamp': datetime.now(timezone.utc).isoformat()

        })

    except Exception as e:

        logger.error(f"Error getting enhanced metrics: {str(e)}")

        return jsonify({'error': str(e)}), 500



@app.route('/api/version', methods=['GET'])

def get_version():

    """ENHANCED: Get comprehensive API version information"""

    return jsonify({

        'api_version': '2.0.0',  # Enhanced version

        'engine_version': 'Enhanced Traditional Horary 2.0',

        'release_date': '2025-05-31',

        'features': [

            'Traditional horary analysis',

            'Timezone support',

            'Swiss Ephemeris calculations',

            'Enhanced Moon void of course analysis',

            'Automatic timezone detection',

            'DST handling',

            'Enhanced dignity calculations',

            'Regiomontanus house system',

            'Enhanced Cazimi detection',

            'Enhanced Combustion analysis',

            'Enhanced Under the Beams calculation',

            'Traditional solar exceptions',

            # NEW ENHANCED FEATURES

            'Future retrograde frustration protection',

            'Directional sign-exit awareness',

            'Translation/collection sequence enforcement',

            'Refranation and abscission detection',

            'Enhanced reception weighting nuance',

            'Venus/Mercury combustion exceptions',

            'Variable Moon speed timing',

            'Fail-fast geocoding',

            'Optional override flags'

        ],

        'enhanced_features': {  # NEW: Detailed enhanced features

            'future_retrograde': {

                'description': 'Checks if planets will station before aspect perfection',

                'classical_source': 'Lilly III Chap. XXI - Frustration of planets'

            },

            'directional_motion': {

                'description': 'Respects actual planetary motion for sign boundaries',

                'classical_source': 'Firmicus Maternus - Sign boundaries and motion'

            },

            'sequence_enforcement': {

                'description': 'Validates proper temporal order for translation/collection',

                'classical_source': 'Lilly III Chap. XXVI - Translation of light'

            },

            'denial_conditions': {

                'description': 'Refranation and abscission detection',

                'classical_source': 'Medieval astrological doctrine'

            },

            'reception_weighting': {

                'description': 'Mutual rulership unconditional power, configurable exaltation boost',

                'implementation': 'Traditional dignity hierarchy preserved'

            },

            'enhanced_solar_conditions': {

                'description': 'Visibility-aware Venus/Mercury combustion exceptions',

                'classical_source': 'Ptolemy Almagest, Al-Biruni visibility calculations'

            },

            'variable_timing': {

                'description': 'Real-time Moon speed from ephemeris',

                'classical_source': 'Lilly III Chap. XXV - Moon variable motion'

            },

            'fail_fast_geocoding': {

                'description': 'No silent defaults, clear error messages',

                'enhancement': 'Better user experience and error handling'

            },

            'override_capabilities': {

                'description': 'Optional bypass for radicality, void Moon, combustion',

                'use_case': 'Special circumstances and edge cases'

            }

        },

        'solar_conditions': {

            'implementation': 'Enhanced traditional medieval and renaissance methods',

            'cazimi': {

                'orb': '17 arcminutes (0.28°)',

                'dignity_bonus': '+6 (exact cazimi +8)',

                'description': 'Heart of the Sun - maximum planetary dignity',

                'enhancement': 'Exact cazimi detection within 3 arcminutes'

            },

            'combustion': {

                'orb': '8 degrees 30 arcminutes',

                'dignity_penalty': '-5 (enhanced gradation by distance)',

                'description': 'Planet burnt by Sun - severely weakened',

                'enhanced_exceptions': [

                    'Mercury in own sign (Gemini/Virgo) with visibility check',

                    'Venus as morning/evening star with elongation ≥10° and civil twilight'

                ]

            },

            'under_beams': {

                'orb': '15 degrees',

                'dignity_penalty': '-3 (enhanced gradation by distance)',

                'description': 'Planet obscured by solar rays - moderately weakened',

                'enhancement': 'Distance-based penalty gradation'

            }

        },

        'classical_sources': [

            'William Lilly - Christian Astrology',

            'Guido Bonatti - Liber Astronomicus',

            'Claudius Ptolemy - Tetrabiblos & Almagest',

            'Firmicus Maternus - Mathesis',

            'Al-Biruni - Elements of Astrology'

        ],

        'backward_compatibility': {

            'preserved': True,

            'old_api_supported': True,

            'migration_required': False,

            'enhancement_note': 'All existing code works unchanged'

        },

        'timestamp': datetime.now(timezone.utc).isoformat()

    })



def serialize_moon_debug(debug_data):

    """Convert moon debug data to JSON-serializable format (preserved)"""

    try:

        serialized = {

            'moon_position': debug_data.get('moon_position', {}),

            'sign_analysis': debug_data.get('sign_analysis', {}),

            'current_aspects': debug_data.get('current_aspects', []),

            'void_result': {

                'void': debug_data.get('void_result', {}).get('void', False),

                'exception': debug_data.get('void_result', {}).get('exception', False),

                'reason': debug_data.get('void_result', {}).get('reason', 'Unknown'),

                'degrees_left_in_sign': debug_data.get('void_result', {}).get('degrees_left_in_sign', 0),

                'perfecting_aspects': debug_data.get('void_result', {}).get('perfecting_aspects', False)

            },

            'future_aspects': []

        }

        

        # Convert future aspects with enhanced processing

        void_result = debug_data.get('void_result', {})

        future_aspects = void_result.get('future_aspects', [])

        

        for aspect in future_aspects:

            try:

                serialized['future_aspects'].append({

                    'planet': aspect['planet'].value if hasattr(aspect['planet'], 'value') else str(aspect['planet']),

                    'aspect': aspect['aspect'].display_name if hasattr(aspect['aspect'], 'display_name') else str(aspect['aspect']),

                    'target_degree': float(aspect.get('target_degree', 0)),

                    'degrees_to_reach': float(aspect.get('degrees_to_reach', 0)),

                    'days_to_aspect': float(aspect.get('days_to_aspect', 0)),

                    'will_perfect': bool(aspect.get('will_perfect', False))

                })

            except Exception as e:

                logger.error(f"Error serializing future aspect: {e}")

                continue

        

        return serialized

        

    except Exception as e:

        logger.error(f"Error serializing moon debug: {e}")

        return {

            'error': 'Could not serialize moon debug data',

            'details': str(e)

        }



# Enhanced error handlers

@app.errorhandler(404)

def not_found(error):

    return jsonify({

        'error': 'Endpoint not found',

        'message': 'The requested API endpoint does not exist',

        'api_version': '2.0.0',

        'available_endpoints': [

            '/api/health',

            '/api/calculate-chart',

            '/api/get-timezone',

            '/api/current-time',

            '/api/moon-debug',

            '/api/metrics',

            '/api/version'

        ],

        'enhanced_features': 'See /api/version for full feature list'

    }), 404



@app.errorhandler(405)

def method_not_allowed(error):

    return jsonify({

        'error': 'Method not allowed',

        'message': 'The HTTP method is not allowed for this endpoint',

        'api_version': '2.0.0'

    }), 405



@app.errorhandler(500)

def internal_error(error):

    logger.error(f"Internal server error: {str(error)}")

    return jsonify({

        'error': 'Internal server error',

        'message': 'An unexpected error occurred in the enhanced engine',

        'api_version': '2.0.0',

        'timestamp': datetime.now(timezone.utc).isoformat()

    }), 500



# Request logging middleware (preserved)

@app.before_request

def log_request():

    logger.info(f"{request.method} {request.path} - {request.remote_addr}")



@app.after_request

def log_response(response):

    logger.info(f"Response: {response.status_code} - {request.method} {request.path}")

    return response



if __name__ == '__main__':

    logger.info("Starting Enhanced Traditional Horary Astrology API Server v2.0.0")

    logger.info("Enhanced Features: Future retrograde, directional motion, enhanced reception")

    logger.info("New Capabilities: Refranation/abscission detection, enhanced solar conditions")

    logger.info("Override Options: Radicality, void Moon, combustion, Saturn 7th")

    logger.info("Classical Sources: Lilly, Bonatti, Ptolemy, Firmicus, Al-Biruni")

    logger.info("Backward Compatibility: All existing code works unchanged")

    

    # Development server configuration

    app.run(debug=True, host='0.0.0.0', port=5000)

    

    # For production, use a WSGI server like Gunicorn:

    # gunicorn -w 4 -b 0.0.0.0:5000 app:app