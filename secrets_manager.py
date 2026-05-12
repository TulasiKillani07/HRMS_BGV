"""
AWS Secrets Manager Integration
Securely fetch API keys and secrets from AWS Secrets Manager
"""

import boto3
import json
import os
from functools import lru_cache
from botocore.exceptions import ClientError

class SecretsManager:
    """
    Manages secrets from AWS Secrets Manager with fallback to environment variables
    """
    
    def __init__(self):
        self.region_name = os.getenv('AWS_REGION', 'us-east-1')
        self.secret_name = os.getenv('SECRET_NAME', 'bgv-app/production')
        self.use_aws = os.getenv('USE_AWS_SECRETS', 'true').lower() == 'true'
        self._secrets = None
        
        if self.use_aws:
            try:
                self.client = boto3.client('secretsmanager', region_name=self.region_name)
                print(f"🔐 AWS Secrets Manager initialized for region: {self.region_name}")
            except Exception as e:
                print(f"⚠️ Could not initialize AWS Secrets Manager: {e}")
                print("⚠️ Falling back to environment variables")
                self.use_aws = False
    
    @lru_cache(maxsize=1)
    def get_secrets(self):
        """
        Fetch secrets from AWS Secrets Manager or environment variables
        Cached to avoid repeated API calls
        """
        if self._secrets is not None:
            return self._secrets
        
        if self.use_aws:
            try:
                return self._fetch_from_aws()
            except Exception as e:
                print(f"❌ Error fetching from AWS Secrets Manager: {str(e)}")
                print("⚠️ Falling back to environment variables")
                return self._get_env_fallback()
        else:
            return self._get_env_fallback()
    
    def _fetch_from_aws(self):
        """Fetch secrets from AWS Secrets Manager"""
        print(f"🔐 Fetching secrets from AWS Secrets Manager: {self.secret_name}")
        
        try:
            response = self.client.get_secret_value(SecretId=self.secret_name)
            
            if 'SecretString' in response:
                self._secrets = json.loads(response['SecretString'])
                print(f"✅ Successfully loaded {len(self._secrets)} secrets from AWS")
                return self._secrets
            else:
                raise Exception("SecretString not found in response")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                raise Exception(f"Secret '{self.secret_name}' not found in AWS Secrets Manager")
            elif error_code == 'InvalidRequestException':
                raise Exception(f"Invalid request to AWS Secrets Manager")
            elif error_code == 'InvalidParameterException':
                raise Exception(f"Invalid parameter in request")
            elif error_code == 'DecryptionFailure':
                raise Exception(f"Cannot decrypt secret")
            elif error_code == 'InternalServiceError':
                raise Exception(f"AWS Secrets Manager internal error")
            else:
                raise Exception(f"AWS Secrets Manager error: {error_code}")
    
    def _get_env_fallback(self):
        """
        Fallback to environment variables for local development
        """
        print("📝 Loading secrets from environment variables")
        
        secrets = {
            'SUREPASS_TOKEN': os.getenv('SUREPASS_TOKEN', ''),
            'MONGO_URI': os.getenv('MONGO_URI', ''),
            'MONGO_DB_NAME': os.getenv('MONGO_DB_NAME', 'bgv_core'),
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
            'SESSION_SECRET': os.getenv('SESSION_SECRET', 'dev-secret-key-change-in-production'),
            'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME', ''),
            'CLOUDINARY_API_KEY': os.getenv('CLOUDINARY_API_KEY', ''),
            'CLOUDINARY_API_SECRET': os.getenv('CLOUDINARY_API_SECRET', ''),
            'GMAIL_CREDENTIALS_PATH': os.getenv('GMAIL_CREDENTIALS_PATH', 'token.json')
        }
        
        # Check if critical secrets are missing
        missing = [k for k, v in secrets.items() if not v and k in ['SUREPASS_TOKEN', 'MONGO_URI']]
        if missing:
            print(f"⚠️ WARNING: Missing critical secrets: {', '.join(missing)}")
        
        self._secrets = secrets
        return secrets
    
    def get(self, key, default=None):
        """
        Get a specific secret value
        
        Args:
            key: Secret key name
            default: Default value if key not found
            
        Returns:
            Secret value or default
        """
        secrets = self.get_secrets()
        value = secrets.get(key, default)
        
        if value is None or value == '':
            print(f"⚠️ WARNING: Secret '{key}' is empty or not found")
        
        return value
    
    def refresh(self):
        """
        Force refresh secrets from source
        Useful when secrets are rotated
        """
        print("🔄 Refreshing secrets...")
        self._secrets = None
        self.get_secrets.cache_clear()
        return self.get_secrets()
    
    def validate(self):
        """
        Validate that all required secrets are present
        
        Returns:
            tuple: (is_valid, missing_keys)
        """
        required_keys = [
            'SUREPASS_TOKEN',
            'MONGO_URI',
            'SESSION_SECRET'
        ]
        
        secrets = self.get_secrets()
        missing = []
        
        for key in required_keys:
            value = secrets.get(key)
            if not value or value == '':
                missing.append(key)
        
        is_valid = len(missing) == 0
        
        if is_valid:
            print("✅ All required secrets are present")
        else:
            print(f"❌ Missing required secrets: {', '.join(missing)}")
        
        return is_valid, missing

# Singleton instance
secrets_manager = SecretsManager()

# Validate on import
if __name__ != "__main__":
    is_valid, missing = secrets_manager.validate()
    if not is_valid:
        print(f"⚠️ WARNING: Application may not function correctly without: {', '.join(missing)}")
