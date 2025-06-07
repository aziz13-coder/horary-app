#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Horary Master - License Generator Utility

This utility generates signed license files for the Enhanced Horary Master application.
It creates RSA key pairs and signs license data for offline verification.

SECURITY NOTE: This utility should only be used by authorized personnel.
The private key must be kept secure and never distributed with the application.

Usage:
    python license_generator.py --generate-keys
    python license_generator.py --create-license "John Doe" "john@example.com" --features enhanced_engine,solar_conditions --days 365

Created: 2025-06-04
Author: Horary Master Team
"""

import argparse
import json
import os
import logging
import hashlib
import platform
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    CRYPTO_AVAILABLE = True
except ImportError:
    print("ERROR: cryptography library not available. Install with: pip install cryptography")
    CRYPTO_AVAILABLE = False
    exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LicenseGenerator:
    """
    Generates and signs license files for Enhanced Horary Master
    """
    
    def __init__(self, private_key_path: str = './private_key.pem', public_key_path: str = './public_key.pem'):
        """
        Initialize the license generator
        
        Args:
            private_key_path: Path to private key file
            public_key_path: Path to public key file
        """
        self.private_key_path = private_key_path
        self.public_key_path = public_key_path
        self._private_key = None
        
        # Available features that can be licensed
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
        
        # Predefined feature bundles
        self.feature_bundles = {
            'basic': ['enhanced_engine', 'solar_conditions', 'timezone_support'],
            'professional': ['enhanced_engine', 'solar_conditions', 'moon_analysis', 'timezone_support', 'future_retrograde', 'directional_motion'],
            'premium': ['enhanced_engine', 'solar_conditions', 'moon_analysis', 'timezone_support', 'future_retrograde', 'directional_motion', 'reception_weighting', 'override_flags', 'premium_support'],
            'enterprise': list(self.available_features.keys())  # All features
        }
    
    def generate_key_pair(self, key_size: int = 2048) -> bool:
        """
        Generate RSA key pair for license signing
        
        Args:
            key_size: RSA key size (default 2048)
            
        Returns:
            True if successful
        """
        try:
            logger.info(f"Generating {key_size}-bit RSA key pair...")
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size
            )
            
            # Get public key
            public_key = private_key.public_key()
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Serialize public key
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            # Write private key
            with open(self.private_key_path, 'wb') as f:
                f.write(private_pem)
            os.chmod(self.private_key_path, 0o600)  # Restrict access
            
            # Write public key
            with open(self.public_key_path, 'wb') as f:
                f.write(public_pem)
            
            logger.info(f"Private key saved to: {self.private_key_path}")
            logger.info(f"Public key saved to: {self.public_key_path}")
            logger.warning("SECURITY: Keep the private key secure and never distribute it!")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to generate key pair: {str(e)}")
            return False
    
    def _load_private_key(self) -> Any:
        """Load the private key for signing"""
        if self._private_key is not None:
            return self._private_key
        
        if not os.path.exists(self.private_key_path):
            raise FileNotFoundError(f"Private key not found: {self.private_key_path}")
        
        try:
            with open(self.private_key_path, 'rb') as f:
                key_data = f.read()
            
            self._private_key = serialization.load_pem_private_key(
                key_data,
                password=None
            )
            
            logger.info("Private key loaded successfully")
            return self._private_key
            
        except Exception as e:
            raise Exception(f"Failed to load private key: {str(e)}")
    
    def _sign_license_data(self, license_data: Dict[str, Any]) -> str:
        """
        Sign license data with private key
        
        Args:
            license_data: License data to sign (without signature field)
            
        Returns:
            Base64-encoded signature
        """
        try:
            private_key = self._load_private_key()
            
            # Create JSON string with sorted keys for consistent hashing
            license_json = json.dumps(license_data, sort_keys=True, separators=(',', ':'))
            license_bytes = license_json.encode('utf-8')
            
            # Sign the data
            signature = private_key.sign(
                license_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
            
            # Encode to base64
            import base64
            signature_b64 = base64.b64encode(signature).decode('ascii')
            
            logger.info("License data signed successfully")
            return signature_b64
            
        except Exception as e:
            raise Exception(f"Failed to sign license data: {str(e)}")
    
    def _get_machine_id(self) -> str:
        """Generate a machine-specific identifier"""
        try:
            system_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
            machine_hash = hashlib.sha256(system_info.encode()).hexdigest()[:16]
            return machine_hash
        except Exception:
            return "unknown-machine"
    
    def create_license(
        self,
        licensed_to: str,
        email: str,
        features: List[str],
        days_valid: int = 365,
        license_type: str = 'commercial',
        machine_specific: bool = False,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a signed license file
        
        Args:
            licensed_to: Name of licensee
            email: Email of licensee
            features: List of features to enable
            days_valid: Number of days license is valid
            license_type: Type of license (commercial, trial, educational)
            machine_specific: Whether to bind to current machine
            output_file: Output file path (default: license.json)
            
        Returns:
            License data dictionary
        """
        try:
            # Validate features
            invalid_features = [f for f in features if f not in self.available_features]
            if invalid_features:
                raise ValueError(f"Invalid features: {invalid_features}")
            
            # Calculate dates
            issue_date = datetime.now(timezone.utc)
            expiry_date = issue_date + timedelta(days=days_valid)
            
            # Create license data
            license_data = {
                'licensedTo': licensed_to,
                'email': email,
                'issueDate': issue_date.isoformat(),
                'expiryDate': expiry_date.isoformat(),
                'features': features,
                'licenseType': license_type,
                'version': '1.0'
            }
            
            # Add machine binding if requested
            if machine_specific:
                license_data['machineId'] = self._get_machine_id()
                logger.info(f"License bound to machine ID: {license_data['machineId']}")
            
            # Sign the license
            signature = self._sign_license_data(license_data)
            license_data['signature'] = signature
            
            # Write to file
            if output_file is None:
                output_file = f"license_{licensed_to.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(license_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"License created successfully: {output_file}")
            logger.info(f"Licensed to: {licensed_to} ({email})")
            logger.info(f"Valid until: {expiry_date.strftime('%Y-%m-%d')}")
            logger.info(f"Features: {', '.join(features)}")
            
            return license_data
            
        except Exception as e:
            logger.error(f"Failed to create license: {str(e)}")
            raise
    
    def create_trial_license(
        self,
        licensed_to: str,
        email: str,
        days_valid: int = 30,
        output_file: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a trial license with basic features
        
        Args:
            licensed_to: Name of licensee
            email: Email of licensee
            days_valid: Number of days trial is valid (default 30)
            output_file: Output file path
            
        Returns:
            License data dictionary
        """
        trial_features = self.feature_bundles['basic']
        
        return self.create_license(
            licensed_to=licensed_to,
            email=email,
            features=trial_features,
            days_valid=days_valid,
            license_type='trial',
            machine_specific=False,
            output_file=output_file
        )
    
    def verify_license(self, license_file: str) -> bool:
        """
        Verify a license file using the public key
        
        Args:
            license_file: Path to license file to verify
            
        Returns:
            True if license is valid
        """
        try:
            from license_manager import LicenseManager
            
            # Use the license manager to verify
            manager = LicenseManager(
                license_file_path=license_file,
                public_key_path=self.public_key_path
            )
            
            is_valid, license_info = manager.validate_license()
            
            if is_valid:
                logger.info("License verification successful")
                logger.info(f"Licensed to: {license_info['licensedTo']}")
                logger.info(f"Features: {', '.join(license_info['features'])}")
                logger.info(f"Days remaining: {license_info['daysRemaining']}")
            else:
                logger.error(f"License verification failed: {license_info.get('error')}")
            
            return is_valid
            
        except Exception as e:
            logger.error(f"License verification error: {str(e)}")
            return False
    
    def list_available_features(self):
        """List all available features"""
        print("\nAvailable Features:")
        print("=" * 50)
        for feature, description in self.available_features.items():
            print(f"  {feature:20} - {description}")
        
        print("\nFeature Bundles:")
        print("=" * 50)
        for bundle, features in self.feature_bundles.items():
            print(f"  {bundle:12} - {', '.join(features)}")
    
    def create_bulk_licenses(self, license_list_file: str):
        """
        Create multiple licenses from a JSON file
        
        File format:
        [
          {
            "licensedTo": "John Doe",
            "email": "john@example.com",
            "features": ["enhanced_engine", "solar_conditions"],
            "daysValid": 365,
            "licenseType": "commercial"
          }
        ]
        """
        try:
            with open(license_list_file, 'r', encoding='utf-8') as f:
                license_list = json.load(f)
            
            created_licenses = []
            
            for i, license_spec in enumerate(license_list):
                try:
                    output_file = f"license_{i+1:03d}_{license_spec['licensedTo'].replace(' ', '_').lower()}.json"
                    
                    license_data = self.create_license(
                        licensed_to=license_spec['licensedTo'],
                        email=license_spec['email'],
                        features=license_spec.get('features', self.feature_bundles['basic']),
                        days_valid=license_spec.get('daysValid', 365),
                        license_type=license_spec.get('licenseType', 'commercial'),
                        machine_specific=license_spec.get('machineSpecific', False),
                        output_file=output_file
                    )
                    
                    created_licenses.append(output_file)
                    
                except Exception as e:
                    logger.error(f"Failed to create license {i+1}: {str(e)}")
            
            logger.info(f"Created {len(created_licenses)} licenses successfully")
            return created_licenses
            
        except Exception as e:
            logger.error(f"Failed to process bulk license file: {str(e)}")
            return []


def main():
    """Command line interface for license generator"""
    parser = argparse.ArgumentParser(description='Enhanced Horary Master License Generator')
    
    parser.add_argument('--generate-keys', action='store_true',
                       help='Generate new RSA key pair')
    
    parser.add_argument('--create-license', nargs=2, metavar=('NAME', 'EMAIL'),
                       help='Create a license for the specified name and email')
    
    parser.add_argument('--trial-license', nargs=2, metavar=('NAME', 'EMAIL'),
                       help='Create a trial license for the specified name and email')
    
    parser.add_argument('--features', type=str,
                       help='Comma-separated list of features or bundle name (basic, professional, premium, enterprise)')
    
    parser.add_argument('--days', type=int, default=365,
                       help='Number of days license is valid (default: 365)')
    
    parser.add_argument('--type', type=str, default='commercial',
                       choices=['commercial', 'trial', 'educational'],
                       help='License type (default: commercial)')
    
    parser.add_argument('--machine-specific', action='store_true',
                       help='Bind license to current machine')
    
    parser.add_argument('--output', type=str,
                       help='Output file path')
    
    parser.add_argument('--verify', type=str,
                       help='Verify a license file')
    
    parser.add_argument('--list-features', action='store_true',
                       help='List available features and bundles')
    
    parser.add_argument('--bulk', type=str,
                       help='Create multiple licenses from JSON file')
    
    parser.add_argument('--private-key', type=str, default='./private_key.pem',
                       help='Path to private key file')
    
    parser.add_argument('--public-key', type=str, default='./public_key.pem',
                       help='Path to public key file')
    
    args = parser.parse_args()
    
    if not CRYPTO_AVAILABLE:
        print("ERROR: cryptography library not available. Install with: pip install cryptography")
        return 1
    
    generator = LicenseGenerator(
        private_key_path=args.private_key,
        public_key_path=args.public_key
    )
    
    try:
        if args.generate_keys:
            success = generator.generate_key_pair()
            return 0 if success else 1
        
        elif args.list_features:
            generator.list_available_features()
            return 0
        
        elif args.verify:
            is_valid = generator.verify_license(args.verify)
            return 0 if is_valid else 1
        
        elif args.bulk:
            created = generator.create_bulk_licenses(args.bulk)
            return 0 if created else 1
        
        elif args.create_license:
            name, email = args.create_license
            
            # Parse features
            if args.features:
                if args.features in generator.feature_bundles:
                    features = generator.feature_bundles[args.features]
                else:
                    features = [f.strip() for f in args.features.split(',')]
            else:
                features = generator.feature_bundles['professional']
            
            generator.create_license(
                licensed_to=name,
                email=email,
                features=features,
                days_valid=args.days,
                license_type=args.type,
                machine_specific=args.machine_specific,
                output_file=args.output
            )
            return 0
        
        elif args.trial_license:
            name, email = args.trial_license
            
            generator.create_trial_license(
                licensed_to=name,
                email=email,
                days_valid=args.days,
                output_file=args.output
            )
            return 0
        
        else:
            parser.print_help()
            return 1
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return 1


if __name__ == '__main__':
    exit(main())