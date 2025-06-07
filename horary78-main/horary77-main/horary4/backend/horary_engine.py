# -*- coding: utf-8 -*-
"""
Complete Traditional Horary Astrology Engine with Enhanced Configuration
REFACTORED VERSION with YAML Configuration and Enhanced Moon Testimony

Created on Wed May 28 11:11:38 2025
Refactored with comprehensive configuration system and enhanced lunar calculations

@author: sabaa (enhanced with configuration system)
"""

import os
import sys
import json
import math
import datetime
import logging
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Any, Union
from enum import Enum
import requests
import subprocess

# Configuration system
from horary_config import get_config, cfg, HoraryError

# Timezone handling
import pytz
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Fallback for Python < 3.9
    ZoneInfo = None

from timezonefinder import TimezoneFinder
import swisseph as swe
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# Import our computational helpers
from _horary_math import (
    calculate_next_station_time, calculate_future_longitude,
    calculate_sign_boundary_longitude, days_to_sign_exit,
    calculate_elongation, is_planet_oriental, sun_altitude_at_civil_twilight,
    calculate_moon_variable_speed, check_aspect_separation_order,
    LocationError, safe_geocode, normalize_longitude, degrees_to_dms
)

# Setup module logger
logger = logging.getLogger(__name__)


class Planet(Enum):
    # Traditional planets only (no outer planets in traditional horary)
    SUN = "Sun"
    MOON = "Moon" 
    MERCURY = "Mercury"
    VENUS = "Venus"
    MARS = "Mars"
    JUPITER = "Jupiter"
    SATURN = "Saturn"
    
    # Chart points
    ASC = "Ascendant"
    MC = "Midheaven"


class Aspect(Enum):
    # Only major (Ptolemaic) aspects used in traditional horary
    CONJUNCTION = (0, "conjunction", "Conjunction")
    SEXTILE = (60, "sextile", "Sextile")
    SQUARE = (90, "square", "Square")
    TRINE = (120, "trine", "Trine")
    OPPOSITION = (180, "opposition", "Opposition")

    def __init__(self, degrees, config_key, display_name):
        self.degrees = degrees
        self.config_key = config_key
        self.display_name = display_name
    
    @property
    def orb(self) -> float:
        """Get orb from configuration"""
        try:
            return cfg().orbs.__dict__[self.config_key]
        except (AttributeError, KeyError):
            logger.warning(f"Orb not found for {self.config_key}, using default 8.0")
            return 8.0


class Sign(Enum):
    ARIES = (0, "Aries", Planet.MARS)
    TAURUS = (30, "Taurus", Planet.VENUS)
    GEMINI = (60, "Gemini", Planet.MERCURY)
    CANCER = (90, "Cancer", Planet.MOON)
    LEO = (120, "Leo", Planet.SUN)
    VIRGO = (150, "Virgo", Planet.MERCURY)
    LIBRA = (180, "Libra", Planet.VENUS)
    SCORPIO = (210, "Scorpio", Planet.MARS)
    SAGITTARIUS = (240, "Sagittarius", Planet.JUPITER)
    CAPRICORN = (270, "Capricorn", Planet.SATURN)
    AQUARIUS = (300, "Aquarius", Planet.SATURN)
    PISCES = (330, "Pisces", Planet.JUPITER)

    def __init__(self, start_degree, sign_name, ruler):
        self.start_degree = start_degree
        self.sign_name = sign_name
        self.ruler = ruler


class SolarCondition(Enum):
    """Solar conditions affecting planetary dignity"""
    CAZIMI = ("Cazimi", 6, "Heart of the Sun - maximum dignity")
    COMBUSTION = ("Combustion", -5, "Burnt by Sun - severely weakened") 
    UNDER_BEAMS = ("Under the Beams", -3, "Obscured by Sun - moderately weakened")
    FREE = ("Free of Sun", 0, "Not affected by solar rays")

    def __init__(self, name, dignity_modifier, description):
        self.condition_name = name
        self.dignity_modifier = dignity_modifier
        self.description = description


@dataclass
class SolarAnalysis:
    """Analysis of planet's relationship to the Sun"""
    planet: Planet
    distance_from_sun: float
    condition: SolarCondition
    exact_cazimi: bool = False
    traditional_exception: bool = False


@dataclass
class PlanetPosition:
    planet: Planet
    longitude: float
    latitude: float
    house: int
    sign: Sign
    dignity_score: int
    retrograde: bool = False
    speed: float = 0.0  # degrees per day


@dataclass
class AspectInfo:
    planet1: Planet
    planet2: Planet
    aspect: Aspect
    orb: float
    applying: bool
    exact_time: Optional[datetime.datetime] = None
    degrees_to_exact: float = 0.0


@dataclass
class LunarAspect:
    """Enhanced lunar aspect information"""
    planet: Planet
    aspect: Aspect
    orb: float
    degrees_difference: float
    perfection_eta_days: float
    perfection_eta_description: str
    applying: bool = True


@dataclass
class Significator:
    """Represents a significator in horary astrology"""
    planet: Planet
    house_ruled: int
    position: PlanetPosition
    role: str  # "querent", "quesited", "co-significator", etc.


@dataclass
class HoraryChart:
    date_time: datetime.datetime
    date_time_utc: datetime.datetime  # UTC time for calculations
    timezone_info: str  # Timezone information
    location: Tuple[float, float]  # (latitude, longitude)
    location_name: str
    planets: Dict[Planet, PlanetPosition]
    aspects: List[AspectInfo]
    houses: List[float]  # House cusps in degrees
    house_rulers: Dict[int, Planet]  # Which planet rules each house
    ascendant: float
    midheaven: float
    solar_analyses: Optional[Dict[Planet, SolarAnalysis]] = None
    julian_day: float = 0.0
    # NEW: Enhanced lunar information
    moon_last_aspect: Optional[LunarAspect] = None
    moon_next_aspect: Optional[LunarAspect] = None


class TimezoneManager:
    """Handles timezone operations for horary calculations"""
    
    def __init__(self):
        self.tf = TimezoneFinder()
        self.geolocator = Nominatim(user_agent="horary_astrology_tz")
    
    def get_timezone_for_location(self, lat: float, lon: float) -> Optional[str]:
        """Get timezone string for given coordinates"""
        try:
            return self.tf.timezone_at(lat=lat, lng=lon)
        except Exception as e:
            logger.error(f"Error getting timezone for {lat}, {lon}: {e}")
            return None
    
    def parse_datetime_with_timezone(self, date_str: str, time_str: str, 
                                   timezone_str: Optional[str] = None, 
                                   lat: float = None, lon: float = None) -> Tuple[datetime.datetime, datetime.datetime, str]:
        """
        Parse datetime string and return both local and UTC datetime objects
        
        Returns:
            Tuple of (local_datetime, utc_datetime, timezone_used)
        """
        # Combine date and time
        dt_naive = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        
        # Determine timezone
        if timezone_str:
            # Use provided timezone
            try:
                if ZoneInfo:
                    tz = ZoneInfo(timezone_str)
                else:
                    tz = pytz.timezone(timezone_str)
                timezone_used = timezone_str
            except Exception:
                # Fallback to UTC if invalid timezone
                tz = pytz.UTC
                timezone_used = "UTC"
        elif lat is not None and lon is not None:
            # Get timezone from coordinates
            tz_str = self.get_timezone_for_location(lat, lon)
            if tz_str:
                try:
                    if ZoneInfo:
                        tz = ZoneInfo(tz_str)
                    else:
                        tz = pytz.timezone(tz_str)
                    timezone_used = tz_str
                except Exception:
                    tz = pytz.UTC
                    timezone_used = "UTC"
            else:
                tz = pytz.UTC
                timezone_used = "UTC"
        else:
            # Default to UTC
            tz = pytz.UTC
            timezone_used = "UTC"
        
        # Create timezone-aware datetime
        if ZoneInfo or hasattr(tz, 'localize'):
            if hasattr(tz, 'localize'):
                # pytz timezone
                try:
                    dt_local = tz.localize(dt_naive)
                except pytz.AmbiguousTimeError:
                    # During DST "fall back" - choose first occurrence
                    dt_local = tz.localize(dt_naive, is_dst=False)
                    logger.warning(f"Ambiguous time {dt_naive} - using standard time")
                except pytz.NonExistentTimeError:
                    # During DST "spring forward" - advance by 1 hour
                    dt_adjusted = dt_naive + datetime.timedelta(hours=1)
                    dt_local = tz.localize(dt_adjusted)
                    logger.warning(f"Non-existent time {dt_naive} - using {dt_adjusted}")
            else:
                # zoneinfo timezone
                dt_local = dt_naive.replace(tzinfo=tz)
        else:
            dt_local = dt_naive.replace(tzinfo=tz)
        
        # Convert to UTC
        dt_utc = dt_local.astimezone(pytz.UTC)
        
        return dt_local, dt_utc, timezone_used
    
    def get_current_time_for_location(self, lat: float, lon: float) -> Tuple[datetime.datetime, datetime.datetime, str]:
        """
        Get current time for a specific location
        
        Returns:
            Tuple of (local_datetime, utc_datetime, timezone_used)
        """
        # Get timezone for location
        tz_str = self.get_timezone_for_location(lat, lon)
        
        if tz_str:
            try:
                if ZoneInfo:
                    tz = ZoneInfo(tz_str)
                else:
                    tz = pytz.timezone(tz_str)
                timezone_used = tz_str
            except Exception:
                tz = pytz.UTC
                timezone_used = "UTC"
        else:
            tz = pytz.UTC
            timezone_used = "UTC"
        
        # Get current UTC time
        utc_now = datetime.datetime.now(pytz.UTC)
        
        # Convert to local time
        local_now = utc_now.astimezone(tz)
        
        return local_now, utc_now, timezone_used


