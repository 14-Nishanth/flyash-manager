import os
import tempfile

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'flyash-mgr-secret-key-change-in-production'
    
    # Support Vercel serverless /tmp directory or cloud DATABASE_URL (Supabase/Neon/Postgres)
    if os.environ.get('VERCEL') == '1' or os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        db_path = os.path.join(tempfile.gettempdir(), 'flyash.db')
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path}'
    else:
        SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'flyash.db')
            
    # Normalize postgres:// to postgresql:// for SQLAlchemy compatibility
    if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
