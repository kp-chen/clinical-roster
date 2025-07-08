"""Field-level encryption for PHI data"""
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from sqlalchemy.types import TypeDecorator, String
from flask import current_app


class FieldEncryption:
    """Handles field-level encryption for sensitive data"""
    
    def __init__(self, key=None):
        if key:
            self.cipher = Fernet(key)
        else:
            # Get key from environment or generate
            key = os.environ.get('FIELD_ENCRYPTION_KEY')
            if not key:
                # In production, this should raise an error
                # For development, generate a key
                if current_app.config.get('ENV') == 'development':
                    key = Fernet.generate_key().decode()
                    current_app.logger.warning(
                        "FIELD_ENCRYPTION_KEY not set! Generated temporary key. "
                        "Set FIELD_ENCRYPTION_KEY environment variable in production."
                    )
                else:
                    raise ValueError("FIELD_ENCRYPTION_KEY environment variable not set")
            
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encrypt(self, data):
        """Encrypt data"""
        if not data:
            return None
        
        if isinstance(data, str):
            data = data.encode()
        
        encrypted = self.cipher.encrypt(data)
        return base64.urlsafe_b64encode(encrypted).decode()
    
    def decrypt(self, encrypted_data):
        """Decrypt data"""
        if not encrypted_data:
            return None
        
        try:
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted = self.cipher.decrypt(decoded)
            return decrypted.decode()
        except Exception as e:
            current_app.logger.error(f"Decryption failed: {e}")
            return None
    
    @staticmethod
    def generate_key(password=None, salt=None):
        """Generate an encryption key from password"""
        if not password:
            return Fernet.generate_key()
        
        if not salt:
            salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key


class EncryptedField(TypeDecorator):
    """SQLAlchemy type for encrypted fields"""
    impl = String
    cache_ok = True
    
    def __init__(self, *args, **kwargs):
        self.encryption = FieldEncryption()
        super().__init__(*args, **kwargs)
    
    def process_bind_param(self, value, dialect):
        """Encrypt value before storing"""
        if value is None:
            return None
        return self.encryption.encrypt(value)
    
    def process_result_value(self, value, dialect):
        """Decrypt value after retrieving"""
        if value is None:
            return None
        return self.encryption.decrypt(value)


class SecureDataHandler:
    """Utilities for handling sensitive data securely"""
    
    @staticmethod
    def mask_email(email):
        """Mask email for display (e.g., j***@example.com)"""
        if not email or '@' not in email:
            return email
        
        local, domain = email.split('@', 1)
        if len(local) <= 3:
            masked_local = local[0] + '*' * (len(local) - 1)
        else:
            masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_nric(nric):
        """Mask NRIC/ID for display (e.g., S****567A)"""
        if not nric or len(nric) < 4:
            return nric
        
        return nric[0] + '*' * (len(nric) - 4) + nric[-3:]
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename to prevent directory traversal"""
        # Remove any directory components
        filename = os.path.basename(filename)
        
        # Remove potentially dangerous characters
        dangerous_chars = ['..', '/', '\\', '\x00']
        for char in dangerous_chars:
            filename = filename.replace(char, '')
        
        # Limit length
        name, ext = os.path.splitext(filename)
        if len(name) > 100:
            name = name[:100]
        
        return name + ext
    
    @staticmethod
    def generate_secure_token(length=32):
        """Generate a secure random token"""
        return base64.urlsafe_b64encode(os.urandom(length)).decode().rstrip('=')


# Example usage in models
def create_encrypted_patient_model():
    """Example of how to use encrypted fields in a model"""
    from app import db
    
    class PatientData(db.Model):
        """Example model with encrypted PHI fields"""
        __tablename__ = 'patient_data'
        
        id = db.Column(db.Integer, primary_key=True)
        
        # Regular fields
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        # Encrypted fields
        nric = db.Column(EncryptedField(255))
        full_name = db.Column(EncryptedField(255))
        phone_number = db.Column(EncryptedField(100))
        medical_notes = db.Column(EncryptedField(1000))
        
        # Methods for secure display
        @property
        def masked_nric(self):
            return SecureDataHandler.mask_nric(self.nric)
        
        @property
        def masked_name(self):
            if not self.full_name:
                return None
            parts = self.full_name.split()
            if len(parts) > 1:
                return f"{parts[0]} {parts[-1][0]}."
            return parts[0]
    
    return PatientData