"""
Horary Engine Configuration Loader
Loads and caches configuration from YAML file with lazy singleton pattern

Created for horary_engine.py refactor
"""

import os
import yaml
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HoraryError(Exception):
    """Custom exception for horary engine configuration errors"""
    pass


class HoraryConfig:
    """Lazy singleton configuration loader for horary constants"""
    
    _instance: Optional['HoraryConfig'] = None
    _config: Optional[SimpleNamespace] = None
    
    def __new__(cls) -> 'HoraryConfig':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        
        # Allow override via environment variable for testing
        config_path = os.environ.get('HORARY_CONFIG')
        
        if config_path:
            config_file = Path(config_path)
        else:
            # Default to horary_constants.yaml in same directory as this file
            config_file = Path(__file__).parent / 'horary_constants.yaml'
        
        try:
            if not config_file.exists():
                raise HoraryError(f"Configuration file not found: {config_file}")
            
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            if not config_dict:
                raise HoraryError(f"Empty or invalid configuration file: {config_file}")
            
            # Convert nested dict to nested SimpleNamespace for dot notation access
            self._config = self._dict_to_namespace(config_dict)
            
            logger.info(f"Loaded horary configuration from {config_file}")
            
        except yaml.YAMLError as e:
            raise HoraryError(f"Invalid YAML in configuration file {config_file}: {e}")
        except Exception as e:
            raise HoraryError(f"Failed to load configuration from {config_file}: {e}")
    
    def _dict_to_namespace(self, d: Dict[str, Any]) -> SimpleNamespace:
        """Convert nested dictionary to nested SimpleNamespace"""
        if isinstance(d, dict):
            return SimpleNamespace(**{k: self._dict_to_namespace(v) for k, v in d.items()})
        elif isinstance(d, list):
            return [self._dict_to_namespace(item) for item in d]
        else:
            return d
    
    @property
    def config(self) -> SimpleNamespace:
        """Get the configuration namespace"""
        if self._config is None:
            self._load_config()
        return self._config
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation path
        
        Args:
            key_path: Dot-separated path like 'timing.default_moon_speed_fallback'
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            value = self.config
            for key in key_path.split('.'):
                value = getattr(value, key)
            return value
        except AttributeError:
            if default is not None:
                return default
            raise HoraryError(f"Configuration key not found: {key_path}")
    
    def require(self, key_path: str) -> Any:
        """
        Get required configuration value, raise error if missing
        
        Args:
            key_path: Dot-separated path like 'timing.default_moon_speed_fallback'
            
        Returns:
            Configuration value
            
        Raises:
            HoraryError: If key is missing
        """
        try:
            value = self.config
            for key in key_path.split('.'):
                value = getattr(value, key)
            return value
        except AttributeError:
            raise HoraryError(f"Required configuration key missing: {key_path}")
    
    def validate_required_keys(self) -> None:
        """Validate that all required configuration keys are present"""
        
        required_keys = [
            'timing.default_moon_speed_fallback',
            'orbs.conjunction',
            'moon.void_rule',
            'confidence.base_confidence',
            'confidence.lunar_confidence_caps.favorable',
            'confidence.lunar_confidence_caps.unfavorable',
            'radicality.asc_too_early',
            'radicality.asc_too_late'
        ]
        
        missing_keys = []
        for key in required_keys:
            try:
                self.require(key)
            except HoraryError:
                missing_keys.append(key)
        
        if missing_keys:
            raise HoraryError(f"Missing required configuration keys: {missing_keys}")
    
    @classmethod
    def reset(cls) -> None:
        """Reset singleton for testing"""
        cls._instance = None
        cls._config = None


# Global configuration instance
def get_config() -> HoraryConfig:
    """Get the global configuration instance"""
    return HoraryConfig()


# Convenience function for quick access
def cfg() -> SimpleNamespace:
    """Get configuration namespace directly"""
    return get_config().config


# Validate configuration on import (unless in test environment)
if os.environ.get('HORARY_CONFIG_SKIP_VALIDATION') != 'true':
    try:
        get_config().validate_required_keys()
    except HoraryError as e:
        logger.error(f"Configuration validation failed: {e}")
        # Don't raise here to allow module import - let individual functions handle missing config# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

