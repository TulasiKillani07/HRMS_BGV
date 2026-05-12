"""
Secure Configuration using AWS Secrets Manager
Replace your current config.py with this file
"""

from secrets_manager import secrets_manager
import cloudinary
import cloudinary.uploader
import cloudinary.api

# ============================================
# Surepass API Configuration
# ============================================
SUREPASS_BASE_URL = "https://kyc-api.surepass.io/api/v1"
SUREPASS_TOKEN = secrets_manager.get('SUREPASS_TOKEN')

if not SUREPASS_TOKEN:
    print("⚠️ WARNING: SUREPASS_TOKEN not configured")

# ============================================
# MongoDB Configuration
# ============================================
MONGO_URI = secrets_manager.get('MONGO_URI')
MONGO_DB_NAME = secrets_manager.get('MONGO_DB_NAME', 'bgv_core')

if not MONGO_URI:
    print("⚠️ WARNING: MONGO_URI not configured")

# ============================================
# OpenAI Configuration (for AI CV Validation)
# ============================================
OPENAI_API_KEY = secrets_manager.get('OPENAI_API_KEY')

if not OPENAI_API_KEY:
    print("⚠️ INFO: OPENAI_API_KEY not configured (AI CV validation will not work)")

# ============================================
# Session Configuration
# ============================================
SESSION_SECRET = secrets_manager.get('SESSION_SECRET', 'change-this-in-production')

if SESSION_SECRET == 'change-this-in-production':
    print("⚠️ WARNING: Using default SESSION_SECRET - change in production!")

# Convert to bytes for HMAC
SESSION_SECRET_BYTES = SESSION_SECRET.encode() if isinstance(SESSION_SECRET, str) else SESSION_SECRET

# ============================================
# Cloudinary Configuration (for file uploads)
# ============================================
CLOUDINARY_CLOUD_NAME = secrets_manager.get('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = secrets_manager.get('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = secrets_manager.get('CLOUDINARY_API_SECRET')

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True
    )
    print("✅ Cloudinary configured successfully")
else:
    print("⚠️ WARNING: Cloudinary not fully configured")

# ============================================
# Gmail Configuration (for email notifications)
# ============================================
GMAIL_CREDENTIALS_PATH = secrets_manager.get('GMAIL_CREDENTIALS_PATH', 'token.json')

# ============================================
# Application Configuration
# ============================================
COOKIE_NAME = "bgvSession"
COOKIE_MAX_AGE = 60 * 60 * 2  # 2 hours
COOKIE_SECURE = True
COOKIE_SAMESITE = "none"

# ============================================
# Environment Info
# ============================================
import os
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
DEBUG = ENVIRONMENT == 'development'

print(f"✅ Configuration loaded successfully")
print(f"📍 Environment: {ENVIRONMENT}")
print(f"🔐 Secrets source: {'AWS Secrets Manager' if secrets_manager.use_aws else 'Environment Variables'}")
