import os
from urllib.parse import urlparse

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'flyash-mgr-secret-key-change-in-production'

    # Vercel must use a persistent PostgreSQL database. SQLite on /tmp is
    # ephemeral in serverless and can lose business data between invocations.
    raw_db_url = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or ''

    is_serverless = bool(
        os.environ.get('VERCEL')
        or os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        or os.environ.get('NOW_REGION')
    )

    if raw_db_url:
        if raw_db_url.startswith('postgres://'):
            raw_db_url = raw_db_url.replace('postgres://', 'postgresql://', 1)

        raw_db_url = raw_db_url.replace(
            'channel_binding=require&', ''
        ).replace(
            '&channel_binding=require', ''
        ).replace(
            'channel_binding=require', ''
        )
        SQLALCHEMY_DATABASE_URI = raw_db_url
    elif is_serverless:
        raise RuntimeError(
            'DATABASE_URL is required on Vercel. '
            'Connect FlyAsh Manager to the Supabase PostgreSQL database before deploying.'
        )
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'flyash.db')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    if SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': False,
        }
    else:
        parsed = urlparse(SQLALCHEMY_DATABASE_URI)
        using_transaction_pooler = parsed.port == 6543

        if using_transaction_pooler:
            from sqlalchemy.pool import NullPool

            SQLALCHEMY_ENGINE_OPTIONS = {
                'poolclass': NullPool,
                'pool_pre_ping': False,
            }
        else:
            SQLALCHEMY_ENGINE_OPTIONS = {
                'pool_size': 1,
                'max_overflow': 0,
                'pool_timeout': 10,
                'pool_pre_ping': True,
                'pool_recycle': 900,
            }
