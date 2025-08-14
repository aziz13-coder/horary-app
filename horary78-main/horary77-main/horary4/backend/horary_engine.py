# -*- coding: utf-8 -*-
"""Backward-compatible wrapper for the horary astrology engine."""

from models import (
    Planet, Aspect, Sign, SolarCondition, SolarAnalysis,
    PlanetPosition, AspectInfo, LunarAspect, Significator, HoraryChart,
)
from question_analysis import TraditionalHoraryQuestionAnalyzer
from calculator import EnhancedTraditionalAstrologicalCalculator
from judgment_engine import (
    TimezoneManager,
    EnhancedTraditionalHoraryJudgmentEngine,
    HoraryEngine,
    load_test_config,
    validate_configuration,
    get_configuration_info,
    HoraryCalculationError,
    HoraryConfigurationError,
    setup_horary_logging,
    profile_calculation,
    get_engine_info,
)
from serialization import serialize_planet_with_solar, serialize_chart_for_frontend
from _horary_math import LocationError

# Backward-compatible aliases
TraditionalAstrologicalCalculator = EnhancedTraditionalAstrologicalCalculator
TraditionalHoraryJudgmentEngine = EnhancedTraditionalHoraryJudgmentEngine

