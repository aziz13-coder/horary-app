#!/usr/bin/env python3
"""
WSGI entry point for Render deployment
"""
import os
import sys

# Add the backend directory to Python path
backend_path = os.path.join(os.path.dirname(__file__), 'horary77-main', 'horary4', 'backend')
sys.path.insert(0, backend_path)

try:
    from app import app as application
    print(f"✅ Successfully imported Flask app from {backend_path}")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print(f"Python path: {sys.path}")
    print(f"Backend path: {backend_path}")
    print(f"Files in backend: {os.listdir(backend_path) if os.path.exists(backend_path) else 'Directory not found'}")
    raise

if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get('PORT', 5000))
    application.run(host='0.0.0.0', port=port, debug=False)