class TraditionalHoraryQuestionAnalyzer:
    """Analyze questions using traditional horary house assignments"""
    
    def __init__(self):
        # Traditional house meanings for horary
        self.house_meanings = {
            1: ["querent", "self", "body", "life", "personality", "appearance"],
            2: ["money", "possessions", "moveable goods", "income", "resources", "values"],
            3: ["siblings", "neighbors", "short journeys", "communication", "letters", "rumors"],
            4: ["father", "home", "land", "property", "endings", "foundations", "graves"],
            5: ["children", "pregnancy", "pleasure", "gambling", "creativity", "entertainment"],
            6: ["illness", "servants", "small animals", "work", "daily routine", "uncle/aunt"],
            7: ["spouse", "partner", "open enemies", "thieves", "others", "contracts"],
            8: ["death", "partner's money", "wills", "transformation", "fear", "surgery"],
            9: ["long journeys", "foreign lands", "religion", "law", "higher learning", "dreams"],
            10: ["mother", "career", "honor", "reputation", "authority", "government"],
            11: ["friends", "hopes", "wishes", "advisors", "king's money", "groups"],
            12: ["hidden enemies", "large animals", "prisons", "secrets", "self-undoing", "witchcraft"]
        }
        
        # Question type patterns
        self.question_patterns = {
            "lost_object": ["where is", "lost", "missing", "find", "stolen"],
            "marriage": ["marry", "wedding", "spouse", "husband", "wife"],
            "pregnancy": ["pregnant", "child", "baby", "conceive"],
            "travel": ["journey", "travel", "trip", "go to", "visit"],
            "money": ["money", "wealth", "rich", "profit", "gain", "debt"],
            "career": ["job", "career", "work", "employment", "business"],
            "health": ["sick", "illness", "disease", "health", "recover", "die"],
            "lawsuit": ["court", "lawsuit", "legal", "judge", "trial"],
            "relationship": ["love", "relationship", "friend", "enemy"]
        }
        
        # Person keywords mapped to their traditional houses
        self.person_keywords = {
            4: ["father", "dad", "grandfather", "stepfather"],
            10: ["mother", "mom", "mum", "stepmother"],
            7: ["spouse", "husband", "wife", "partner"],
            3: ["brother", "sister", "sibling"],
            5: ["child", "son", "daughter", "baby"],
            11: ["friend", "ally", "benefactor"]
        }
    
    def _turn(self, base: int, offset: int) -> int:
        """Return the house offset steps from base (1-based)."""
        return ((base + offset - 1) % 12) + 1
    
    def analyze_question(self, question: str) -> Dict[str, Any]:
        """Analyze question to determine significators using traditional methods"""
        
        question_lower = question.lower()
        
        # Determine question type
        question_type = self._determine_question_type(question_lower)
        
        # Determine primary houses involved
        houses = self._determine_houses(question_lower, question_type)
        
        # Determine significators
        significators = self._determine_significators(houses, question_type)
        
        return {
            "question_type": question_type,
            "relevant_houses": houses,
            "significators": significators,
            "traditional_analysis": True
        }
    
    def _determine_question_type(self, question: str) -> str:
        """Determine the type of horary question"""
        for q_type, keywords in self.question_patterns.items():
            if any(keyword in question for keyword in keywords):
                return q_type
        return "general"
    
    def _determine_houses(self, question: str, question_type: str) -> List[int]:
        """Determine which houses are involved in the question"""
        from typing import List, Set, Optional
        
        houses: List[int] = [1]  # 1st house = querent
        
        # ------------- detect named person -------------
        subject_house: Optional[int] = None
        for h, kws in self.person_keywords.items():
            if any(k in question.lower() for k in kws):
                subject_house = h
                break
        
        # ------------- detect key themes ---------------
        death_words = ["die", "death", "pass away", "funeral"]
        illness_words = ["sick", "illness", "disease", "recover"]
        
        if subject_house is not None:
            q_lower = question.lower()
            if any(w in q_lower for w in death_words):
                houses.append(self._turn(subject_house, 8))  # 8th from subject
                houses.append(subject_house)
            elif any(w in q_lower for w in illness_words):
                houses.append(self._turn(subject_house, 6))  # 6th from subject
                houses.append(subject_house)
            else:
                houses.append(subject_house)
        else:
            # ✱ Unchanged fallback branch ✱
            if question_type == "lost_object":
                houses.append(2)  # Moveable possessions
            elif question_type == "marriage" or "spouse" in question:
                houses.append(7)  # Marriage/spouse
            elif question_type == "pregnancy" or "child" in question:
                houses.append(5)  # Children
            elif question_type == "travel":
                if any(word in question for word in ["far", "foreign", "abroad"]):
                    houses.append(9)  # Long journeys
                else:
                    houses.append(3)  # Short journeys
            elif question_type == "money":
                houses.append(2)  # Money/possessions
            elif question_type == "career":
                houses.append(10)  # Career/reputation
            elif question_type == "health":
                houses.append(6)  # Illness
            elif question_type == "lawsuit":
                houses.append(7)  # Open enemies/legal opponents
            else:
                # Default to 7th house for "others" or general questions
                houses.append(7)
            
            # Look for specific house keywords
            for house, keywords in self.house_meanings.items():
                if house not in houses and any(keyword in question for keyword in keywords):
                    houses.append(house)
        
        # ------------- de-duplicate while preserving order -------------
        seen: Set[int] = set()
        return [h for h in houses if not (h in seen or seen.add(h))]
    
    def _determine_significators(self, houses: List[int], question_type: str) -> Dict[str, Any]:
        """Determine traditional significators"""
        
        significators = {
            "querent_house": 1,  # Always 1st house
            "quesited_house": houses[1] if len(houses) > 1 else 7,
            "moon_role": "co-significator of querent and general flow",
            "special_significators": {}
        }
        
        # Add natural significators based on question type
        if question_type == "marriage":
            significators["special_significators"]["venus"] = "natural significator of love"
            significators["special_significators"]["mars"] = "natural significator of men"
        elif question_type == "money":
            significators["special_significators"]["jupiter"] = "greater fortune"
            significators["special_significators"]["venus"] = "lesser fortune"
        elif question_type == "career":
            significators["special_significators"]["sun"] = "honor and reputation"
            significators["special_significators"]["jupiter"] = "success"
        elif question_type == "health":
            significators["special_significators"]["mars"] = "fever and inflammation"
            significators["special_significators"]["saturn"] = "chronic illness"
        
        return significators
    """Analyze questions using traditional horary house assignments"""
    
    def __init__(self):
        # Traditional house meanings for horary
        self.house_meanings = {
            1: ["querent", "self", "body", "life", "personality", "appearance"],
            2: ["money", "possessions", "moveable goods", "income", "resources", "values"],
            3: ["siblings", "neighbors", "short journeys", "communication", "letters", "rumors"],
            4: ["father", "home", "land", "property", "endings", "foundations", "graves"],
            5: ["children", "pregnancy", "pleasure", "gambling", "creativity", "entertainment"],
            6: ["illness", "servants", "small animals", "work", "daily routine", "uncle/aunt"],
            7: ["spouse", "partner", "open enemies", "thieves", "others", "contracts"],
            8: ["death", "partner's money", "wills", "transformation", "fear", "surgery"],
            9: ["long journeys", "foreign lands", "religion", "law", "higher learning", "dreams"],
            10: ["mother", "career", "honor", "reputation", "authority", "government"],
            11: ["friends", "hopes", "wishes", "advisors", "king's money", "groups"],
            12: ["hidden enemies", "large animals", "prisons", "secrets", "self-undoing", "witchcraft"]
        }
        
        # Question type patterns
        self.question_patterns = {
            "lost_object": ["where is", "lost", "missing", "find", "stolen"],
            "marriage": ["marry", "wedding", "spouse", "husband", "wife"],
            "pregnancy": ["pregnant", "child", "baby", "conceive"],
            "travel": ["journey", "travel", "trip", "go to", "visit"],
            "money": ["money", "wealth", "rich", "profit", "gain", "debt"],
            "career": ["job", "career", "work", "employment", "business"],
            "health": ["sick", "illness", "disease", "health", "recover", "die"],
            "lawsuit": ["court", "lawsuit", "legal", "judge", "trial"],
            "relationship": ["love", "relationship", "friend", "enemy"]
        }
    
    def analyze_question(self, question: str) -> Dict[str, Any]:
        """Analyze question to determine significators using traditional methods"""
        
        question_lower = question.lower()
        
        # Determine question type
        question_type = self._determine_question_type(question_lower)
        
        # Determine primary houses involved
        houses = self._determine_houses(question_lower, question_type)
        
        # Determine significators
        significators = self._determine_significators(houses, question_type)
        
        return {
            "question_type": question_type,
            "relevant_houses": houses,
            "significators": significators,
            "traditional_analysis": True
        }
    
    def _determine_question_type(self, question: str) -> str:
        """Determine the type of horary question"""
        for q_type, keywords in self.question_patterns.items():
            if any(keyword in question for keyword in keywords):
                return q_type
        return "general"
    
    def _determine_houses(self, question: str, question_type: str) -> List[int]:
        """Determine which houses are involved in the question"""
        
        # Start with querent (always 1st house)
        houses = [1]
        
        # Determine quesited house based on question type and content
        if question_type == "lost_object":
            houses.append(2)  # Moveable possessions
        elif question_type == "marriage" or "spouse" in question:
            houses.append(7)  # Marriage/spouse
        elif question_type == "pregnancy" or "child" in question:
            houses.append(5)  # Children
        elif question_type == "travel":
            if any(word in question for word in ["far", "foreign", "abroad"]):
                houses.append(9)  # Long journeys
            else:
                houses.append(3)  # Short journeys
        elif question_type == "money":
            houses.append(2)  # Money/possessions
        elif question_type == "career":
            houses.append(10)  # Career/reputation
        elif question_type == "health":
            houses.append(6)  # Illness
        elif question_type == "lawsuit":
            houses.append(7)  # Open enemies/legal opponents
        else:
            # Default to 7th house for "others" or general questions
            houses.append(7)
        
        # Look for specific house keywords
        for house, keywords in self.house_meanings.items():
            if house not in houses and any(keyword in question for keyword in keywords):
                houses.append(house)
        
        return houses
    
    def _determine_significators(self, houses: List[int], question_type: str) -> Dict[str, Any]:
        """Determine traditional significators"""
        
        significators = {
            "querent_house": 1,  # Always 1st house
            "quesited_house": houses[1] if len(houses) > 1 else 7,
            "moon_role": "co-significator of querent and general flow",
            "special_significators": {}
        }
        
        # Add natural significators based on question type
        if question_type == "marriage":
            significators["special_significators"]["venus"] = "natural significator of love"
            significators["special_significators"]["mars"] = "natural significator of men"
        elif question_type == "money":
            significators["special_significators"]["jupiter"] = "greater fortune"
            significators["special_significators"]["venus"] = "lesser fortune"
        elif question_type == "career":
            significators["special_significators"]["sun"] = "honor and reputation"
            significators["special_significators"]["jupiter"] = "success"
        elif question_type == "health":
            significators["special_significators"]["mars"] = "fever and inflammation"
            significators["special_significators"]["saturn"] = "chronic illness"
        
        return significators


