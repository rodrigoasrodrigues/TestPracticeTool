import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:password@localhost/testpracticetool'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    IMAGE_S3_PATH = os.environ.get('IMAGE_S3_PATH', '').strip()
    IMAGE_S3_URL_EXPIRATION = int(os.environ.get('IMAGE_S3_URL_EXPIRATION', '3600'))
    AWS_REGION = os.environ.get('AWS_REGION', '').strip() or None
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '').strip() or None
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
