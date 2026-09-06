import os
import sqlite3
from flask import Flask, redirect, url_for, send_from_directory
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from config import Config
from models import db, User


def _migrate_db():
    """Ensure newly added columns exist in SQLite tables."""
    if not Config.SQLALCHEMY_DATABASE_URI.startswith('sqlite:///'):
        return
    db_path = Config.SQLALCHEMY_DATABASE_URI.replace('sqlite:///', '')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Migrations definition
        table_migrations = {
            'material_inward': [('quantity_unit', "VARCHAR(20) DEFAULT 'Ton'")],
            'material_outward': [('quantity_unit', "VARCHAR(20) DEFAULT 'Ton'")],
            'user': [
                ('name', "VARCHAR(100) DEFAULT 'Admin'"),
                ('email', "VARCHAR(120) DEFAULT 'admin@flyash.com'"),
                ('phone', "VARCHAR(20)"),
                ('is_active', "BOOLEAN DEFAULT 1"),
                ('created_at', "DATETIME")
            ],
            'login_history': [
                ('user_id', "INTEGER"),
                ('email', "VARCHAR(120)"),
                ('user_role', "VARCHAR(30)")
            ],
            'job_wage_entry': [
                ('group_id', "INTEGER")
            ],
            'alert_settings': [
                ('owner_name', "VARCHAR(100) DEFAULT 'Nishanth (Owner)'"),
                ('owner_email', "VARCHAR(120) DEFAULT 'nishanthissan1515@gmail.com'"),
                ('email_alerts_enabled', "BOOLEAN DEFAULT 1"),
                ('smtp_host', "VARCHAR(100) DEFAULT 'smtp.gmail.com'"),
                ('smtp_port', "INTEGER DEFAULT 587"),
                ('smtp_user', "VARCHAR(120)"),
                ('smtp_password', "VARCHAR(120)"),
                ('alert_on_all_users', "BOOLEAN DEFAULT 1")
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
                db.session.add(JobRateSetting(product_name=prod, job_type=job, rate_per_piece=rate, unit=unit))
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

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(parties_bp)
    app.register_blueprint(reports_bp)

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

    # Template context processors
    @app.context_processor
    def inject_globals():
        return {
            'app_name': 'FlyAsh Manager',
            'app_version': '1.0.0',
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
    app.run(debug=True, host='0.0.0.0', port=5000)