class EnhancedTraditionalAstrologicalCalculator:
    """Enhanced Traditional astrological calculations with configuration system"""
    
    def __init__(self):
        # Set Swiss Ephemeris path
        swe.set_ephe_path('')
        
        # Initialize timezone manager
        self.timezone_manager = TimezoneManager()
        
        # Traditional planets only
        self.planets_swe = {
            Planet.SUN: swe.SUN,
            Planet.MOON: swe.MOON,
            Planet.MERCURY: swe.MERCURY,
            Planet.VENUS: swe.VENUS,
            Planet.MARS: swe.MARS,
            Planet.JUPITER: swe.JUPITER,
            Planet.SATURN: swe.SATURN
        }
        
        # Traditional exaltations
        self.exaltations = {
            Planet.SUN: Sign.ARIES,
            Planet.MOON: Sign.TAURUS,
            Planet.MERCURY: Sign.VIRGO,
            Planet.VENUS: Sign.PISCES,
            Planet.MARS: Sign.CAPRICORN,
            Planet.JUPITER: Sign.CANCER,
            Planet.SATURN: Sign.LIBRA
        }
        
        # Traditional falls (opposite to exaltations)
        self.falls = {
            Planet.SUN: Sign.LIBRA,
            Planet.MOON: Sign.SCORPIO,
            Planet.MERCURY: Sign.PISCES,
            Planet.VENUS: Sign.VIRGO,
            Planet.MARS: Sign.CANCER,
            Planet.JUPITER: Sign.CAPRICORN,
            Planet.SATURN: Sign.ARIES
        }
        
        # Planets that have traditional exceptions to combustion
        self.combustion_resistant = {
            Planet.MERCURY: "Mercury rejoices near Sun",
            Planet.VENUS: "Venus as morning/evening star"
        }
    
    def get_real_moon_speed(self, jd_ut: float) -> float:
        """Get actual Moon speed from ephemeris in degrees per day"""
        try:
            moon_data, ret_flag = swe.calc_ut(jd_ut, swe.MOON, swe.FLG_SWIEPH | swe.FLG_SPEED)
            return abs(moon_data[3])  # degrees per day
        except Exception as e:
            logger.warning(f"Failed to get Moon speed from ephemeris: {e}")
            # Fall back to configured default
            return cfg().timing.default_moon_speed_fallback
    
    def calculate_chart(self, dt_local: datetime.datetime, dt_utc: datetime.datetime, 
                       timezone_info: str, lat: float, lon: float, location_name: str) -> HoraryChart:
        """Enhanced Calculate horary chart with configuration system"""
        
        # Convert UTC datetime to Julian Day for Swiss Ephemeris
        jd_ut = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, 
                          dt_utc.hour + dt_utc.minute/60.0 + dt_utc.second/3600.0)
        
        logger.info(f"Calculating chart for:")
        logger.info(f"  Local time: {dt_local} ({timezone_info})")
        logger.info(f"  UTC time: {dt_utc}")
        logger.info(f"  Julian Day (UT): {jd_ut}")
        logger.info(f"  Location: {location_name} ({lat:.4f}, {lon:.4f})")
        
        # Calculate traditional planets only
        planets = {}
        for planet_enum, planet_id in self.planets_swe.items():
            try:
                planet_data, ret_flag = swe.calc_ut(jd_ut, planet_id, swe.FLG_SWIEPH | swe.FLG_SPEED)
                
                longitude = planet_data[0]
                latitude = planet_data[1]
                speed = planet_data[3]  # degrees/day
                retrograde = speed < 0
                
                sign = self._get_sign(longitude)
                
                planets[planet_enum] = PlanetPosition(
                    planet=planet_enum,
                    longitude=longitude,
                    latitude=latitude,
                    house=0,  # Will be calculated after houses
                    sign=sign,
                    dignity_score=0,  # Will be calculated after solar analysis
                    retrograde=retrograde,
                    speed=speed
                )
                
            except Exception as e:
                logger.error(f"Error calculating {planet_enum.value}: {e}")
                # Create fallback
                planets[planet_enum] = PlanetPosition(
                    planet=planet_enum,
                    longitude=0.0,
                    latitude=0.0,
                    house=1,
                    sign=Sign.ARIES,
                    dignity_score=0,
                    speed=0.0
                )
        
        # Calculate houses (Regiomontanus - traditional for horary)
        try:
            houses_data, ascmc = swe.houses(jd_ut, lat, lon, b'R')  # Regiomontanus
            houses = list(houses_data)
            ascendant = ascmc[0]
            midheaven = ascmc[1]
        except Exception as e:
            logger.error(f"Error calculating houses: {e}")
            ascendant = 0.0
            midheaven = 90.0
            houses = [i * 30.0 for i in range(12)]
        
        # Calculate house positions and house rulers
        house_rulers = {}
        for i, cusp in enumerate(houses, 1):
            sign = self._get_sign(cusp)
            house_rulers[i] = sign.ruler
        
        # Update planet house positions
        for planet_pos in planets.values():
            house = self._calculate_house_position(planet_pos.longitude, houses)
            planet_pos.house = house
        
        # Enhanced solar condition analysis
        sun_pos = planets[Planet.SUN]
        solar_analyses = {}
        
        for planet_enum, planet_pos in planets.items():
            solar_analysis = self._analyze_enhanced_solar_condition(
                planet_enum, planet_pos, sun_pos, lat, lon, jd_ut)
            solar_analyses[planet_enum] = solar_analysis
            
            # Calculate dignity with enhanced solar conditions
            planet_pos.dignity_score = self._calculate_enhanced_dignity(
                planet_pos.planet, planet_pos.sign, planet_pos.house, solar_analysis)
        
        # Calculate enhanced traditional aspects
        aspects = self._calculate_enhanced_aspects(planets, jd_ut)
        
        # NEW: Calculate last and next lunar aspects
        moon_last_aspect = self._calculate_moon_last_aspect(planets, jd_ut)
        moon_next_aspect = self._calculate_moon_next_aspect(planets, jd_ut)
        
        chart = HoraryChart(
            date_time=dt_local,
            date_time_utc=dt_utc,
            timezone_info=timezone_info,
            location=(lat, lon),
            location_name=location_name,
            planets=planets,
            aspects=aspects,
            houses=houses,
            house_rulers=house_rulers,
            ascendant=ascendant,
            midheaven=midheaven,
            solar_analyses=solar_analyses,
            julian_day=jd_ut,
            moon_last_aspect=moon_last_aspect,
            moon_next_aspect=moon_next_aspect
        )
        
        return chart
    
    def _calculate_moon_last_aspect(self, planets: Dict[Planet, PlanetPosition], 
                                   jd_ut: float) -> Optional[LunarAspect]:
        """Calculate Moon's last separating aspect"""
        
        moon_pos = planets[Planet.MOON]
        moon_speed = self.get_real_moon_speed(jd_ut)
        
        # Look back to find most recent separating aspect
        separating_aspects = []
        
        for planet, planet_pos in planets.items():
            if planet == Planet.MOON:
                continue
            
            # Calculate current separation
            separation = abs(moon_pos.longitude - planet_pos.longitude)
            if separation > 180:
                separation = 360 - separation
            
            # Check each aspect type
            for aspect_type in Aspect:
                orb_diff = abs(separation - aspect_type.degrees)
                max_orb = aspect_type.orb
                
                # Wider orb for recently separating
                if orb_diff <= max_orb * 1.5:
                    # Check if separating (Moon was closer recently)
                    if self._is_moon_separating_from_aspect(moon_pos, planet_pos, aspect_type, moon_speed):
                        degrees_since_exact = orb_diff
                        time_since_exact = degrees_since_exact / moon_speed
                        
                        separating_aspects.append(LunarAspect(
                            planet=planet,
                            aspect=aspect_type,
                            orb=orb_diff,
                            degrees_difference=degrees_since_exact,
                            perfection_eta_days=time_since_exact,
                            perfection_eta_description=f"{time_since_exact:.1f} days ago",
                            applying=False
                        ))
        
        # Return most recent (smallest time_since_exact)
        if separating_aspects:
            return min(separating_aspects, key=lambda x: x.perfection_eta_days)
        
        return None
    
    def _calculate_moon_next_aspect(self, planets: Dict[Planet, PlanetPosition], 
                                   jd_ut: float) -> Optional[LunarAspect]:
        """Calculate Moon's next applying aspect"""
        
        moon_pos = planets[Planet.MOON]
        moon_speed = self.get_real_moon_speed(jd_ut)
        
        # Find closest applying aspect
        applying_aspects = []
        
        for planet, planet_pos in planets.items():
            if planet == Planet.MOON:
                continue
            
            # Calculate current separation
            separation = abs(moon_pos.longitude - planet_pos.longitude)
            if separation > 180:
                separation = 360 - separation
            
            # Check each aspect type
            for aspect_type in Aspect:
                orb_diff = abs(separation - aspect_type.degrees)
                max_orb = aspect_type.orb
                
                if orb_diff <= max_orb:
                    # Check if applying
                    if self._is_moon_applying_to_aspect(moon_pos, planet_pos, aspect_type, moon_speed):
                        degrees_to_exact = orb_diff
                        relative_speed = abs(moon_speed - abs(planet_pos.speed))
                        time_to_exact = degrees_to_exact / relative_speed if relative_speed > 0 else float('inf')
                        
                        applying_aspects.append(LunarAspect(
                            planet=planet,
                            aspect=aspect_type,
                            orb=orb_diff,
                            degrees_difference=degrees_to_exact,
                            perfection_eta_days=time_to_exact,
                            perfection_eta_description=self._format_timing_description(time_to_exact),
                            applying=True
                        ))
        
        # Return soonest (smallest time_to_exact)
        if applying_aspects:
            return min(applying_aspects, key=lambda x: x.perfection_eta_days)
        
        return None
    
    def _is_moon_separating_from_aspect(self, moon_pos: PlanetPosition, 
                                       planet_pos: PlanetPosition, aspect: Aspect, 
                                       moon_speed: float) -> bool:
        """Check if Moon is separating from an aspect"""
        
        # Calculate separation change over time
        time_increment = 0.1  # days
        current_separation = abs(moon_pos.longitude - planet_pos.longitude)
        if current_separation > 180:
            current_separation = 360 - current_separation
        
        # Future Moon position
        future_moon_lon = (moon_pos.longitude + moon_speed * time_increment) % 360
        future_separation = abs(future_moon_lon - planet_pos.longitude)
        if future_separation > 180:
            future_separation = 360 - future_separation
        
        # Separating if orb from aspect degree is increasing
        current_orb = abs(current_separation - aspect.degrees)
        future_orb = abs(future_separation - aspect.degrees)
        
        return future_orb > current_orb
    
    def _is_moon_applying_to_aspect(self, moon_pos: PlanetPosition, 
                                   planet_pos: PlanetPosition, aspect: Aspect, 
                                   moon_speed: float) -> bool:
        """Check if Moon is applying to an aspect"""
        
        # Calculate separation change over time
        time_increment = 0.1  # days
        current_separation = abs(moon_pos.longitude - planet_pos.longitude)
        if current_separation > 180:
            current_separation = 360 - current_separation
        
        # Future Moon position
        future_moon_lon = (moon_pos.longitude + moon_speed * time_increment) % 360
        future_separation = abs(future_moon_lon - planet_pos.longitude)
        if future_separation > 180:
            future_separation = 360 - future_separation
        
        # Applying if orb from aspect degree is decreasing
        current_orb = abs(current_separation - aspect.degrees)
        future_orb = abs(future_separation - aspect.degrees)
        
        return future_orb < current_orb
    
    def _format_timing_description(self, days: float) -> str:
        """Format timing description for aspect perfection"""
        if days < 0.5:
            return "Within hours"
        elif days < 1:
            return "Within a day"
        elif days < 7:
            return f"Within {int(days)} days"
        elif days < 30:
            return f"Within {int(days/7)} weeks"
        elif days < 365:
            return f"Within {int(days/30)} months"
        else:
            return "More than a year"
    
    # [Continue with the rest of the methods...]
    # Due to space constraints, I'll continue with key methods
    
    def _analyze_enhanced_solar_condition(self, planet: Planet, planet_pos: PlanetPosition, 
                                        sun_pos: PlanetPosition, lat: float, lon: float,
                                        jd_ut: float) -> SolarAnalysis:
        """Enhanced solar condition analysis with configuration"""
        
        # Don't analyze the Sun itself
        if planet == Planet.SUN:
            return SolarAnalysis(
                planet=planet,
                distance_from_sun=0.0,
                condition=SolarCondition.FREE,
                exact_cazimi=False
            )
        
        # Calculate elongation
        elongation = calculate_elongation(planet_pos.longitude, sun_pos.longitude)
        
        # Get configured orbs
        cazimi_orb = cfg().orbs.cazimi_orb_arcmin / 60.0  # Convert arcminutes to degrees
        combustion_orb = cfg().orbs.combustion_orb
        under_beams_orb = cfg().orbs.under_beams_orb
        
        # Enhanced visibility check for Venus and Mercury
        traditional_exception = False
        if planet in self.combustion_resistant:
            traditional_exception = self._check_enhanced_combustion_exception(
                planet, planet_pos, sun_pos, lat, lon, jd_ut)
        
        # Determine condition by hierarchy
        if elongation <= cazimi_orb:
            # Cazimi - Heart of the Sun (maximum dignity)
            exact_cazimi = elongation <= (3/60)  # Within 3 arcminutes = exact cazimi
            return SolarAnalysis(
                planet=planet,
                distance_from_sun=elongation,
                condition=SolarCondition.CAZIMI,
                exact_cazimi=exact_cazimi,
                traditional_exception=False  # Cazimi overrides exceptions
            )
        
        elif elongation <= combustion_orb:
            # Combustion - but check for traditional exceptions
            if traditional_exception:
                return SolarAnalysis(
                    planet=planet,
                    distance_from_sun=elongation,
                    condition=SolarCondition.FREE,  # Exception negates combustion
                    traditional_exception=True
                )
            else:
                return SolarAnalysis(
                    planet=planet,
                    distance_from_sun=elongation,
                    condition=SolarCondition.COMBUSTION,
                    traditional_exception=False
                )
        
        elif elongation <= under_beams_orb:
            # Under the Beams - with exception handling
            if traditional_exception:
                return SolarAnalysis(
                    planet=planet,
                    distance_from_sun=elongation,
                    condition=SolarCondition.FREE,  # Exception reduces to free
                    traditional_exception=True
                )
            else:
                return SolarAnalysis(
                    planet=planet,
                    distance_from_sun=elongation,
                    condition=SolarCondition.UNDER_BEAMS,
                    traditional_exception=False
                )
        
        # Free of solar interference
        return SolarAnalysis(
            planet=planet,
            distance_from_sun=elongation,
            condition=SolarCondition.FREE,
            traditional_exception=False
        )
    
    def _check_enhanced_combustion_exception(self, planet: Planet, planet_pos: PlanetPosition,
                                           sun_pos: PlanetPosition, lat: float, lon: float, 
                                           jd_ut: float) -> bool:
        """Enhanced combustion exception check with visibility calculations"""
        
        elongation = calculate_elongation(planet_pos.longitude, sun_pos.longitude)
        
        # Must have minimum 10° elongation
        if elongation < 10.0:
            return False
        
        # Check if planet is oriental (morning) or occidental (evening)
        is_oriental = is_planet_oriental(planet_pos.longitude, sun_pos.longitude)
        
        # Get Sun altitude at civil twilight
        sun_altitude = sun_altitude_at_civil_twilight(lat, lon, jd_ut)
        
        # Classical visibility conditions
        if planet == Planet.MERCURY:
            # Mercury rejoices near Sun but needs visibility
            if elongation >= 10.0 and planet_pos.sign in [Sign.GEMINI, Sign.VIRGO]:
                return True
            # Or if greater elongation (18° for Mercury)
            if elongation >= 18.0:
                return True
                
        elif planet == Planet.VENUS:
            # Venus as morning/evening star exception
            if elongation >= 10.0:  # Minimum visibility
                # Check if conditions support visibility
                if sun_altitude <= -8.0:  # Civil twilight or darker
                    return True
                # Or if Venus is at maximum elongation (classical ~47°)
                if elongation >= 40.0:
                    return True
        
        return False
    
    def _calculate_enhanced_dignity(self, planet: Planet, sign: Sign, house: int, 
                                  solar_analysis: Optional[SolarAnalysis] = None) -> int:
        """Enhanced dignity calculation with configuration"""
        score = 0
        config = cfg()
        
        # Rulership
        if sign.ruler == planet:
            score += config.dignity.rulership
        
        # Exaltation
        if planet in self.exaltations and self.exaltations[planet] == sign:
            score += config.dignity.exaltation
        
        # Detriment - opposite to rulership
        detriment_signs = {
            Planet.SUN: [Sign.AQUARIUS],
            Planet.MOON: [Sign.CAPRICORN],
            Planet.MERCURY: [Sign.PISCES, Sign.SAGITTARIUS],
            Planet.VENUS: [Sign.ARIES, Sign.SCORPIO],
            Planet.MARS: [Sign.LIBRA, Sign.TAURUS],
            Planet.JUPITER: [Sign.GEMINI, Sign.VIRGO],
            Planet.SATURN: [Sign.CANCER, Sign.LEO]
        }
        
        if planet in detriment_signs and sign in detriment_signs[planet]:
            score += config.dignity.detriment
        
        # Fall
        if planet in self.falls and self.falls[planet] == sign:
            score += config.dignity.fall
        
        # House considerations - traditional joys
        house_joys = {
            Planet.MERCURY: 1,  # 1st house
            Planet.MOON: 3,     # 3rd house
            Planet.VENUS: 5,    # 5th house
            Planet.MARS: 6,     # 6th house
            Planet.SUN: 9,      # 9th house
            Planet.JUPITER: 11, # 11th house
            Planet.SATURN: 12   # 12th house
        }
        
        if planet in house_joys and house_joys[planet] == house:
            score += config.dignity.joy
        
        # Angular houses
        if house in [1, 4, 7, 10]:
            score += config.dignity.angular
        elif house in [2, 5, 8, 11]:  # Succedent houses
            score += config.dignity.succedent
        elif house in [3, 6, 9, 12]:  # Cadent houses
            score += config.dignity.cadent
        
        # Enhanced solar conditions
        if solar_analysis:
            condition = solar_analysis.condition
            
            if condition == SolarCondition.CAZIMI:
                # Cazimi overrides ALL negative conditions
                if solar_analysis.exact_cazimi:
                    score += config.confidence.solar.exact_cazimi_bonus
                else:
                    score += config.confidence.solar.cazimi_bonus
                    
            elif condition == SolarCondition.COMBUSTION:
                if not solar_analysis.traditional_exception:
                    score -= config.confidence.solar.combustion_penalty
                
            elif condition == SolarCondition.UNDER_BEAMS:
                if not solar_analysis.traditional_exception:
                    score -= config.confidence.solar.under_beams_penalty
        
        return score
    
    def _calculate_enhanced_aspects(self, planets: Dict[Planet, PlanetPosition], 
                                  jd_ut: float) -> List[AspectInfo]:
        """Enhanced aspect calculation with configuration"""
        aspects = []
        planet_list = list(planets.keys())
        config = cfg()
        
        for i, planet1 in enumerate(planet_list):
            for planet2 in planet_list[i+1:]:
                pos1 = planets[planet1]
                pos2 = planets[planet2]
                
                # Calculate angular separation
                angle_diff = abs(pos1.longitude - pos2.longitude)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                
                # Check each traditional aspect
                for aspect_type in Aspect:
                    orb_diff = abs(angle_diff - aspect_type.degrees)
                    
                    # Configured orbs
                    max_orb = aspect_type.orb
                    
                    # Luminary bonuses
                    if Planet.SUN in [planet1, planet2]:
                        max_orb += config.orbs.sun_orb_bonus
                    if Planet.MOON in [planet1, planet2]:
                        max_orb += config.orbs.moon_orb_bonus
                    
                    if orb_diff <= max_orb:
                        # Determine if applying
                        applying = self._is_applying_enhanced(pos1, pos2, aspect_type, jd_ut)
                        
                        # Calculate degrees to exact and timing
                        degrees_to_exact, exact_time = self._calculate_enhanced_degrees_to_exact(
                            pos1, pos2, aspect_type, jd_ut)
                        
                        aspects.append(AspectInfo(
                            planet1=planet1,
                            planet2=planet2,
                            aspect=aspect_type,
                            orb=orb_diff,
                            applying=applying,
                            exact_time=exact_time,
                            degrees_to_exact=degrees_to_exact
                        ))
                        break
        
        return aspects
    
    def _is_applying_enhanced(self, pos1: PlanetPosition, pos2: PlanetPosition, 
                            aspect: Aspect, jd_ut: float) -> bool:
        """Enhanced applying check with directional sign-exit check"""
        
        # Faster planet applies to slower planet
        if abs(pos1.speed) > abs(pos2.speed):
            faster, slower = pos1, pos2
        else:
            faster, slower = pos2, pos1
        
        # Calculate current separation
        separation = faster.longitude - slower.longitude
        
        # Normalize to -180 to +180
        while separation > 180:
            separation -= 360
        while separation < -180:
            separation += 360
        
        # Calculate target separation for this aspect
        target = aspect.degrees
        
        # Check both directions
        targets = [target, -target]
        if target != 0 and target != 180:
            targets.extend([target - 360, -target + 360])
        
        # Find closest target
        closest_target = min(targets, key=lambda t: abs(separation - t))
        current_orb = abs(separation - closest_target)
        
        # Check if aspect will perfect before either planet exits sign
        days_to_perfect = current_orb / abs(faster.speed - slower.speed) if abs(faster.speed - slower.speed) > 0 else float('inf')
        
        # Check days until each planet exits its current sign (directional)
        faster_days_to_exit = days_to_sign_exit(faster.longitude, faster.speed)
        slower_days_to_exit = days_to_sign_exit(slower.longitude, slower.speed)
        
        # If either planet exits sign before perfection, aspect does not apply
        if faster_days_to_exit and days_to_perfect > faster_days_to_exit:
            return False
        if slower_days_to_exit and days_to_perfect > slower_days_to_exit:
            return False
        
        # Calculate future position to confirm applying
        time_increment = cfg().timing.timing_precision_days
        future_separation = separation + (faster.speed - slower.speed) * time_increment
        
        # Normalize future separation
        while future_separation > 180:
            future_separation -= 360
        while future_separation < -180:
            future_separation += 360
        
        future_orb = abs(future_separation - closest_target)
        
        return future_orb < current_orb
    
    def _calculate_enhanced_degrees_to_exact(self, pos1: PlanetPosition, pos2: PlanetPosition, 
                                           aspect: Aspect, jd_ut: float) -> Tuple[float, Optional[datetime.datetime]]:
        """Enhanced degrees and time calculation"""
        
        # Current separation
        separation = abs(pos1.longitude - pos2.longitude)
        if separation > 180:
            separation = 360 - separation
        
        # Orb from exact
        orb_from_exact = abs(separation - aspect.degrees)
        
        # Calculate exact time if planets are applying
        exact_time = None
        if abs(pos1.speed - pos2.speed) > 0:
            days_to_exact = orb_from_exact / abs(pos1.speed - pos2.speed)
            
            max_future_days = cfg().timing.max_future_days
            if days_to_exact < max_future_days:
                try:
                    exact_jd = jd_ut + days_to_exact
                    # Convert back to datetime
                    year, month, day, hour = swe.jdut1_to_utc(exact_jd, 1)  # Flag 1 for Gregorian
                    exact_time = datetime.datetime(int(year), int(month), int(day), 
                                                 int(hour), int((hour % 1) * 60))
                except:
                    exact_time = None
        
        # If already very close, return small value
        if orb_from_exact < 0.1:
            return 0.1, exact_time
        
        return orb_from_exact, exact_time
    
    def _get_sign(self, longitude: float) -> Sign:
        """Get zodiac sign from longitude"""
        longitude = longitude % 360
        for sign in Sign:
            if sign.start_degree <= longitude < (sign.start_degree + 30):
                return sign
        return Sign.PISCES
    
    def _calculate_house_position(self, longitude: float, houses: List[float]) -> int:
        """Calculate house position"""
        longitude = longitude % 360
        
        for i in range(12):
            current_cusp = houses[i] % 360
            next_cusp = houses[(i + 1) % 12] % 360
            
            if current_cusp > next_cusp:  # Crosses 0°
                if longitude >= current_cusp or longitude < next_cusp:
                    return i + 1
            else:
                if current_cusp <= longitude < next_cusp:
                    return i + 1
        
        return 1


