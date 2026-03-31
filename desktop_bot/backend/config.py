import os
import sys
import tempfile
from dotenv import load_dotenv

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    env_path = os.path.join(BASE_DIR, '.env')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(os.path.dirname(BASE_DIR), '.env')

load_dotenv(env_path)

SECRET_KEY = os.environ.get('SECRET_KEY', 'desktop-bot-local-key')

UPLOAD_FOLDER = os.path.join(tempfile.gettempdir(), 'meubot_uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload

# Chrome options
if os.environ.get('ELECTRON_RUN') == '1':
    CHROME_HEADLESS = False
else:
    CHROME_HEADLESS = os.environ.get('CHROME_HEADLESS', 'true').lower() == 'true'
