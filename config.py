import os
import tempfile

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'flyash-mgr-secret-key-change-in-production'

    # Check for external cloud DATABASE_URL (e.g. Supabase, Neon, PostgreSQL, MySQL)
    raw_db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or ''

    if raw_db_url:
        # Normalize postgres:// to postgresql:// for modern SQLAlchemy
        if raw_db_url.startswith('postgres://'):
            raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)
        # Strip unsupported channel_binding param from URL if present
        raw_db_url = raw_db_url.replace('channel_binding=require&', '').replace('&channel_binding=require', '').replace('channel_binding=require', '')
        SQLALCHEMY_DATABASE_URI = raw_db_url
    elif bool(os.environ.get('VERCEL')) or bool(os.environ.get('AWS_LAMBDA_FUNCTION_NAME')) or bool(os.environ.get('NOW_REGION')):
        # Serverless fallback SQLite in /tmp
        db_path = os.path.join(tempfile.gettempdir(), 'flyash.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    else:
        # Local development SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'flyash.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Keep the serverless DB pool deliberately small. A Vercel function instance
    # normally handles a small amount of concurrent work, and a large pool can
    # create unnecessary database connections across many serverless instances.
    if not SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_size': 1,
            'max_overflow': 0,
            'pool_timeout': 10,
            # Avoid a network round-trip on every checkout. Connections are
            # short-lived in serverless and can be recreated if the provider closes one.
            'pool_pre_ping': False,
            'pool_recycle': 900,
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': False,
        }
