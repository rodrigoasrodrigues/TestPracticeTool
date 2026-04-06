import os
from dotenv import load_dotenv
from sqlalchemy.engine import URL

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))


def _build_database_uri():
    database_url = os.environ.get('DATABASE_URL', '').strip()
    if database_url:
        return database_url

    db_host = os.environ.get('DB_HOST', '').strip()
    db_name = os.environ.get('DB_NAME', '').strip()

    if db_host and db_name:
        db_driver = os.environ.get('DB_DRIVER', 'mysql+pymysql').strip() or 'mysql+pymysql'
        db_user = os.environ.get('DB_USER', '').strip() or None
        db_password = os.environ.get('DB_PASSWORD')
        db_port_raw = os.environ.get('DB_PORT', '').strip()
        db_port = int(db_port_raw) if db_port_raw else None

        return URL.create(
            drivername=db_driver,
            username=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database=db_name,
        ).render_as_string(hide_password=False)

    return 'mysql+pymysql://root:password@localhost/testpracticetool'


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = _build_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    IMAGE_S3_PATH = os.environ.get('IMAGE_S3_PATH', '').strip()
    IMAGE_S3_URL_EXPIRATION = int(os.environ.get('IMAGE_S3_URL_EXPIRATION', '3600'))
    AWS_REGION = os.environ.get('AWS_REGION', '').strip() or None
    AWS_S3_ENDPOINT_URL = os.environ.get('AWS_S3_ENDPOINT_URL', '').strip() or None
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max upload
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
