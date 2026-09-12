import os
import sqlite3
from flask import Flask, redirect, url_for, send_from_directory
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import Config
from models import db, User


def _migrate_db():
    """Ensure newly added columns exist in SQLite and PostgreSQL tables."""
    # PostgreSQL migration
    if not Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(10) DEFAULT \'en\';'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS cooldown_minutes INTEGER DEFAULT 30;'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS max_alerts_per_day INTEGER DEFAULT 3;'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS alert_on_first_login_only BOOLEAN DEFAULT FALSE;'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS alert_on_owner_login BOOLEAN DEFAULT FALSE;'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS alert_on_staff_login BOOLEAN DEFAULT TRUE;'))
                conn.execute(db.text('ALTER TABLE "alert_settings" ADD COLUMN IF NOT EXISTS alert_on_failed_attempts BOOLEAN DEFAULT TRUE;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS tray_count DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS pieces_per_tray DOUBLE PRECISION DEFAULT 105.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS wastage_per_tray DOUBLE PRECISION DEFAULT 5.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS total_wastage DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS gross_quantity DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS gross_amount DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('ALTER TABLE "job_wage_entry" ADD COLUMN IF NOT EXISTS wastage_amount DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('ALTER TABLE "job_rate_setting" ADD COLUMN IF NOT EXISTS pieces_per_tray DOUBLE PRECISION DEFAULT 105.0;'))
                conn.execute(db.text('ALTER TABLE "job_rate_setting" ADD COLUMN IF NOT EXISTS wastage_per_tray DOUBLE PRECISION DEFAULT 5.0;'))
                conn.execute(db.text('ALTER TABLE "job_rate_setting" ADD COLUMN IF NOT EXISTS opening_stock DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('''
                    CREATE TABLE IF NOT EXISTS "expense" (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL DEFAULT CURRENT_DATE,
                        category VARCHAR(60) NOT NULL DEFAULT 'Diesel / Fuel',
                        title VARCHAR(150) NOT NULL,
                        amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        payment_mode VARCHAR(30) DEFAULT 'cash',
                        paid_to VARCHAR(100),
                        reference_no VARCHAR(50),
                        notes TEXT,
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                '''))
                conn.execute(db.text('''
                    CREATE TABLE IF NOT EXISTS "party_adjustment" (
                        id SERIAL PRIMARY KEY,
                        party_id INTEGER NOT NULL REFERENCES "party"(id) ON DELETE CASCADE,
                        date DATE NOT NULL DEFAULT CURRENT_DATE,
                        adjustment_type VARCHAR(30) NOT NULL DEFAULT 'past_unpaid_due',
                        amount DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        reason VARCHAR(255) NOT NULL,
                        reference_no VARCHAR(50),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                '''))
                conn.execute(db.text('ALTER TABLE "party" ADD COLUMN IF NOT EXISTS default_selling_rate DOUBLE PRECISION DEFAULT 0.0;'))
                conn.execute(db.text('''
                    CREATE TABLE IF NOT EXISTS "party_product_rate" (
                        id SERIAL PRIMARY KEY,
                        party_id INTEGER NOT NULL REFERENCES "party"(id) ON DELETE CASCADE,
                        product_name VARCHAR(120) NOT NULL,
                        rate DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        unit VARCHAR(30) DEFAULT 'Pieces / Pcs',
                        notes VARCHAR(255),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_party_product_rate UNIQUE (party_id, product_name)
                    );
                '''))
                conn.execute(db.text('''
                    CREATE TABLE IF NOT EXISTS "stock_adjustment" (
                        id SERIAL PRIMARY KEY,
                        date DATE NOT NULL DEFAULT CURRENT_DATE,
                        item_type VARCHAR(30) NOT NULL DEFAULT 'product',
                        item_name VARCHAR(120) NOT NULL,
                        quantity DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        unit VARCHAR(30) DEFAULT 'Pieces',
                        adjustment_type VARCHAR(40) NOT NULL DEFAULT 'past_month_stock',
                        notes VARCHAR(255),
                        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                '''))
                conn.commit()
        except Exception as e:
            print(f"[WARN] PostgreSQL migration notice: {e}")
        return

    # SQLite migration
    db_path = Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "party_adjustment" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                party_id INTEGER NOT NULL,
                date DATE NOT NULL,
                adjustment_type VARCHAR(30) NOT NULL DEFAULT 'past_unpaid_due',
                amount FLOAT NOT NULL DEFAULT 0.0,
                reason VARCHAR(255) NOT NULL,
                reference_no VARCHAR(50),
                created_at DATETIME,
                FOREIGN KEY (party_id) REFERENCES party(id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "party_product_rate" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                party_id INTEGER NOT NULL,
                product_name VARCHAR(120) NOT NULL,
                rate FLOAT NOT NULL DEFAULT 0.0,
                unit VARCHAR(30) DEFAULT 'Pieces / Pcs',
                notes VARCHAR(255),
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY (party_id) REFERENCES party(id) ON DELETE CASCADE,
                UNIQUE (party_id, product_name)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "stock_adjustment" (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                item_type VARCHAR(30) NOT NULL DEFAULT 'product',
                item_name VARCHAR(120) NOT NULL,
                quantity FLOAT NOT NULL DEFAULT 0.0,
                unit VARCHAR(30) DEFAULT 'Pieces',
                adjustment_type VARCHAR(40) NOT NULL DEFAULT 'past_month_stock',
                notes VARCHAR(255),
                created_at DATETIME
            )
        ''')
        conn.commit()
        
        # Migrations definition
        table_migrations = {
            'party': [('default_selling_rate', "FLOAT DEFAULT 0.0")],
            'material_inward': [('quantity_unit', "VARCHAR(20) DEFAULT 'Ton'")],
            'material_outward': [('quantity_unit', "VARCHAR(20) DEFAULT 'Ton'")],
            'job_rate_setting': [
                ('pieces_per_tray', "FLOAT DEFAULT 105.0"),
                ('wastage_per_tray', "FLOAT DEFAULT 5.0"),
                ('opening_stock', "FLOAT DEFAULT 0.0")
            ],
            'user': [
                ('name', "VARCHAR(100) DEFAULT 'Admin'"),
                ('email', "VARCHAR(120) DEFAULT 'admin@flyash.com'"),
                ('phone', "VARCHAR(20)"),
                ('preferred_language', "VARCHAR(10) DEFAULT 'en'"),
                ('is_active', "BOOLEAN DEFAULT 1"),
                ('created_at', "DATETIME")
            ],
            'login_history': [
                ('user_id', "INTEGER"),
                ('email', "VARCHAR(120)"),
                ('user_role', "VARCHAR(30)")
            ],
            'job_wage_entry': [
                ('group_id', "INTEGER"),
                ('tray_count', "FLOAT DEFAULT 0.0"),
                ('pieces_per_tray', "FLOAT DEFAULT 105.0"),
                ('wastage_per_tray', "FLOAT DEFAULT 5.0"),
                ('total_wastage', "FLOAT DEFAULT 0.0"),
                ('gross_quantity', "FLOAT DEFAULT 0.0"),
                ('gross_amount', "FLOAT DEFAULT 0.0"),
                ('wastage_amount', "FLOAT DEFAULT 0.0")
            ],
            'alert_settings': [
                ('owner_name', "VARCHAR(100) DEFAULT 'Nishanth (Owner)'"),
                ('owner_email', "VARCHAR(120) DEFAULT 'nishanthissan1515@gmail.com'"),
                ('email_alerts_enabled', "BOOLEAN DEFAULT 1"),
                ('smtp_host', "VARCHAR(100) DEFAULT 'smtp.gmail.com'"),
                ('smtp_port', "INTEGER DEFAULT 587"),
                ('smtp_user', "VARCHAR(120)"),
                ('smtp_password', "VARCHAR(120)"),
                ('telegram_bot_token', "VARCHAR(255)"),
                ('telegram_chat_id', "VARCHAR(100)"),
                ('telegram_morning_reminder_enabled', "BOOLEAN DEFAULT 1"),
                ('telegram_morning_reminder_time', "VARCHAR(10) DEFAULT '07:00'"),
                ('telegram_evening_reminder_enabled', "BOOLEAN DEFAULT 1"),
                ('telegram_evening_reminder_time', "VARCHAR(10) DEFAULT '19:00'"),
                ('last_morning_sent_date', "DATE"),
                ('last_evening_sent_date', "DATE"),
                ('alert_on_all_users', "BOOLEAN DEFAULT 1"),
                ('cooldown_minutes', "INTEGER DEFAULT 30"),
                ('max_alerts_per_day', "INTEGER DEFAULT 3"),
                ('alert_on_first_login_only', "BOOLEAN DEFAULT 0"),
                ('alert_on_owner_login', "BOOLEAN DEFAULT 0"),
                ('alert_on_staff_login', "BOOLEAN DEFAULT 1"),
                ('alert_on_failed_attempts', "BOOLEAN DEFAULT 1")
            ]
        }
        
        for table, cols in table_migrations.items():
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                existing_cols = [col[1] for col in cursor.fetchall()]
                if existing_cols:
                    for col_name, col_def in cols:
                        if col_name not in existing_cols:
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
            except Exception:
                pass
                
        conn.commit()
        conn.close()


def _create_default_rates_and_groups():
    """Seed default piece rates and initial groups for Flyash Bricks, Solid Blocks, and Hollow Blocks."""
    from models import JobRateSetting, EmployeeGroup, Employee
    try:
        if not JobRateSetting.query.first():
            standard_rates = [
                # --- Fly Ash Bricks ---
                ('Fly Ash Brick 9"x4"x3" (Standard)', 'Production (Per Piece)', 0.60, 'Pieces / Pcs'),
                ('Fly Ash Brick 9"x4"x3" (Standard)', 'Loading Only', 0.25, 'Pieces / Pcs'),
                ('Fly Ash Brick 9"x4"x3" (Standard)', 'Unloading Only', 0.20, 'Pieces / Pcs'),
                ('Fly Ash Brick 9"x4"x3" (Standard)', 'Both Loading & Unloading', 0.45, 'Pieces / Pcs'),
                ('Fly Ash Brick Modular (190 x 90 x 90 mm)', 'Production (Per Piece)', 0.55, 'Pieces / Pcs'),
                ('Fly Ash Brick Modular (190 x 90 x 90 mm)', 'Both Loading & Unloading', 0.40, 'Pieces / Pcs'),
                
                # --- Solid Blocks ---
                ('Solid Block 4"', 'Production (Per Piece)', 1.20, 'Pieces / Pcs'),
                ('Solid Block 4"', 'Loading Only', 0.35, 'Pieces / Pcs'),
                ('Solid Block 4"', 'Unloading Only', 0.30, 'Pieces / Pcs'),
                ('Solid Block 4"', 'Both Loading & Unloading', 0.65, 'Pieces / Pcs'),
                ('Solid Block 6"', 'Production (Per Piece)', 1.60, 'Pieces / Pcs'),
                ('Solid Block 6"', 'Loading Only', 0.45, 'Pieces / Pcs'),
                ('Solid Block 6"', 'Unloading Only', 0.40, 'Pieces / Pcs'),
                ('Solid Block 6"', 'Both Loading & Unloading', 0.85, 'Pieces / Pcs'),
                ('Solid Block 8"', 'Production (Per Piece)', 2.00, 'Pieces / Pcs'),
                ('Solid Block 8"', 'Loading Only', 0.55, 'Pieces / Pcs'),
                ('Solid Block 8"', 'Unloading Only', 0.50, 'Pieces / Pcs'),
                ('Solid Block 8"', 'Both Loading & Unloading', 1.05, 'Pieces / Pcs'),
                
                # --- Hollow Blocks ---
                ('Hollow Block 4" (400 x 200 x 100 mm)', 'Production (Per Piece)', 1.00, 'Pieces / Pcs'),
                ('Hollow Block 4" (400 x 200 x 100 mm)', 'Both Loading & Unloading', 0.55, 'Pieces / Pcs'),
                ('Hollow Block 6" (400 x 200 x 150 mm)', 'Production (Per Piece)', 1.40, 'Pieces / Pcs'),
                ('Hollow Block 6" (400 x 200 x 150 mm)', 'Loading Only', 0.40, 'Pieces / Pcs'),
                ('Hollow Block 6" (400 x 200 x 150 mm)', 'Unloading Only', 0.35, 'Pieces / Pcs'),
                ('Hollow Block 6" (400 x 200 x 150 mm)', 'Both Loading & Unloading', 0.75, 'Pieces / Pcs'),
                ('Hollow Block 8" (400 x 200 x 200 mm)', 'Production (Per Piece)', 1.80, 'Pieces / Pcs'),
                ('Hollow Block 8" (400 x 200 x 200 mm)', 'Both Loading & Unloading', 0.95, 'Pieces / Pcs'),
                ('Hollow Block 9" (400 x 200 x 225 mm)', 'Production (Per Piece)', 2.00, 'Pieces / Pcs'),
                ('Hollow Block 9" (400 x 200 x 225 mm)', 'Both Loading & Unloading', 1.05, 'Pieces / Pcs'),
                ('Hollow Block 12" (400 x 200 x 300 mm)', 'Production (Per Piece)', 2.50, 'Pieces / Pcs'),
                ('Hollow Block 12" (400 x 200 x 300 mm)', 'Both Loading & Unloading', 1.35, 'Pieces / Pcs'),
            ]
            for prod, job, rate, unit in standard_rates:
                tray_cap = 105.0 if 'Brick' in prod else (60.0 if 'Block' in prod else 100.0)
                waste_cap = 5.0 if 'Brick' in prod else 3.0
                db.session.add(JobRateSetting(
                    product_name=prod,
                    job_type=job,
                    rate_per_piece=rate,
                    pieces_per_tray=tray_cap,
                    wastage_per_tray=waste_cap,
                    unit=unit
                ))
            db.session.commit()

        if not EmployeeGroup.query.first():
            sample_groups = [
                ('Brick Production Team (Gang 1)', 'Group dedicated to daily Fly Ash Brick manufacturing', 'Production (Per Piece)', 'Fly Ash Brick 9"x4"x3" (Standard)'),
                ('Solid & Hollow Block Gang (Gang 2)', 'Group for solid and hollow block machine production', 'Production (Per Piece)', 'Solid Block 6"'),
                ('Loading & Vehicle Dispatch Team', 'Labor gang for vehicle loading and transport', 'Loading Only', 'Fly Ash Brick 9"x4"x3" (Standard)'),
                ('Unloading & Material Handling Gang', 'Labor team for unloading raw materials and bricks', 'Unloading Only', 'Fly Ash Brick 9"x4"x3" (Standard)')
            ]
            all_emps = Employee.query.filter_by(is_active=True).all()
            for gname, desc, jtype, prod in sample_groups:
                grp = EmployeeGroup(name=gname, description=desc, default_job_type=jtype, default_product_name=prod)
                if all_emps:
                    grp.members = all_emps[:min(4, len(all_emps))]
                db.session.add(grp)
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[WARN] Error seeding rates/groups: {e}")


def _create_default_admin():
    """Create a default admin user if none exists and set owner email."""
    if not User.query.first():
        admin = User(name='Nishanth (Owner)', username='admin', email='nishanthissan1515@gmail.com', role='owner')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('[OK] Default admin user created (nishanthissan1515@gmail.com / admin123)')
    else:
        # Ensure owner has email nishanthissan1515@gmail.com
        owner = User.query.filter((User.role == 'owner') | (User.id == 1)).first()
        if owner and (not owner.email or owner.email == 'admin@flyash.com'):
            owner.name = 'Nishanth (Owner)'
            owner.email = 'nishanthissan1515@gmail.com'
            db.session.commit()


def create_app():
    """Application factory."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    templates_dir = os.path.join(base_dir, 'templates')
    static_dir = os.path.join(base_dir, 'static')
    
    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=static_dir,
        static_url_path='/static'
    )
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    CSRFProtect(app)

    # Explicit static file handler for serverless Vercel
    
    # PWA Manifest and Service Worker routes
    @app.route('/manifest.json')
    def pwa_manifest():
        return send_from_directory(static_dir, 'manifest.json', mimetype='application/manifest+json')

    @app.route('/sw.js')
    def pwa_sw():
        response = send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
        response.headers['Service-Worker-Allowed'] = '/'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    @app.route('/static/<path:filename>')
    def serve_static(filename):
        return send_from_directory(static_dir, filename)

    # Flask-Login setup
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprints
    from routes.auth import bp as auth_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.employees import bp as employees_bp
    from routes.materials import bp as materials_bp
    from routes.parties import bp as parties_bp
    from routes.reports import bp as reports_bp
    from routes.expenses import bp as expenses_bp
    from routes.stock import bp as stock_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(parties_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(stock_bp)

    # Redirect root to dashboard if no dashboard blueprint handles it
    @app.route('/favicon.ico')
    def favicon():
        return '', 204

    # Create database tables and default admin user
    with app.app_context():
        _migrate_db()
        db.create_all()
        _create_default_admin()
        _create_default_rates_and_groups()
        if not app.config.get('TESTING'):
            try:
                from utils.telegram_service import start_telegram_scheduler
                start_telegram_scheduler(app)
            except Exception as e:
                print(f"[WARN] Could not start Telegram scheduler: {e}")

    # Template context processors
    from translations import SUPPORTED_LANGUAGES, LANGUAGE_MAP, get_translation
    from flask import session, request
    from flask_login import current_user

    @app.context_processor
    def inject_globals():
        user_lang = None
        if current_user.is_authenticated:
            user_lang = getattr(current_user, 'preferred_language', None)
        active_lang = session.get('lang') or request.cookies.get('flyash_lang') or user_lang or 'en'
        if active_lang not in LANGUAGE_MAP:
            active_lang = 'en'

        def _t(key, default=None):
            return get_translation(key, active_lang, default)

        return {
            'app_name': 'FlyAsh Manager',
            'app_version': '1.0.0',
            'supported_languages': SUPPORTED_LANGUAGES,
            'language_map': LANGUAGE_MAP,
            'current_language': active_lang,
            'current_lang_meta': LANGUAGE_MAP.get(active_lang, LANGUAGE_MAP['en']),
            '_t': _t,
            't': _t
        }

    return app


# Run the application
app = create_app()

if __name__ == '__main__':
    print('=' * 50)
    print('  FlyAsh Manager v1.0')
    print('  http://localhost:5000')
    print('  Login: admin / admin123')
    print('=' * 50)
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
