# -*- coding: utf-8 -*-
"""Serialization helpers for the horary astrology engine."""

from typing import Dict, Any, Optional

from models import Planet, SolarAnalysis, PlanetPosition, HoraryChart, SolarCondition

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


