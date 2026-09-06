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
    elif os.environ.get('VERCEL') == '1' or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        # Serverless fallback SQLite in /tmp
        db_path = os.path.join(tempfile.gettempdir(), 'flyash.db')
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'
    else:
        # Local development SQLite
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'flyash.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Engine options for reliable cloud database connections (auto-reconnect & pre-ping)
    if not SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }
