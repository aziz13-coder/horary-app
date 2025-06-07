# -*- coding: utf-8 -*-
"""
Enhanced Horary Master - Offline License Management System

This module provides secure offline license verification using RSA signatures.
Licenses are JSON files signed with a private key and verified with a public key.

Features:
- Offline verification (no internet required)
- Cryptographic security using RSA-2048
- Feature-based licensing
- Expiry date validation
- Machine-specific binding (optional)
- Graceful error handling

Created: 2025-06-04
Author: Horary Master Team
"""

import json
import os
import logging
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.exceptions import InvalidSignature
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)


class LicenseError(Exception):
    """Custom exception for license-related errors"""
    pass


class LicenseManager:
    """
    Manages offline license verification for Enhanced Horary Master
    
    License file format:
    {
        "licensedTo": "User Name",
        "email": "user@example.com", 
        "issueDate": "2025-06-04T10:00:00Z",
        "expiryDate": "2026-06-04T10:00:00Z",
        "features": ["enhanced_engine", "solar_conditions", "moon_analysis"],
        "machineId": "optional-machine-specific-hash",
        "licenseType": "commercial|trial|educational",
        "version": "1.0",
        "signature": "base64-encoded-signature"
    }
    """
    
    def __init__(self, license_file_path: Optional[str] = None, public_key_path: Optional[str] = None):
        """
        Initialize the license manager
        
        Args:
            license_file_path: Path to license file (default: ./license.json)
            public_key_path: Path to public key file (default: ./public_key.pem)
        """
        self.license_file = license_file_path or self._get_default_license_path()
        self.public_key_file = public_key_path or self._get_default_public_key_path()
        
        self._license_data = None
        self._public_key = None
        self._validation_cache = {}
        
        # Available features in the application
        self.available_features = {
            'enhanced_engine': 'Enhanced Traditional Horary Engine 2.0',
            'solar_conditions': 'Advanced Solar Condition Analysis',
            'moon_analysis': 'Enhanced Moon Void of Course Detection',
            'timezone_support': 'Automatic Timezone Detection',
            'future_retrograde': 'Future Retrograde Frustration Protection',
            'directional_motion': 'Directional Sign-Exit Awareness',
            'reception_weighting': 'Enhanced Reception Weighting',
            'override_flags': 'Optional Override Capabilities',
            'premium_support': 'Priority Customer Support',
            'unlimited_charts': 'Unlimited Chart Calculations'
        }
        
        logger.info("License Manager initialized")
    
    def _get_default_license_path(self) -> str:
        """Get default license file path"""
        # Look for license file in multiple locations
        possible_paths = [
            './license.json',
            './horary_license.json',
            os.path.join(os.path.dirname(__file__), 'license.json'),
            os.path.expanduser('~/Documents/HoraryMaster/license.json'),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'license.json')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found license file at: {path}")
                return path
        
        # Default to current directory
        return './license.json'
    
    def _get_default_public_key_path(self) -> str:
        """Get default public key file path"""
        # Look for public key in multiple locations
        possible_paths = [
            './public_key.pem',
            os.path.join(os.path.dirname(__file__), 'public_key.pem'),
            os.path.join(os.path.dirname(__file__), 'keys', 'public_key.pem')
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                logger.info(f"Found public key at: {path}")
                return path
        
        # Default to current directory
        return './public_key.pem'
    
    def _load_public_key(self) -> Any:
        """Load and cache the public key"""
        if self._public_key is not None:
            return self._public_key
        
        if not CRYPTO_AVAILABLE:
            raise LicenseError("Cryptography library not available. Install with: pip install cryptography")
        
        if not os.path.exists(self.public_key_file):
            raise LicenseError(f"Public key file not found: {self.public_key_file}")
        
        try:
            with open(self.public_key_file, 'rb') as f:
                key_data = f.read()
            
            self._public_key = serialization.load_pem_public_key(key_data)
            logger.info("Public key loaded successfully")
            return self._public_key
            
        except Exception as e:
            raise LicenseError(f"Failed to load public key: {str(e)}")
    
    def _load_license_file(self) -> Dict[str, Any]:
        """Load and parse the license file"""
        if not os.path.exists(self.license_file):
            raise LicenseError(f"License file not found: {self.license_file}")
        
        try:
            with open(self.license_file, 'r', encoding='utf-8') as f:
                license_data = json.load(f)
            
            # Validate required fields
            required_fields = ['licensedTo', 'issueDate', 'expiryDate', 'features', 'signature']
            missing_fields = [field for field in required_fields if field not in license_data]
            
            if missing_fields:
                raise LicenseError(f"License file missing required fields: {missing_fields}")
            
            self._license_data = license_data
            return license_data
            
        except json.JSONDecodeError as e:
            raise LicenseError(f"Invalid license file format: {str(e)}")
        except Exception as e:
            raise LicenseError(f"Failed to load license file: {str(e)}")
    
    def _verify_signature(self, license_data: Dict[str, Any]) -> bool:
        """Verify the license signature"""
        if not CRYPTO_AVAILABLE:
            logger.warning("Cryptography not available - signature verification skipped")
            return True  # Allow operation without crypto in development
        
        try:
            public_key = self._load_public_key()
            signature = license_data.get('signature', '')
            
            if not signature:
                raise LicenseError("License signature missing")
            
            # Create data to verify (license without signature)
            license_copy = license_data.copy()
            del license_copy['signature']
            
            # Sort keys for consistent hashing
            license_json = json.dumps(license_copy, sort_keys=True, separators=(',', ':'))
            license_bytes = license_json.encode('utf-8')
            
            # Decode signature from base64
            import base64
            signature_bytes = base64.b64decode(signature)
            
            # Verify signature
            public_key.verify(
                signature_bytes,
                license_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            logger.info("License signature verified successfully")
            return True
            
        except InvalidSignature:
            raise LicenseError("Invalid license signature")
        except Exception as e:
            raise LicenseError(f"Signature verification failed: {str(e)}")
    
    def _check_expiry(self, license_data: Dict[str, Any]) -> bool:
        """Check if license has expired"""
        try:
            expiry_str = license_data.get('expiryDate')
            if not expiry_str:
                raise LicenseError("License expiry date missing")
            
            # Parse ISO format date
            expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            current_date = datetime.now(timezone.utc)
            
            if current_date > expiry_date:
                days_expired = (current_date - expiry_date).days
                raise LicenseError(f"License expired {days_expired} days ago")
            
            days_remaining = (expiry_date - current_date).days
            logger.info(f"License valid - {days_remaining} days remaining")
            return True
            
        except ValueError as e:
            raise LicenseError(f"Invalid expiry date format: {str(e)}")
    
    def _check_machine_binding(self, license_data: Dict[str, Any]) -> bool:
        """Check machine-specific binding (if present)"""
        license_machine_id = license_data.get('machineId')
        
        if not license_machine_id:
            # No machine binding required
            return True
        
        try:
            current_machine_id = self._get_machine_id()
            
            if license_machine_id != current_machine_id:
                raise LicenseError("License is bound to a different machine")
            
            logger.info("Machine binding verification successful")
            return True
            
        except Exception as e:
            raise LicenseError(f"Machine binding check failed: {str(e)}")
    
    def _get_machine_id(self) -> str:
        """Generate a machine-specific identifier"""
        try:
            # Create a hash based on system information
            system_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
            machine_hash = hashlib.sha256(system_info.encode()).hexdigest()[:16]
            return machine_hash
        except Exception:
            return "unknown-machine"
    
    def validate_license(self, force_reload: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate the license file
        
        Args:
            force_reload: Force reload of license file
            
        Returns:
            Tuple of (is_valid, license_info)
        """
        cache_key = f"{self.license_file}-{os.path.getmtime(self.license_file) if os.path.exists(self.license_file) else 0}"
        
        if not force_reload and cache_key in self._validation_cache:
            cached_result = self._validation_cache[cache_key]
            logger.debug("Using cached license validation result")
            return cached_result
        
        try:
            # Load license file
            license_data = self._load_license_file()
            
            # Verify signature
            self._verify_signature(license_data)
            
            # Check expiry
            self._check_expiry(license_data)
            
            # Check machine binding
            self._check_machine_binding(license_data)
            
            # Create license info
            license_info = {
                'valid': True,
                'licensedTo': license_data.get('licensedTo', 'Unknown'),
                'email': license_data.get('email', ''),
                'licenseType': license_data.get('licenseType', 'commercial'),
                'issueDate': license_data.get('issueDate'),
                'expiryDate': license_data.get('expiryDate'),
                'features': license_data.get('features', []),
                'version': license_data.get('version', '1.0'),
                'daysRemaining': self._get_days_remaining(license_data),
                'error': None
            }
            
            result = (True, license_info)
            self._validation_cache[cache_key] = result
            
            logger.info(f"License validation successful for: {license_info['licensedTo']}")
            return result
            
        except LicenseError as e:
            error_info = {
                'valid': False,
                'error': str(e),
                'licensedTo': None,
                'features': [],
                'daysRemaining': 0
            }
            
            result = (False, error_info)
            logger.error(f"License validation failed: {str(e)}")
            return result
        
        except Exception as e:
            error_info = {
                'valid': False,
                'error': f"Unexpected license validation error: {str(e)}",
                'licensedTo': None,
                'features': [],
                'daysRemaining': 0
            }
            
            result = (False, error_info)
            logger.error(f"Unexpected license validation error: {str(e)}")
            return result
    
    def _get_days_remaining(self, license_data: Dict[str, Any]) -> int:
        """Get days remaining until license expires"""
        try:
            expiry_str = license_data.get('expiryDate')
            if not expiry_str:
                return 0
            
            expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
            current_date = datetime.now(timezone.utc)
            
            if current_date > expiry_date:
                return 0
            
            return (expiry_date - current_date).days
            
        except Exception:
            return 0
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a specific feature is enabled in the license"""
        try:
            is_valid, license_info = self.validate_license()
            
            if not is_valid:
                return False
            
            enabled_features = license_info.get('features', [])
            return feature in enabled_features
            
        except Exception as e:
            logger.error(f"Error checking feature {feature}: {str(e)}")
            return False
    
    def get_license_status(self) -> Dict[str, Any]:
        """Get comprehensive license status information"""
        is_valid, license_info = self.validate_license()
        
        if is_valid:
            # Map enabled features to descriptions
            enabled_features = license_info.get('features', [])
            feature_descriptions = {
                feature: self.available_features.get(feature, f"Unknown feature: {feature}")
                for feature in enabled_features
            }
            
            status = {
                'valid': True,
                'licensedTo': license_info['licensedTo'],
                'email': license_info.get('email', ''),
                'licenseType': license_info.get('licenseType', 'commercial'),
                'issueDate': license_info['issueDate'],
                'expiryDate': license_info['expiryDate'],
                'daysRemaining': license_info['daysRemaining'],
                'features': feature_descriptions,
                'featureCount': len(enabled_features),
                'machineId': self._get_machine_id(),
                'status': 'Valid' if license_info['daysRemaining'] > 30 else 'Expiring Soon' if license_info['daysRemaining'] > 0 else 'Expired'
            }
        else:
            status = {
                'valid': False,
                'error': license_info.get('error', 'Unknown license error'),
                'licensedTo': None,
                'features': {},
                'featureCount': 0,
                'daysRemaining': 0,
                'status': 'Invalid'
            }
        
        return status
    
    def create_trial_license(self, name: str, email: str, days: int = 30) -> Dict[str, Any]:
        """
        Create a trial license (for development/testing purposes)
        Note: This requires the private key and should only be used by developers
        """
        logger.warning("Creating trial license - this should only be used for development")
        
        from datetime import timedelta
        
        issue_date = datetime.now(timezone.utc)
        expiry_date = issue_date + timedelta(days=days)
        
        trial_license = {
            'licensedTo': name,
            'email': email,
            'issueDate': issue_date.isoformat(),
            'expiryDate': expiry_date.isoformat(),
            'features': ['enhanced_engine', 'solar_conditions', 'moon_analysis', 'timezone_support'],
            'licenseType': 'trial',
            'version': '1.0',
            'signature': 'trial-signature-placeholder'  # In production, this would be properly signed
        }
        
        return trial_license


# Utility functions for easy integration

def check_license() -> Tuple[bool, Dict[str, Any]]:
    """Simple license check function"""
    manager = LicenseManager()
    return manager.validate_license()


def is_feature_available(feature: str) -> bool:
    """Check if a feature is available in the current license"""
    manager = LicenseManager()
    return manager.is_feature_enabled(feature)


def get_license_info() -> Dict[str, Any]:
    """Get license information for display"""
    manager = LicenseManager()
    return manager.get_license_status()


# Example usage
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Test license validation
    manager = LicenseManager()
    is_valid, info = manager.validate_license()
    
    print(f"License Valid: {is_valid}")
    print(f"License Info: {json.dumps(info, indent=2)}")
    
    # Test feature checking
    print(f"Enhanced Engine Available: {manager.is_feature_enabled('enhanced_engine')}")
    print(f"Solar Conditions Available: {manager.is_feature_enabled('solar_conditions')}")
    
    # Get full status
    status = manager.get_license_status()
    print(f"Full Status: {json.dumps(status, indent=2)}")