class EnhancedTraditionalHoraryJudgmentEngine:
    """Enhanced Traditional horary judgment engine with configuration system"""
    
    def __init__(self):
        self.question_analyzer = TraditionalHoraryQuestionAnalyzer()
        self.calculator = EnhancedTraditionalAstrologicalCalculator()
        self.timezone_manager = TimezoneManager()
        
        # Enhanced location service
        try:
            from geopy.geocoders import Nominatim
            self.geolocator = Nominatim(user_agent="enhanced_horary_astrology")
        except:
            self.geolocator = None
    
    def judge_question(self, question: str, location: str, 
                      date_str: Optional[str] = None, time_str: Optional[str] = None,
                      timezone_str: Optional[str] = None, use_current_time: bool = True,
                      manual_houses: Optional[List[int]] = None,
                      # Legacy override flags (now configurable)
                      ignore_radicality: bool = False,
                      ignore_void_moon: bool = False,
                      ignore_combustion: bool = False,
                      ignore_saturn_7th: bool = False,
                      # Legacy reception weighting (now configurable)
                      exaltation_confidence_boost: float = None) -> Dict[str, Any]:
        """Enhanced Traditional horary judgment with configuration system"""
        
        try:
            # Use configured values if not overridden
            config = cfg()
            if exaltation_confidence_boost is None:
                exaltation_confidence_boost = config.confidence.reception.mutual_exaltation_bonus
            
            # Fail-fast geocoding
            if self.geolocator:
                try:
                    lat, lon, full_location = safe_geocode(location)
                except LocationError as e:
                    raise e
            else:
                raise LocationError("Geocoding service not available")
            
            # Handle datetime with proper timezone support
            if use_current_time:
                dt_local, dt_utc, timezone_used = self.timezone_manager.get_current_time_for_location(lat, lon)
            else:
                if not date_str or not time_str:
                    raise ValueError("Date and time must be provided when not using current time")
                dt_local, dt_utc, timezone_used = self.timezone_manager.parse_datetime_with_timezone(
                    date_str, time_str, timezone_str, lat, lon)
            
            chart = self.calculator.calculate_chart(dt_local, dt_utc, timezone_used, lat, lon, full_location)
            
            # Analyze question traditionally
            question_analysis = self.question_analyzer.analyze_question(question)
            
            # Override with manual houses if provided
            if manual_houses:
                question_analysis["relevant_houses"] = manual_houses
                question_analysis["significators"]["quesited_house"] = manual_houses[1] if len(manual_houses) > 1 else 7
            
            # Apply enhanced judgment with configuration
            judgment = self._apply_enhanced_judgment(
                chart, question_analysis, 
                ignore_radicality, ignore_void_moon, ignore_combustion, ignore_saturn_7th,
                exaltation_confidence_boost)
            
            # Serialize chart data for frontend
            chart_data_serialized = serialize_chart_for_frontend(chart, chart.solar_analyses)

            general_info = self._calculate_general_info(chart)
            considerations = self._calculate_considerations(chart, question_analysis)

            return {
                "question": question,
                "judgment": judgment["result"],
                "confidence": judgment["confidence"],
                "reasoning": judgment["reasoning"],
                
                "chart_data": chart_data_serialized,
                
                "question_analysis": question_analysis,
                "timing": judgment.get("timing"),
                "moon_aspects": self._build_moon_story(chart),  # Enhanced Moon story
                "traditional_factors": judgment.get("traditional_factors", {}),
                "solar_factors": judgment.get("solar_factors", {}),
                "general_info": general_info,
                "considerations": considerations,
                
                # NEW: Enhanced lunar aspects
                "moon_last_aspect": self._serialize_lunar_aspect(chart.moon_last_aspect),
                "moon_next_aspect": self._serialize_lunar_aspect(chart.moon_next_aspect),
                
                "timezone_info": {
                    "local_time": dt_local.isoformat(),
                    "utc_time": dt_utc.isoformat(),
                    "timezone": timezone_used,
                    "location_name": full_location,
                    "coordinates": {
                        "latitude": lat,
                        "longitude": lon
                    }
                }
            }
            
        except LocationError as e:
            return {
                "error": str(e),
                "judgment": "LOCATION_ERROR",
                "confidence": 0,
                "reasoning": [f"Location error: {e}"],
                "error_type": "LocationError"
            }
        except Exception as e:
            import traceback
            logger.error(f"Error in judge_question: {e}")
            logger.error(traceback.format_exc())
            return {
                "error": str(e),
                "judgment": "ERROR",
                "confidence": 0,
                "reasoning": [f"Calculation error: {e}"]
            }
    
    def _serialize_lunar_aspect(self, lunar_aspect: Optional[LunarAspect]) -> Optional[Dict]:
        """Serialize LunarAspect for JSON output"""
        if not lunar_aspect:
            return None
        
        return {
            "planet": lunar_aspect.planet.value,
            "aspect": lunar_aspect.aspect.display_name,
            "orb": round(lunar_aspect.orb, 2),
            "degrees_difference": round(lunar_aspect.degrees_difference, 2),
            "perfection_eta_days": round(lunar_aspect.perfection_eta_days, 2),
            "perfection_eta_description": lunar_aspect.perfection_eta_description,
            "applying": lunar_aspect.applying
        }
    
    # NEW: Enhanced Moon accidental dignity helpers
    def _moon_phase_bonus(self, chart: HoraryChart) -> int:
        """Calculate Moon phase bonus from configuration"""
        
        moon_pos = chart.planets[Planet.MOON]
        sun_pos = chart.planets[Planet.SUN]
        
        # Calculate angular distance (elongation)
        elongation = abs(moon_pos.longitude - sun_pos.longitude)
        if elongation > 180:
            elongation = 360 - elongation
        
        config = cfg()
        
        # Determine phase and return bonus
        if 0 <= elongation < 30:
            return config.moon.phase_bonus.new_moon
        elif 30 <= elongation < 60:
            return config.moon.phase_bonus.waxing_crescent
        elif 60 <= elongation < 120:
            return config.moon.phase_bonus.first_quarter
        elif 120 <= elongation < 150:
            return config.moon.phase_bonus.waxing_gibbous
        elif 150 <= elongation < 210:
            return config.moon.phase_bonus.full_moon
        elif 210 <= elongation < 240:
            return config.moon.phase_bonus.waning_gibbous
        elif 240 <= elongation < 300:
            return config.moon.phase_bonus.last_quarter
        else:  # 300 <= elongation < 360
            return config.moon.phase_bonus.waning_crescent
    
    def _moon_speed_bonus(self, chart: HoraryChart) -> int:
        """Calculate Moon speed bonus from configuration"""
        
        moon_speed = abs(chart.planets[Planet.MOON].speed)
        config = cfg()
        
        if moon_speed < 11.0:
            return config.moon.speed_bonus.very_slow
        elif moon_speed < 12.0:
            return config.moon.speed_bonus.slow
        elif moon_speed < 14.0:
            return config.moon.speed_bonus.average
        elif moon_speed < 15.0:
            return config.moon.speed_bonus.fast
        else:
            return config.moon.speed_bonus.very_fast
    
    def _moon_angularity_bonus(self, chart: HoraryChart) -> int:
        """Calculate Moon angularity bonus from configuration"""
        
        moon_house = chart.planets[Planet.MOON].house
        config = cfg()
        
        if moon_house in [1, 4, 7, 10]:
            return config.moon.angularity_bonus.angular
        elif moon_house in [2, 5, 8, 11]:
            return config.moon.angularity_bonus.succedent
        else:  # cadent houses 3, 6, 9, 12
            return config.moon.angularity_bonus.cadent

    # ---------------- General Info Helpers -----------------

    PLANET_SEQUENCE = [
        Planet.SATURN,
        Planet.JUPITER,
        Planet.MARS,
        Planet.SUN,
        Planet.VENUS,
        Planet.MERCURY,
        Planet.MOON,
    ]

    PLANETARY_DAY_RULERS = {
        0: Planet.MOON,      # Monday
        1: Planet.MARS,      # Tuesday
        2: Planet.MERCURY,   # Wednesday
        3: Planet.JUPITER,   # Thursday
        4: Planet.VENUS,     # Friday
        5: Planet.SATURN,    # Saturday
        6: Planet.SUN        # Sunday
    }

    LUNAR_MANSIONS = [
        "Al Sharatain", "Al Butain", "Al Thurayya", "Al Dabaran",
        "Al Hak'ah", "Al Han'ah", "Al Dhira", "Al Nathrah",
        "Al Tarf", "Al Jabhah", "Al Zubrah", "Al Sarfah",
        "Al Awwa", "Al Simak", "Al Ghafr", "Al Jubana",
        "Iklil", "Al Qalb", "Al Shaula", "Al Na'am",
        "Al Baldah", "Sa'd al Dhabih", "Sa'd Bula", "Sa'd al Su'ud",
        "Sa'd al Akhbiya", "Al Fargh al Mukdim", "Al Fargh al Thani",
        "Batn al Hut"
    ]

    def _get_moon_phase_name(self, chart: HoraryChart) -> str:
        """Return textual Moon phase name"""
        moon_pos = chart.planets[Planet.MOON]
        sun_pos = chart.planets[Planet.SUN]

        elongation = abs(moon_pos.longitude - sun_pos.longitude)
        if elongation > 180:
            elongation = 360 - elongation

        if 0 <= elongation < 30:
            return "New Moon"
        elif 30 <= elongation < 60:
            return "Waxing Crescent"
        elif 60 <= elongation < 120:
            return "First Quarter"
        elif 120 <= elongation < 150:
            return "Waxing Gibbous"
        elif 150 <= elongation < 210:
            return "Full Moon"
        elif 210 <= elongation < 240:
            return "Waning Gibbous"
        elif 240 <= elongation < 300:
            return "Last Quarter"
        else:
            return "Waning Crescent"

    def _moon_speed_category(self, speed: float) -> str:
        """Return a text category for Moon's speed"""
        speed = abs(speed)
        if speed < 11.0:
            return "Very Slow"
        elif speed < 12.0:
            return "Slow"
        elif speed < 14.0:
            return "Average"
        elif speed < 15.0:
            return "Fast"
        else:
            return "Very Fast"

    def _calculate_general_info(self, chart: HoraryChart) -> Dict[str, Any]:
        """Calculate general chart information for frontend display"""
        dt_local = chart.date_time
        weekday = dt_local.weekday()
        day_ruler = self.PLANETARY_DAY_RULERS.get(weekday, Planet.SUN)

        hour_index = dt_local.hour
        start_idx = self.PLANET_SEQUENCE.index(day_ruler)
        hour_ruler = self.PLANET_SEQUENCE[(start_idx + hour_index) % 7]

        moon_pos = chart.planets[Planet.MOON]

        mansion_index = int((moon_pos.longitude % 360) / (360 / 28)) + 1
        mansion_name = self.LUNAR_MANSIONS[mansion_index - 1]

        void_info = self._is_moon_void_of_course_enhanced(chart)

        return {
            "planetary_day": day_ruler.value,
            "planetary_hour": hour_ruler.value,
            "moon_phase": self._get_moon_phase_name(chart),
            "moon_mansion": {
                "number": mansion_index,
                "name": mansion_name,
            },
            "moon_condition": {
                "sign": moon_pos.sign.sign_name,
                "speed": moon_pos.speed,
                "speed_category": self._moon_speed_category(moon_pos.speed),
                "void_of_course": void_info["void"],
                "void_reason": void_info["reason"],
            }
        }

    def _calculate_considerations(self, chart: HoraryChart, question_analysis: Dict) -> Dict[str, Any]:
        """Return standard horary considerations"""
        radicality = self._check_enhanced_radicality(chart)
        moon_void = self._is_moon_void_of_course_enhanced(chart)

        return {
            "radical": radicality["valid"],
            "radical_reason": radicality["reason"],
            "moon_void": moon_void["void"],
            "moon_void_reason": moon_void["reason"],
        }
    
    # [Continue with rest of enhanced methods...]
    # Due to space constraints, I'll highlight the key enhanced methods
    
    def _apply_enhanced_judgment(self, chart: HoraryChart, question_analysis: Dict,
                               ignore_radicality: bool = False, ignore_void_moon: bool = False,
                               ignore_combustion: bool = False, ignore_saturn_7th: bool = False,
                               exaltation_confidence_boost: float = 15.0) -> Dict[str, Any]:
        """Enhanced judgment with configuration system"""
        
        reasoning = []
        config = cfg()
        confidence = config.confidence.base_confidence
        
        # 1. Enhanced radicality with configuration
        if not ignore_radicality:
            radicality = self._check_enhanced_radicality(chart, ignore_saturn_7th)
            if not radicality["valid"]:
                return {
                    "result": "NOT RADICAL",
                    "confidence": 0,
                    "reasoning": [radicality["reason"]],
                    "timing": None
                }
            reasoning.append(f"Radicality: {radicality['reason']}")
        else:
            reasoning.append("Radicality: Bypassed by override")
        
        # 2. Identify significators
        significators = self._identify_significators(chart, question_analysis)
        if not significators["valid"]:
            return {
                "result": "CANNOT JUDGE",
                "confidence": 0,
                "reasoning": reasoning + [significators["reason"]],
                "timing": None
            }
        
        reasoning.append(f"Significators: {significators['description']}")
        
        querent_planet = significators["querent"]
        quesited_planet = significators["quesited"]
        
        # Enhanced solar condition analysis
        solar_factors = self._analyze_enhanced_solar_factors(
            chart, querent_planet, quesited_planet, ignore_combustion)
        
        if solar_factors["significant"]:
            reasoning.append(f"Solar conditions: {solar_factors['summary']}")
            
            # Adjust confidence based on enhanced solar conditions
            if solar_factors["cazimi_count"] > 0:
                confidence += config.confidence.solar.cazimi_bonus
                reasoning.append("Cazimi planets significantly strengthen the judgment")
            elif solar_factors["combustion_count"] > 0 and not ignore_combustion:
                confidence -= config.confidence.solar.combustion_penalty
                reasoning.append("Combusted planets significantly weaken the judgment")
        
        # 3. Enhanced perfection check
        perfection = self._check_enhanced_perfection(chart, querent_planet, quesited_planet, 
                                                   exaltation_confidence_boost)
        
        if perfection["perfects"]:
            result = "YES" if perfection["favorable"] else "NO"
            confidence = min(confidence, perfection["confidence"])
            reasoning.append(f"Perfection: {perfection['reason']}")
            
            # Enhanced timing with real Moon speed
            timing = self._calculate_enhanced_timing(chart, perfection)
            
            return {
                "result": result,
                "confidence": confidence,
                "reasoning": reasoning,
                "timing": timing,
                "traditional_factors": {
                    "perfection_type": perfection["type"],
                    "reception": perfection.get("reception", "none"),
                    "querent_strength": chart.planets[querent_planet].dignity_score,
                    "quesited_strength": chart.planets[quesited_planet].dignity_score
                },
                "solar_factors": solar_factors
            }
        
        # 4. Enhanced denial conditions (retrograde now configurable)
        denial = self._check_enhanced_denial_conditions(chart, querent_planet, quesited_planet)
        if denial["denied"]:
            return {
                "result": "NO",
                "confidence": min(confidence, denial["confidence"]),
                "reasoning": reasoning + [f"Denial: {denial['reason']}"],
                "timing": None,
                "solar_factors": solar_factors
            }
        
        # 5. Enhanced Moon's testimony with configurable void checking
        moon_testimony = self._check_enhanced_moon_testimony(chart, querent_planet, quesited_planet, 
                                                           ignore_void_moon)
        reasoning.append(f"Moon: {moon_testimony['reason']}")
        
        # Apply configured confidence caps
        if moon_testimony["favorable"]:
            result = "YES"
            confidence = min(confidence, config.confidence.lunar_confidence_caps.favorable)
        elif moon_testimony["unfavorable"]:
            result = "NO"
            confidence = min(confidence, config.confidence.lunar_confidence_caps.unfavorable)
        else:
            result = "UNCLEAR"
            confidence = min(confidence, config.confidence.lunar_confidence_caps.neutral)
        
        return {
            "result": result,
            "confidence": confidence,
            "reasoning": reasoning,
            "timing": moon_testimony.get("timing", "Uncertain"),
            "traditional_factors": {
                "moon_void": moon_testimony.get("void_of_course", False),
                "significator_strength": f"Querent: {chart.planets[querent_planet].dignity_score:+d}, Quesited: {chart.planets[quesited_planet].dignity_score:+d}",
                "moon_accidentals": {
                    "phase_bonus": self._moon_phase_bonus(chart),
                    "speed_bonus": self._moon_speed_bonus(chart),
                    "angularity_bonus": self._moon_angularity_bonus(chart)
                }
            },
            "solar_factors": solar_factors
        }
    
    def _check_enhanced_radicality(self, chart: HoraryChart, ignore_saturn_7th: bool = False) -> Dict[str, Any]:
        """Enhanced radicality checks with configuration"""
        
        config = cfg()
        asc_degree = chart.ascendant % 30
        
        # Too early
        if asc_degree < config.radicality.asc_too_early:
            return {
                "valid": False,
                "reason": f"Ascendant too early at {asc_degree:.1f}° - question premature or not mature"
            }
        
        # Too late
        if asc_degree > config.radicality.asc_too_late:
            return {
                "valid": False,
                "reason": f"Ascendant too late at {asc_degree:.1f}° - question too late or already decided"
            }
        
        # Saturn in 7th house (configurable)
        if config.radicality.saturn_7th_enabled and not ignore_saturn_7th:
            saturn_pos = chart.planets[Planet.SATURN]
            if saturn_pos.house == 7:
                return {
                    "valid": False,
                    "reason": "Saturn in 7th house - astrologer may err in judgment (Bonatti)"
                }
        
        # Via Combusta (configurable)
        if config.radicality.via_combusta_enabled:
            moon_pos = chart.planets[Planet.MOON]
            moon_degree_in_sign = moon_pos.longitude % 30
            
            via_combusta = config.radicality.via_combusta
            
            if ((moon_pos.sign == Sign.LIBRA and moon_degree_in_sign > via_combusta.libra_start) or
                (moon_pos.sign == Sign.SCORPIO and via_combusta.scorpio_full) or
                (moon_pos.sign == Sign.CAPRICORN and moon_degree_in_sign > via_combusta.capricorn_start)):
                return {
                    "valid": False,
                    "reason": f"Moon in Via Combusta ({moon_pos.sign.sign_name} {moon_degree_in_sign:.1f}°) - volatile or corrupted matter"
                }
        
        return {
            "valid": True,
            "reason": f"Chart is radical - Ascendant at {asc_degree:.1f}°"
        }
    
    def _check_enhanced_denial_conditions(self, chart: HoraryChart, querent: Planet, quesited: Planet) -> Dict[str, Any]:
        """Enhanced denial conditions with configurable retrograde handling"""
        
        config = cfg()
        
        # Prohibition - Saturn aspects significators before they perfect
        for aspect in chart.aspects:
            if (aspect.planet1 == Planet.SATURN or aspect.planet2 == Planet.SATURN) and aspect.applying:
                other_planet = aspect.planet2 if aspect.planet1 == Planet.SATURN else aspect.planet1
                
                if other_planet in [querent, quesited]:
                    sig_aspect = self._find_applying_aspect(chart, querent, quesited)
                    if sig_aspect and aspect.degrees_to_exact < sig_aspect["degrees_to_exact"]:
                        return {
                            "denied": True,
                            "confidence": config.confidence.denial.prohibition,
                            "reason": f"Prohibition by Saturn - aspects {other_planet.value} before perfection"
                        }
        
        # Enhanced retrograde handling - configurable instead of automatic denial
        querent_pos = chart.planets[querent]
        quesited_pos = chart.planets[quesited]
        
        if not config.retrograde.automatic_denial:
            # Retrograde is now just a penalty, not automatic denial
            if querent_pos.retrograde or quesited_pos.retrograde:
                # This will be handled in dignity scoring instead
                pass
        else:
            # Legacy behavior - automatic denial
            if querent_pos.retrograde or quesited_pos.retrograde:
                return {
                    "denied": True,
                    "confidence": config.confidence.denial.frustration_retrograde,
                    "reason": f"Frustration - {'querent' if querent_pos.retrograde else 'quesited'} significator retrograde"
                }
        
        return {"denied": False}
    
    def _check_enhanced_translation_of_light(self, chart: HoraryChart, querent: Planet, quesited: Planet) -> Dict[str, Any]:
        """Enhanced translation with configurable speed requirement removal"""
        
        config = cfg()
        translation_config = config.moon.translation
        
        # Remove speed prerequisite if configured
        if not translation_config.require_speed_advantage:
            # Check all planets regardless of speed
            for planet, pos in chart.planets.items():
                if planet in [querent, quesited]:
                    continue
                
                # Check aspects to both significators
                aspect_to_querent = self._find_applying_aspect(chart, planet, querent)
                aspect_to_quesited = self._find_applying_aspect(chart, planet, quesited)
                
                # Enhanced: Check separation order if required
                if aspect_to_querent and aspect_to_quesited:
                    if translation_config.require_proper_sequence:
                        # Check proper sequence: separate from one, then apply to other
                        querent_separation = check_aspect_separation_order(
                            chart.planets[querent].longitude, chart.planets[querent].speed,
                            pos.longitude, pos.speed,
                            aspect_to_querent["aspect"].degrees, chart.julian_day)
                        
                        quesited_separation = check_aspect_separation_order(
                            chart.planets[quesited].longitude, chart.planets[quesited].speed,
                            pos.longitude, pos.speed,
                            aspect_to_quesited["aspect"].degrees, chart.julian_day)
                        
                        # Proper translation sequence
                        if (querent_separation["is_separating"] and 
                            aspect_to_quesited["degrees_to_exact"] < aspect_to_querent["degrees_to_exact"]):
                            return {
                                "found": True,
                                "translator": planet,
                                "favorable": True,
                                "sequence": f"separating from {querent.value}, applying to {quesited.value}"
                            }
                        elif (quesited_separation["is_separating"] and 
                              aspect_to_querent["degrees_to_exact"] < aspect_to_quesited["degrees_to_exact"]):
                            return {
                                "found": True,
                                "translator": planet,
                                "favorable": True,
                                "sequence": f"separating from {quesited.value}, applying to {querent.value}"
                            }
                    else:
                        # Simple translation without sequence requirement
                        return {
                            "found": True,
                            "translator": planet,
                            "favorable": True,
                            "sequence": f"connecting {querent.value} and {quesited.value}"
                        }
        
        return {"found": False}
    
    def _check_enhanced_moon_testimony(self, chart: HoraryChart, querent: Planet, quesited: Planet,
                                     ignore_void_moon: bool = False) -> Dict[str, Any]:
        """Enhanced Moon testimony with configurable void-of-course methods"""
        
        moon_pos = chart.planets[Planet.MOON]
        config = cfg()
        
        # Check if Moon is void of course using configured method
        if not ignore_void_moon:
            void_check = self._is_moon_void_of_course_enhanced(chart)
            if void_check["void"] and not void_check["exception"]:
                return {
                    "favorable": False,
                    "unfavorable": True,
                    "reason": f"Moon void of course - {void_check['reason']}",
                    "void_of_course": True,
                    "timing": "Nothing comes of the matter"
                }
        elif ignore_void_moon:
            return {
                "favorable": False,
                "unfavorable": False,
                "reason": "Moon void of course - ignored by override",
                "void_of_course": True,
                "timing": "Uncertain (void Moon overridden)"
            }
        
        # Enhanced Moon analysis with accidental dignities
        phase_bonus = self._moon_phase_bonus(chart)
        speed_bonus = self._moon_speed_bonus(chart)
        angularity_bonus = self._moon_angularity_bonus(chart)
        
        total_moon_bonus = phase_bonus + speed_bonus + angularity_bonus
        adjusted_dignity = moon_pos.dignity_score + total_moon_bonus
        
        # Moon's next aspect using enhanced calculation
        next_aspect = chart.moon_next_aspect
        
        if next_aspect:
            other_planet = next_aspect.planet
            aspect_type = next_aspect.aspect
            
            if other_planet in [querent, quesited]:
                favorable = aspect_type in [Aspect.CONJUNCTION, Aspect.SEXTILE, Aspect.TRINE]
                
                return {
                    "favorable": favorable,
                    "unfavorable": not favorable,
                    "reason": f"Moon next {aspect_type.display_name}s {other_planet.value} (total dignity: {adjusted_dignity:+d})",
                    "timing": next_aspect.perfection_eta_description,
                    "void_of_course": False
                }
        
        # Moon's general condition with enhanced accidentals
        if adjusted_dignity > 0:
            return {
                "favorable": True,
                "unfavorable": False,
                "reason": f"Moon well-dignified in {moon_pos.sign.sign_name} (adjusted dignity: {adjusted_dignity:+d})",
                "void_of_course": False
            }
        elif adjusted_dignity < -3:
            return {
                "favorable": False,
                "unfavorable": True,
                "reason": f"Moon poorly dignified in {moon_pos.sign.sign_name} (adjusted dignity: {adjusted_dignity:+d})",
                "void_of_course": False
            }
        
        return {
            "favorable": False,
            "unfavorable": False,
            "reason": f"Moon testimony neutral (adjusted dignity: {adjusted_dignity:+d})",
            "void_of_course": False
        }
    
    def _is_moon_void_of_course_enhanced(self, chart: HoraryChart) -> Dict[str, Any]:
        """Enhanced void of course check with configurable methods"""
        
        moon_pos = chart.planets[Planet.MOON]
        config = cfg()
        void_rule = config.moon.void_rule
        
        if void_rule == "by_sign":
            return self._void_by_sign_method(chart)
        elif void_rule == "by_orb":
            return self._void_by_orb_method(chart)
        elif void_rule == "lilly":
            return self._void_lilly_method(chart)
        else:
            logger.warning(f"Unknown void rule: {void_rule}, defaulting to by_sign")
            return self._void_by_sign_method(chart)
    
    def _void_by_sign_method(self, chart: HoraryChart) -> Dict[str, Any]:
        """Traditional void-of-course by sign boundary method"""
        
        moon_pos = chart.planets[Planet.MOON]
        config = cfg()
        
        # Calculate degrees left in current sign
        moon_degree_in_sign = moon_pos.longitude % 30
        degrees_left_in_sign = 30 - moon_degree_in_sign
        
        if abs(moon_pos.speed) < config.timing.stationary_speed_threshold:
            return {
                "void": False,
                "exception": False,
                "reason": "Moon stationary - cannot be void of course",
                "degrees_left_in_sign": degrees_left_in_sign
            }
        
        # Find future aspects in current sign
        future_aspects = []
        
        for planet, planet_pos in chart.planets.items():
            if planet == Planet.MOON:
                continue
            
            for aspect_type in Aspect:
                target_moon_positions = self._calculate_aspect_positions(
                    planet_pos.longitude, aspect_type, moon_pos.sign)
                
                for target_position in target_moon_positions:
                    target_degree_in_sign = target_position % 30
                    
                    if target_degree_in_sign > moon_degree_in_sign:
                        degrees_to_target = target_degree_in_sign - moon_degree_in_sign
                        
                        if degrees_to_target < degrees_left_in_sign:
                            future_aspects.append({
                                "planet": planet,
                                "aspect": aspect_type,
                                "target_degree": target_degree_in_sign,
                                "degrees_to_reach": degrees_to_target
                            })
        
        # Traditional exceptions
        void_exceptions = config.moon.void_exceptions
        exceptions = False
        
        if moon_pos.sign == Sign.CANCER and void_exceptions.cancer:
            exceptions = True
        elif moon_pos.sign == Sign.SAGITTARIUS and void_exceptions.sagittarius:
            exceptions = True
        elif moon_pos.sign == Sign.TAURUS and void_exceptions.taurus:
            exceptions = True
        
        has_future_aspects = len(future_aspects) > 0
        is_void = not has_future_aspects
        
        if is_void:
            reason = f"Moon makes no more aspects before leaving {moon_pos.sign.sign_name}"
        else:
            next_aspect = min(future_aspects, key=lambda x: x["degrees_to_reach"])
            reason = f"Moon will {next_aspect['aspect'].display_name.lower()} {next_aspect['planet'].value} at {next_aspect['target_degree']:.1f}° {moon_pos.sign.sign_name}"
        
        if exceptions:
            if moon_pos.sign == Sign.CANCER:
                reason += " (but in own sign - Cancer)"
            elif moon_pos.sign == Sign.SAGITTARIUS:
                reason += " (but in joy - Sagittarius)"
            elif moon_pos.sign == Sign.TAURUS:
                reason += " (but in exaltation - Taurus)"
        
        return {
            "void": is_void,
            "exception": exceptions,
            "reason": reason,
            "degrees_left_in_sign": degrees_left_in_sign
        }
    
    def _void_by_orb_method(self, chart: HoraryChart) -> Dict[str, Any]:
        """Void-of-course by orb method"""
        
        moon_pos = chart.planets[Planet.MOON]
        config = cfg()
        void_orb = config.orbs.void_orb_deg
        
        # Check if Moon is within orb of any aspect
        for planet, planet_pos in chart.planets.items():
            if planet == Planet.MOON:
                continue
            
            separation = abs(moon_pos.longitude - planet_pos.longitude)
            if separation > 180:
                separation = 360 - separation
            
            for aspect_type in Aspect:
                orb_diff = abs(separation - aspect_type.degrees)
                if orb_diff <= void_orb:
                    return {
                        "void": False,
                        "exception": False,
                        "reason": f"Moon within {void_orb}° orb of {aspect_type.display_name} to {planet.value}"
                    }
        
        return {
            "void": True,
            "exception": False,
            "reason": f"Moon not within {void_orb}° of any aspect"
        }
    
    def _void_lilly_method(self, chart: HoraryChart) -> Dict[str, Any]:
        """William Lilly's void-of-course method"""
        
        # Lilly's method: Moon is void if it makes no more aspects before changing sign,
        # except when in Cancer, Taurus, Sagittarius, or Pisces
        moon_pos = chart.planets[Planet.MOON]
        
        # Lilly's exceptions
        lilly_exceptions = [Sign.CANCER, Sign.TAURUS, Sign.SAGITTARIUS, Sign.PISCES]
        exception = moon_pos.sign in lilly_exceptions
        
        # Use sign method for the actual calculation
        void_result = self._void_by_sign_method(chart)
        void_result["exception"] = exception
        
        if exception:
            void_result["reason"] += f" (Lilly exception: {moon_pos.sign.sign_name})"
        
        return void_result
    
    def _calculate_aspect_positions(self, planet_longitude: float, aspect: Aspect, moon_sign: Sign) -> List[float]:
        """Calculate aspect positions (preserved from original)"""
        positions = []
        
        aspect_positions = [
            (planet_longitude + aspect.degrees) % 360,
            (planet_longitude - aspect.degrees) % 360
        ]
        
        sign_start = moon_sign.start_degree
        sign_end = (sign_start + 30) % 360
        
        for pos in aspect_positions:
            pos_normalized = pos % 360
            
            if sign_start < sign_end:
                if sign_start <= pos_normalized < sign_end:
                    positions.append(pos_normalized)
            else:  
                if pos_normalized >= sign_start or pos_normalized < sign_end:
                    positions.append(pos_normalized)
        
        return positions
    
    def _build_moon_story(self, chart: HoraryChart) -> List[Dict]:
        """Enhanced Moon story with real timing calculations"""
        
        moon_pos = chart.planets[Planet.MOON]
        moon_speed = self.calculator.get_real_moon_speed(chart.julian_day)
        
        # Get current aspects
        current_moon_aspects = []
        for aspect in chart.aspects:
            if Planet.MOON in [aspect.planet1, aspect.planet2]:
                other_planet = aspect.planet2 if aspect.planet1 == Planet.MOON else aspect.planet1
                
                # Enhanced timing using real Moon speed
                if aspect.applying:
                    timing_days = aspect.degrees_to_exact / moon_speed if moon_speed > 0 else 0
                    timing_estimate = self._format_timing_description_enhanced(timing_days)
                else:
                    timing_estimate = "Past"
                    timing_days = 0
                
                current_moon_aspects.append({
                    "planet": other_planet.value,
                    "aspect": aspect.aspect.display_name,
                    "orb": float(aspect.orb),
                    "applying": bool(aspect.applying),
                    "status": "applying" if aspect.applying else "separating",
                    "timing": str(timing_estimate),
                    "days_to_perfect": float(timing_days) if aspect.applying else 0.0
                })
        
        # Sort by timing for applying aspects, orb for separating
        current_moon_aspects.sort(key=lambda x: x.get("days_to_perfect", 999) if x["applying"] else x["orb"])
        
        return current_moon_aspects
    
    def _format_timing_description_enhanced(self, days: float) -> str:
        """Enhanced timing description with configuration"""
        if days < 0.5:
            return "Within hours"
        elif days < 1:
            return "Within a day"
        elif days < 7:
            return f"Within {int(days)} days"
        elif days < 30:
            return f"Within {int(days/7)} weeks"
        elif days < 365:
            return f"Within {int(days/30)} months"
        else:
            return "More than a year"
    
    def _calculate_enhanced_timing(self, chart: HoraryChart, perfection: Dict) -> str:
        """Enhanced timing calculation with real Moon speed"""
        
        if "aspect" in perfection:
            degrees = perfection["aspect"]["degrees_to_exact"]
            moon_speed = self.calculator.get_real_moon_speed(chart.julian_day)
            timing_days = degrees / moon_speed
            return self._format_timing_description_enhanced(timing_days)
        
        return "Timing uncertain"
    
    # Preserve all existing helper methods for backward compatibility
    def _identify_significators(self, chart: HoraryChart, question_analysis: Dict) -> Dict[str, Any]:
        """Identify traditional significators (preserved)"""
        
        querent_house = 1
        querent_ruler = chart.house_rulers.get(querent_house)
        
        quesited_house = question_analysis["significators"]["quesited_house"]
        quesited_ruler = chart.house_rulers.get(quesited_house)
        
        if not querent_ruler or not quesited_ruler:
            return {
                "valid": False,
                "reason": "Cannot determine house rulers"
            }
        
        if querent_ruler == quesited_ruler:
            return {
                "valid": False,
                "reason": f"{querent_ruler.value} rules both querent and quesited - seek natural significators"
            }
        
        return {
            "valid": True,
            "querent": querent_ruler,
            "quesited": quesited_ruler,
            "description": f"Querent: {querent_ruler.value} (ruler of {querent_house}), Quesited: {quesited_ruler.value} (ruler of {quesited_house})"
        }
    
    def _find_applying_aspect(self, chart: HoraryChart, planet1: Planet, planet2: Planet) -> Optional[Dict]:
        """Find applying aspect between two planets (preserved)"""
        for aspect in chart.aspects:
            if ((aspect.planet1 == planet1 and aspect.planet2 == planet2) or
                (aspect.planet1 == planet2 and aspect.planet2 == planet1)) and aspect.applying:
                return {
                    "aspect": aspect.aspect,
                    "orb": aspect.orb,
                    "degrees_to_exact": aspect.degrees_to_exact
                }
        return None
    
    def _check_enhanced_perfection(self, chart: HoraryChart, querent: Planet, quesited: Planet,
                                 exaltation_confidence_boost: float = 15.0) -> Dict[str, Any]:
        """Enhanced perfection check with configuration"""
        
        config = cfg()
        querent_pos = chart.planets[querent]
        quesited_pos = chart.planets[quesited]
        
        # 1. Direct perfection with enhanced checks
        direct_aspect = self._find_applying_aspect(chart, querent, quesited)
        if direct_aspect:
            perfects_in_sign = self._enhanced_perfects_in_sign(querent_pos, quesited_pos, direct_aspect, chart)
            
            if perfects_in_sign:
                reception = self._check_enhanced_mutual_reception(chart, querent, quesited)
                
                # Enhanced reception weighting with configuration
                if reception == "mutual_rulership":
                    return {
                        "perfects": True,
                        "type": "direct",
                        "favorable": True,
                        "confidence": config.confidence.perfection.direct_with_mutual_rulership,
                        "reason": f"{direct_aspect['aspect'].display_name} with mutual rulership - unconditional perfection",
                        "reception": reception,
                        "aspect": direct_aspect
                    }
                elif reception == "mutual_exaltation":
                    base_confidence = config.confidence.perfection.direct_with_mutual_exaltation
                    boosted_confidence = min(100, base_confidence + exaltation_confidence_boost)
                    
                    return {
                        "perfects": True,
                        "type": "direct",
                        "favorable": True,
                        "confidence": int(boosted_confidence),
                        "reason": f"{direct_aspect['aspect'].display_name} with mutual exaltation (+{exaltation_confidence_boost}% confidence)",
                        "reception": reception,
                        "aspect": direct_aspect
                    }
                else:
                    favorable = self._is_aspect_favorable(direct_aspect["aspect"], reception)
                    return {
                        "perfects": True,
                        "type": "direct",
                        "favorable": favorable,
                        "confidence": config.confidence.perfection.direct_basic,
                        "reason": f"{direct_aspect['aspect'].display_name} between significators" + 
                                 (f" with {reception}" if reception != "none" else ""),
                        "reception": reception,
                        "aspect": direct_aspect
                    }
        
        # 2. Enhanced translation of light
        translation = self._check_enhanced_translation_of_light(chart, querent, quesited)
        if translation["found"]:
            return {
                "perfects": True,
                "type": "translation",
                "favorable": translation["favorable"],
                "confidence": config.confidence.perfection.translation_of_light,
                "reason": f"Translation of light by {translation['translator'].value} - {translation['sequence']}",
                "translator": translation["translator"]
            }
        
        # 3. Enhanced collection of light
        collection = self._check_enhanced_collection_of_light(chart, querent, quesited)
        if collection["found"]:
            return {
                "perfects": True,
                "type": "collection",
                "favorable": collection["favorable"],
                "confidence": config.confidence.perfection.collection_of_light,
                "reason": f"Collection of light by {collection['collector'].value}",
                "collector": collection["collector"]
            }
        
        # 4. Enhanced mutual reception without aspect
        reception = self._check_enhanced_mutual_reception(chart, querent, quesited)
        if reception == "mutual_rulership":
            return {
                "perfects": True,
                "type": "reception",
                "favorable": True,
                "confidence": config.confidence.perfection.reception_only,
                "reason": "Mutual reception by rulership - unconditional perfection",
                "reception": reception
            }
        elif reception == "mutual_exaltation":
            boosted_confidence = min(100, config.confidence.perfection.reception_only + exaltation_confidence_boost)
            return {
                "perfects": True,
                "type": "reception",
                "favorable": True,
                "confidence": int(boosted_confidence),
                "reason": f"Mutual reception by exaltation (+{exaltation_confidence_boost}% confidence)",
                "reception": reception
            }
        
        return {
            "perfects": False,
            "reason": "No perfection found between significators"
        }
    
    def _check_enhanced_collection_of_light(self, chart: HoraryChart, querent: Planet, quesited: Planet) -> Dict[str, Any]:
        """Enhanced collection with configuration"""
        
        config = cfg()
        collection_config = config.moon.collection
        
        for planet, pos in chart.planets.items():
            if planet in [querent, quesited]:
                continue
            
            # Check if this planet receives aspects from both significators
            aspects_from_querent = self._find_applying_aspect(chart, querent, planet)
            aspects_from_quesited = self._find_applying_aspect(chart, quesited, planet)
            
            if aspects_from_querent and aspects_from_quesited:
                # Check dignity requirement if configured
                if collection_config.require_collector_dignity:
                    if pos.dignity_score < collection_config.minimum_dignity_score:
                        continue
                
                # Enhanced timing enforcement
                querent_pos = chart.planets[querent]
                quesited_pos = chart.planets[quesited]
                
                querent_days_to_sign = days_to_sign_exit(querent_pos.longitude, querent_pos.speed)
                quesited_days_to_sign = days_to_sign_exit(quesited_pos.longitude, quesited_pos.speed)
                
                # Calculate days to perfect both collection aspects
                max_collection_days = max(
                    aspects_from_querent["degrees_to_exact"] / abs(querent_pos.speed - pos.speed) if abs(querent_pos.speed - pos.speed) > 0 else 0,
                    aspects_from_quesited["degrees_to_exact"] / abs(quesited_pos.speed - pos.speed) if abs(quesited_pos.speed - pos.speed) > 0 else 0
                )
                
                # Check if collection completes before sign changes
                valid_collection = True
                if querent_days_to_sign and max_collection_days > querent_days_to_sign:
                    valid_collection = False
                if quesited_days_to_sign and max_collection_days > quesited_days_to_sign:
                    valid_collection = False
                
                if valid_collection:
                    return {
                        "found": True,
                        "collector": planet,
                        "favorable": True,
                        "strength": pos.dignity_score,
                        "timing_valid": True
                    }
        
        return {"found": False}
    
    def _enhanced_perfects_in_sign(self, pos1: PlanetPosition, pos2: PlanetPosition, 
                                  aspect_info: Dict, chart: HoraryChart) -> bool:
        """Enhanced perfection check with directional awareness"""
        
        # Use enhanced sign exit calculations
        days_to_exit_1 = days_to_sign_exit(pos1.longitude, pos1.speed)
        days_to_exit_2 = days_to_sign_exit(pos2.longitude, pos2.speed)
        
        # Estimate days until aspect perfects
        relative_speed = abs(pos1.speed - pos2.speed)
        if relative_speed == 0:
            return False
        
        days_to_perfect = aspect_info["degrees_to_exact"] / relative_speed
        
        # Check if either planet exits sign before perfection
        if days_to_exit_1 and days_to_perfect > days_to_exit_1:
            return False
        if days_to_exit_2 and days_to_perfect > days_to_exit_2:
            return False
        
        return True
    
    def _check_enhanced_mutual_reception(self, chart: HoraryChart, planet1: Planet, planet2: Planet) -> str:
        """Enhanced mutual reception check (preserved logic)"""
        
        pos1 = chart.planets[planet1]
        pos2 = chart.planets[planet2]
        
        # Mutual reception by rulership
        if (pos1.sign.ruler == planet2 and pos2.sign.ruler == planet1):
            return "mutual_rulership"
        
        # Mutual reception by exaltation
        calc = self.calculator
        if (planet1 in calc.exaltations and calc.exaltations[planet1] == pos2.sign and
            planet2 in calc.exaltations and calc.exaltations[planet2] == pos1.sign):
            return "mutual_exaltation"
        
        # Mixed reception
        if ((pos1.sign.ruler == planet2 and planet2 in calc.exaltations and calc.exaltations[planet2] == pos1.sign) or
            (pos2.sign.ruler == planet1 and planet1 in calc.exaltations and calc.exaltations[planet1] == pos2.sign)):
            return "mixed_reception"
        
        return "none"
    
    def _is_aspect_favorable(self, aspect: Aspect, reception: str) -> bool:
        """Determine if aspect is favorable (preserved)"""
        
        favorable_aspects = [Aspect.CONJUNCTION, Aspect.SEXTILE, Aspect.TRINE]
        unfavorable_aspects = [Aspect.SQUARE, Aspect.OPPOSITION]
        
        base_favorable = aspect in favorable_aspects
        
        # Mutual reception can overcome bad aspects
        if reception in ["mutual_rulership", "mutual_exaltation", "mixed_reception"]:
            return True
        
        return base_favorable
    
    def _analyze_enhanced_solar_factors(self, chart: HoraryChart, querent: Planet, quesited: Planet, 
                                      ignore_combustion: bool = False) -> Dict:
        """Enhanced solar factors analysis with configuration - FIXED serialization"""
        
        solar_analyses = getattr(chart, 'solar_analyses', {})
        
        # Count significant solar conditions
        cazimi_planets = []
        combusted_planets = []
        under_beams_planets = []
        
        for planet, analysis in solar_analyses.items():
            if analysis.condition == SolarCondition.CAZIMI:
                cazimi_planets.append(planet)
            elif analysis.condition == SolarCondition.COMBUSTION and not ignore_combustion:
                combusted_planets.append(planet)
            elif analysis.condition == SolarCondition.UNDER_BEAMS and not ignore_combustion:
                under_beams_planets.append(planet)
        
        # Build summary with override notes
        summary_parts = []
        if cazimi_planets:
            summary_parts.append(f"Cazimi: {', '.join(p.value for p in cazimi_planets)}")
        if combusted_planets:
            summary_parts.append(f"Combusted: {', '.join(p.value for p in combusted_planets)}")
        if under_beams_planets:
            summary_parts.append(f"Under Beams: {', '.join(p.value for p in under_beams_planets)}")
        
        if ignore_combustion and (combusted_planets or under_beams_planets):
            summary_parts.append("(Combustion effects ignored by override)")
        
        # Convert detailed analyses for JSON serialization
        detailed_analyses_serializable = {}
        for planet, analysis in solar_analyses.items():
            detailed_analyses_serializable[planet.value] = {
                "planet": planet.value,
                "distance_from_sun": round(analysis.distance_from_sun, 4),
                "condition": analysis.condition.condition_name,
                "dignity_modifier": analysis.condition.dignity_modifier if not (ignore_combustion and analysis.condition in [SolarCondition.COMBUSTION, SolarCondition.UNDER_BEAMS]) else 0,
                "description": analysis.condition.description,
                "exact_cazimi": bool(analysis.exact_cazimi),
                "traditional_exception": bool(analysis.traditional_exception),
                "effect_ignored": ignore_combustion and analysis.condition in [SolarCondition.COMBUSTION, SolarCondition.UNDER_BEAMS]
            }
        
        return {
            "significant": len(summary_parts) > 0,
            "summary": "; ".join(summary_parts) if summary_parts else "No significant solar conditions",
            "cazimi_count": len(cazimi_planets),
            "combustion_count": len(combusted_planets) if not ignore_combustion else 0,
            "under_beams_count": len(under_beams_planets) if not ignore_combustion else 0,
            "detailed_analyses": detailed_analyses_serializable,
            "combustion_ignored": ignore_combustion
        }


