import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Vercel creates fresh Python instances periodically. The application previously
# ran create_all(), migrations, and seed queries on every cold start. Production
# schema/data are already provisioned, so skip that expensive work by default on
# Vercel. Set FLYASH_RUN_DB_INIT=1 only when a one-time schema/seed initialization
# is intentionally required.
if os.environ.get("VERCEL") and os.environ.get("FLYASH_RUN_DB_INIT") != "1":
    app_source_path = PROJECT_ROOT / "app.py"
    app_source = app_source_path.read_text(encoding="utf-8")

    startup_block = '''    # Create database tables and default admin user
    with app.app_context():
        db.create_all()
        _migrate_db()
        _create_default_admin()
        _create_default_rates_and_groups()
        if not app.config.get('TESTING') and not os.environ.get('VERCEL') and not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            try:
                from utils.telegram_service import start_telegram_scheduler
                start_telegram_scheduler(app)
            except Exception as e:
                print(f"[WARN] Could not start Telegram scheduler: {e}")
'''

    replacement = '''    # Database schema and seed data are provisioned outside the request path on Vercel.
    # Local development keeps the original initialization behavior.
    if not os.environ.get('VERCEL') and not os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
        with app.app_context():
            db.create_all()
            _migrate_db()
            _create_default_admin()
            _create_default_rates_and_groups()
            if not app.config.get('TESTING'):
                try:
                    from utils.telegram_service import start_telegram_scheduler
                    start_telegram_scheduler(app)
                except Exception as e:
                    print(f"[WARN] Could not start Telegram scheduler: {e}")
'''

    if startup_block not in app_source:
        raise RuntimeError("Expected app.py startup block was not found; refusing to modify application source")

    app_source = app_source.replace(startup_block, replacement, 1)

    # Execute the transformed source as the normal 'app' module so all existing
    # blueprint imports and Flask routes continue to behave exactly as before.
    module_globals = {"__name__": "app", "__file__": str(app_source_path), "__package__": ""}
    sys.modules["app"] = type(sys)("app")
    app_module = sys.modules["app"]
    app_module.__file__ = str(app_source_path)
    app_module.__package__ = ""
    exec(compile(app_source, str(app_source_path), "exec"), app_module.__dict__)
    app = app_module.app
else:
    from app import app

# Vercel serverless function entrypoint
app = app
