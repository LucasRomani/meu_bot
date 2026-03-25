import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet

# Load .env file from root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SECRET_KEY = os.environ.get('SECRET_KEY', 'bot-sischef-qrpedir-secret-key-change-in-production')
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    # Use a default SQLite if no POSTGRES_URL is provided, for local dev only.
    # But for Supabase/Cloud, this MUST be set.
    print("⚠️ DATABASE_URL não encontrada no .env! Usando SQLite local (apenas para desenvolvimento).")
    DATABASE_URL = "sqlite:///./local_dev.db"

ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

if not ENCRYPTION_KEY:
    # Generate a key if it doesn't exist (useful for first run in dev)
    # In cloud, this should be set as an environment variable!
    ENCRYPTION_KEY = Fernet.generate_key().decode()

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

# Chrome options
CHROME_HEADLESS = os.environ.get('CHROME_HEADLESS', 'true').lower() == 'true'
