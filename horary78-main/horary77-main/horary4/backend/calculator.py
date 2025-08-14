# -*- coding: utf-8 -*-
"""Astrological calculation utilities for the horary engine."""

import datetime
import math
import logging
from typing import Dict, List, Tuple, Optional, Any

import swisseph as swe

from horary_config import cfg
from _horary_math import (
    calculate_next_station_time, calculate_future_longitude,
    calculate_sign_boundary_longitude, days_to_sign_exit,
    calculate_elongation, is_planet_oriental, sun_altitude_at_civil_twilight,
    calculate_moon_variable_speed, check_aspect_separation_order,
    LocationError, safe_geocode, normalize_longitude, degrees_to_dms
)
from models import (
    Planet, Aspect, Sign, SolarCondition, SolarAnalysis,
    PlanetPosition, AspectInfo, LunarAspect, Significator, HoraryChart
)

logger = logging.getLogger(__name__)

class EnhancedTraditionalAstrologicalCalculator:
    """Enhanced Traditional astrological calculations with configuration system"""
    
    def __init__(self):
        # Set Swiss Ephemeris path
        swe.set_ephe_path('')
        
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