# NEW: Top-level HoraryEngine class as required
class HoraryEngine:
    """
    Top-level Horary Engine providing the required judge(question, settings) interface
    This is the main entry point as specified in the requirements
    """
    
    def __init__(self):
        self.engine = EnhancedTraditionalHoraryJudgmentEngine()
    
    def judge(self, question: str, settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for horary judgment as specified in requirements
        
        Args:
            question: The horary question to judge
            settings: Dictionary containing all judgment settings
        
        Returns:
            Dictionary with judgment result and analysis
        """
        
        # Extract settings with defaults
        location = settings.get("location", "London, England")
        date_str = settings.get("date")
        time_str = settings.get("time") 
        timezone_str = settings.get("timezone")
        use_current_time = settings.get("use_current_time", True)
        manual_houses = settings.get("manual_houses")
        
        # Extract override flags
        ignore_radicality = settings.get("ignore_radicality", False)
        ignore_void_moon = settings.get("ignore_void_moon", False)
        ignore_combustion = settings.get("ignore_combustion", False)
        ignore_saturn_7th = settings.get("ignore_saturn_7th", False)
        
        # Extract reception weighting (now configurable)
        exaltation_confidence_boost = settings.get("exaltation_confidence_boost")
        if exaltation_confidence_boost is None:
            # Use configured default
            exaltation_confidence_boost = cfg().confidence.reception.mutual_exaltation_bonus
        
        # Call the enhanced engine
        return self.engine.judge_question(
            question=question,
            location=location,
            date_str=date_str,
            time_str=time_str,
            timezone_str=timezone_str,
            use_current_time=use_current_time,
            manual_houses=manual_houses,
            ignore_radicality=ignore_radicality,
            ignore_void_moon=ignore_void_moon,
            ignore_combustion=ignore_combustion,
            ignore_saturn_7th=ignore_saturn_7th,
            exaltation_confidence_boost=exaltation_confidence_boost
        )


# Preserve backward compatibility
TraditionalAstrologicalCalculator = EnhancedTraditionalAstrologicalCalculator
TraditionalHoraryJudgmentEngine = EnhancedTraditionalHoraryJudgmentEngine


# Preserve existing serialization functions with enhancements
def serialize_planet_with_solar(planet_pos: PlanetPosition, solar_analysis: Optional[SolarAnalysis] = None) -> Dict:
    """Enhanced helper function to serialize planet data including solar conditions"""
    data = {
        'longitude': float(planet_pos.longitude),
        'latitude': float(planet_pos.latitude),
        'house': int(planet_pos.house),
        'sign': planet_pos.sign.sign_name,
        'dignity_score': int(planet_pos.dignity_score),
        'retrograde': bool(planet_pos.retrograde),
        'speed': float(planet_pos.speed),
        'degree_in_sign': float(planet_pos.longitude % 30)
    }
    
    if solar_analysis:
        data['solar_condition'] = {
            'condition': solar_analysis.condition.condition_name,
            'distance_from_sun': round(solar_analysis.distance_from_sun, 4),
            'dignity_effect': solar_analysis.condition.dignity_modifier,
            'description': solar_analysis.condition.description,
            'exact_cazimi': solar_analysis.exact_cazimi,
            'traditional_exception': solar_analysis.traditional_exception
        }
    
    return data


def serialize_chart_for_frontend(chart: HoraryChart, solar_analyses: Dict[Planet, SolarAnalysis] = None) -> Dict[str, Any]:
    """Enhanced serialize HoraryChart object for frontend consumption"""
    
    planets_data = {}
    for planet, planet_pos in chart.planets.items():
        solar_analysis = solar_analyses.get(planet) if solar_analyses else None
        planets_data[planet.value] = serialize_planet_with_solar(planet_pos, solar_analysis)
    
    aspects_data = []
    for aspect in chart.aspects:
        aspects_data.append({
            'planet1': aspect.planet1.value,
            'planet2': aspect.planet2.value,
            'aspect': aspect.aspect.display_name,
            'orb': round(aspect.orb, 2),
            'applying': aspect.applying,
            'degrees_to_exact': round(aspect.degrees_to_exact, 2),
            'exact_time': aspect.exact_time.isoformat() if aspect.exact_time else None
        })
    
    # Enhanced solar conditions summary with proper enum handling
    solar_conditions_summary = None
    if solar_analyses:
        cazimi_planets = []
        combusted_planets = []
        under_beams_planets = []
        free_planets = []
        
        for planet, analysis in solar_analyses.items():
            planet_info = {
                'planet': planet.value,
                'distance_from_sun': round(analysis.distance_from_sun, 4)
            }
            
            if analysis.condition == SolarCondition.CAZIMI:
                planet_info['exact_cazimi'] = analysis.exact_cazimi
                planet_info['dignity_effect'] = analysis.condition.dignity_modifier
                cazimi_planets.append(planet_info)
            elif analysis.condition == SolarCondition.COMBUSTION:
                planet_info['traditional_exception'] = analysis.traditional_exception
                planet_info['dignity_effect'] = analysis.condition.dignity_modifier
                combusted_planets.append(planet_info)
            elif analysis.condition == SolarCondition.UNDER_BEAMS:
                planet_info['dignity_effect'] = analysis.condition.dignity_modifier
                under_beams_planets.append(planet_info)
            else:  # FREE
                free_planets.append(planet_info)
        
        solar_conditions_summary = {
            'cazimi_planets': cazimi_planets,
            'combusted_planets': combusted_planets,
            'under_beams_planets': under_beams_planets,
            'free_planets': free_planets,
            'significant_conditions': len(cazimi_planets) + len(combusted_planets) + len(under_beams_planets)
        }
    
    # Enhanced serialization with new lunar aspects
    result = {
        'planets': planets_data,
        'aspects': aspects_data,
        'houses': [round(cusp, 2) for cusp in chart.houses],
        'house_rulers': {str(house): ruler.value for house, ruler in chart.house_rulers.items()},
        'ascendant': round(chart.ascendant, 4),
        'midheaven': round(chart.midheaven, 4),
        'solar_conditions_summary': solar_conditions_summary,
        
        'timezone_info': {
            'local_time': chart.date_time.isoformat(),
            'utc_time': chart.date_time_utc.isoformat(),
            'timezone': chart.timezone_info,
            'location_name': chart.location_name,
            'coordinates': {
                'latitude': chart.location[0],
                'longitude': chart.location[1]
            }
        }
    }
    
    # Add enhanced lunar aspects if available
    if hasattr(chart, 'moon_last_aspect') and chart.moon_last_aspect:
        result['moon_last_aspect'] = {
            'planet': chart.moon_last_aspect.planet.value,
            'aspect': chart.moon_last_aspect.aspect.display_name,
            'orb': round(chart.moon_last_aspect.orb, 2),
            'degrees_difference': round(chart.moon_last_aspect.degrees_difference, 2),
            'perfection_eta_days': round(chart.moon_last_aspect.perfection_eta_days, 2),
            'perfection_eta_description': chart.moon_last_aspect.perfection_eta_description,
            'applying': chart.moon_last_aspect.applying
        }
    
    if hasattr(chart, 'moon_next_aspect') and chart.moon_next_aspect:
        result['moon_next_aspect'] = {
            'planet': chart.moon_next_aspect.planet.value,
            'aspect': chart.moon_next_aspect.aspect.display_name,
            'orb': round(chart.moon_next_aspect.orb, 2),
            'degrees_difference': round(chart.moon_next_aspect.degrees_difference, 2),
            'perfection_eta_days': round(chart.moon_next_aspect.perfection_eta_days, 2),
            'perfection_eta_description': chart.moon_next_aspect.perfection_eta_description,
            'applying': chart.moon_next_aspect.applying
        }
    
    return result


# Helper functions for testing and development
def load_test_config(config_path: str) -> None:
    """Load test configuration for unit testing"""
    import os
    from horary_config import HoraryConfig
    
    os.environ['HORARY_CONFIG'] = config_path
    HoraryConfig.reset()


def validate_configuration() -> Dict[str, Any]:
    """Validate current configuration and return status"""
    try:
        config = get_config()
        config.validate_required_keys()
        
        return {
            "valid": True,
            "config_file": os.environ.get('HORARY_CONFIG', 'horary_constants.yaml'),
            "message": "Configuration is valid"
        }
    except HoraryError as e:
        return {
            "valid": False,
            "error": str(e),
            "message": "Configuration validation failed"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": str(e),
            "message": "Unexpected error during configuration validation"
        }


def get_configuration_info() -> Dict[str, Any]:
    """Get information about current configuration"""
    try:
        config = get_config()
        
        return {
            "config_file": os.environ.get('HORARY_CONFIG', 'horary_constants.yaml'),
            "timing": {
                "default_moon_speed_fallback": config.get('timing.default_moon_speed_fallback'),
                "max_future_days": config.get('timing.max_future_days')
            },
            "moon": {
                "void_rule": config.get('moon.void_rule'),
                "translation_require_speed": config.get('moon.translation.require_speed_advantage', True)
            },
            "confidence": {
                "base_confidence": config.get('confidence.base_confidence'),
                "lunar_favorable_cap": config.get('confidence.lunar_confidence_caps.favorable'),
                "lunar_unfavorable_cap": config.get('confidence.lunar_confidence_caps.unfavorable')
            },
            "retrograde": {
                "automatic_denial": config.get('retrograde.automatic_denial', True),
                "dignity_penalty": config.get('retrograde.dignity_penalty', -2)
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "message": "Failed to get configuration info"
        }


# Enhanced error handling
class HoraryCalculationError(Exception):
    """Exception raised for calculation errors in horary engine"""
    pass


class HoraryConfigurationError(Exception):
    """Exception raised for configuration errors in horary engine"""
    pass


# Logging setup for the module
def setup_horary_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    """Setup logging for horary engine"""
    import logging
    
    # Configure logger
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    logger.info(f"Horary engine logging configured at {level} level")


# Performance monitoring helpers
def profile_calculation(func):
    """Decorator to profile calculation performance"""
    import time
    import functools
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            
            # Add performance info to result if it's a dict
            if isinstance(result, dict):
                result['_performance'] = {
                    'function': func.__name__,
                    'execution_time_seconds': execution_time
                }
            
            return result
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.4f} seconds: {e}")
            raise
    
    return wrapper


# Module version and compatibility info
__version__ = "2.0.0"
__compatibility__ = {
    "api_version": "1.0",
    "config_version": "1.0",
    "breaking_changes": [],
    "deprecated": []
}


def get_engine_info() -> Dict[str, Any]:
    """Get information about the horary engine"""
    return {
        "version": __version__,
        "compatibility": __compatibility__,
        "configuration_status": validate_configuration(),
        "features": {
            "enhanced_moon_testimony": True,
            "configurable_orbs": True,
            "real_moon_speed": True,
            "enhanced_solar_conditions": True,
            "configurable_void_moon": True,
            "retrograde_penalty_mode": True,
            "translation_without_speed": True,
            "lunar_accidental_dignities": True
        }
    }


# Initialize logging on module import
if os.environ.get('HORARY_DISABLE_AUTO_LOGGING') != 'true':
    try:
        setup_horary_logging()
    except Exception as e:
        print(f"Warning: Failed to setup logging: {e}")


# Validate configuration on module import (unless disabled)
if os.environ.get('HORARY_CONFIG_SKIP_VALIDATION') != 'true':
    validation_result = validate_configuration()
    if not validation_result["valid"]:
        logger.warning(f"Configuration validation warning: {validation_result['error']}")
        # Don't raise exception to allow module import - let individual functions handle it