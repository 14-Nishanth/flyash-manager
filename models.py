from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Application user for login/authentication and staff management."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, index=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='admin')  # owner, admin, operator, accountant, staff
    phone = db.Column(db.String(20))
    preferred_language = db.Column(db.String(10), default='en')  # en, hi, bho, ta, ml, te, kn, bn, mr, gu, pa, or
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username} ({self.email})>'


class LoginHistory(db.Model):
    """Tracks login alerts, sign in history, IP, device and timestamps."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120))
    user_role = db.Column(db.String(30))
    ip_address = db.Column(db.String(50))
    user_agent = db.Column(db.String(255))
    status = db.Column(db.String(20), default='SUCCESS')  # SUCCESS, FAILED
    timestamp = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<LoginHistory {self.username} {self.status} {self.timestamp}>'


class AlertSettings(db.Model):
    """Configuration for mobile/SMS/WhatsApp/Telegram and Email alerts."""
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=True)
    channel = db.Column(db.String(20), default='whatsapp')  # whatsapp, telegram, sms, webhook, email, both
    phone_number = db.Column(db.String(20))  # Owner's mobile number
    owner_name = db.Column(db.String(100), default='Nishanth (Owner)')
    owner_email = db.Column(db.String(120), default='nishanthissan1515@gmail.com')  # Owner's email address
    email_alerts_enabled = db.Column(db.Boolean, default=True)
    smtp_host = db.Column(db.String(100), default='smtp.gmail.com')
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(120), default='')
    smtp_password = db.Column(db.String(120), default='')
    api_key = db.Column(db.String(255))      # WhatsApp / Fast2SMS API Key or Telegram Bot Token
    chat_id = db.Column(db.String(100))      # Telegram chat ID or webhook secret
    webhook_url = db.Column(db.String(255))
    alert_on_all_users = db.Column(db.Boolean, default=True)  # Alert when staff/other users log in
    cooldown_minutes = db.Column(db.Integer, default=30)  # Cooldown between alerts per user (mins)
    max_alerts_per_day = db.Column(db.Integer, default=3)  # Maximum alerts per user per day
    alert_on_first_login_only = db.Column(db.Boolean, default=False)  # Alert only once on first daily login
    alert_on_owner_login = db.Column(db.Boolean, default=False)  # Alert on owner/admin login
    alert_on_staff_login = db.Column(db.Boolean, default=True)  # Alert on staff logins
    alert_on_failed_attempts = db.Column(db.Boolean, default=True)  # Alert on wrong passwords
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<AlertSettings {self.channel} enabled={self.is_enabled}>'


class JobRateSetting(db.Model):
    """Configurable piece-rate for different products and operations (Production, Loading, Unloading)."""
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False) # e.g. Fly Ash Brick, Solid Block 4", Solid Block 6", Hollow Block 6"
    job_type = db.Column(db.String(50), nullable=False)      # Production, Loading Only, Unloading Only, Both Loading & Unloading
    rate_per_piece = db.Column(db.Float, nullable=False, default=0.0) # Rate per piece/unit (₹)
    pieces_per_tray = db.Column(db.Float, default=105.0)     # Standard stack capacity per tray (e.g. 105 pcs standard)
    wastage_per_tray = db.Column(db.Float, default=5.0)      # Daily breakage wastage deducted per tray (e.g. 5 pcs)
    opening_stock = db.Column(db.Float, default=0.0)         # Base yard stock opening balance (Pcs)
    unit = db.Column(db.String(30), default='Pieces / Pcs')
    notes = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('product_name', 'job_type', name='uq_product_job_rate'),)

    def __repr__(self):
        return f'<JobRateSetting {self.product_name} - {self.job_type}: ₹{self.rate_per_piece} (Tray:{self.pieces_per_tray}, Waste:{self.wastage_per_tray})>'


# Association table for Many-to-Many relationship between EmployeeGroup and Employee
employee_group_members = db.Table('employee_group_members',
    db.Column('group_id', db.Integer, db.ForeignKey('employee_group.id', ondelete='CASCADE'), primary_key=True),
    db.Column('employee_id', db.Integer, db.ForeignKey('employee.id', ondelete='CASCADE'), primary_key=True)
)


class EmployeeGroup(db.Model):
    """Labor gang / team for piece-rate group jobs."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False) # e.g. Brick Production Gang, Solid Block Team, Loading Team
    description = db.Column(db.String(255))
    default_job_type = db.Column(db.String(50))
    default_product_name = db.Column(db.String(100))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    members = db.relationship('Employee', secondary=employee_group_members, lazy='subquery',
                              backref=db.backref('groups', lazy=True))

    def __repr__(self):
        return f'<EmployeeGroup {self.name} ({len(self.members)} members)>'


class JobWageEntry(db.Model):
    """Daily job / piece-rate work record divided among assigned workers in a group."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    group_id = db.Column(db.Integer, db.ForeignKey('employee_group.id'), nullable=True) # Optional assigned labor group
    job_type = db.Column(db.String(50), nullable=False)  # Production, Loading Only, Both Loading & Unloading, Unloading Only, Custom
    product_name = db.Column(db.String(100), nullable=False)  # e.g., Hollow Block 6", Fly Ash Brick 9x4x3, Solid Block 6"
    tray_count = db.Column(db.Float, default=0.0)             # Number of trays/tracks (e.g. 36)
    pieces_per_tray = db.Column(db.Float, default=105.0)       # Standard stack per tray (e.g. 105)
    wastage_per_tray = db.Column(db.Float, default=5.0)        # Wastage pieces deducted per tray (e.g. 5)
    total_wastage = db.Column(db.Float, default=0.0)          # Total wastage pieces (e.g. 36 * 5 = 180)
    gross_quantity = db.Column(db.Float, default=0.0)         # Actual physical stock produced (e.g. 36 * 105 = 3780)
    quantity = db.Column(db.Float, nullable=False)            # Payable wage quantity (e.g. 3780 - 180 = 3600)
    unit = db.Column(db.String(30), default='Pieces / Pcs')
    rate_per_unit = db.Column(db.Float, nullable=False, default=0.0)
    gross_amount = db.Column(db.Float, default=0.0)           # Full production expense value (e.g. 3780 * 0.60 = ₹2268.00)
    wastage_amount = db.Column(db.Float, default=0.0)         # Amount cut from workers for wastage (e.g. 180 * 0.60 = ₹108.00)
    total_amount = db.Column(db.Float, nullable=False, default=0.0) # Net salary paid to workers (e.g. 3600 * 0.60 = ₹2160.00)
    worker_count = db.Column(db.Integer, nullable=False, default=1)
    wage_per_worker = db.Column(db.Float, nullable=False, default=0.0)
    vehicle_no = db.Column(db.String(30))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    group = db.relationship('EmployeeGroup', backref='job_entries', lazy=True)
    allocations = db.relationship('EmployeeJobAllocation', backref='job_entry', lazy=True,
                                  cascade='all, delete-orphan')

    @property
    def calculated_gross_amount(self):
        if self.gross_amount and self.gross_amount > 0:
            return self.gross_amount
        g_qty = self.gross_quantity if (self.gross_quantity and self.gross_quantity > 0) else self.quantity
        return round(g_qty * self.rate_per_unit, 2)

    @property
    def calculated_wastage_amount(self):
        if self.wastage_amount and self.wastage_amount > 0:
            return self.wastage_amount
        w_qty = self.total_wastage or 0.0
        return round(w_qty * self.rate_per_unit, 2)

    def __repr__(self):
        return f'<JobWageEntry {self.date} {self.job_type} Gross:₹{self.calculated_gross_amount} WasteCut:₹{self.calculated_wastage_amount} NetSalary:₹{self.total_amount}>'


class Employee(db.Model):
    """Company employee record."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15))
    role = db.Column(db.String(50))
    daily_wage = db.Column(db.Float, default=0)
    joining_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendances = db.relationship('Attendance', backref='employee', lazy=True,
                                  cascade='all, delete-orphan')
    job_allocations = db.relationship('EmployeeJobAllocation', backref='employee', lazy=True,
                                      cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Employee {self.name}>'


class EmployeeJobAllocation(db.Model):
    """Individual worker share of a daily job pool."""
    id = db.Column(db.Integer, primary_key=True)
    job_entry_id = db.Column(db.Integer, db.ForeignKey('job_wage_entry.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    allocated_wage = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<EmployeeJobAllocation Emp:{self.employee_id} Job:{self.job_entry_id} ₹{self.allocated_wage}>'


class Attendance(db.Model):
    """Daily attendance record for an employee."""
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default='present')  # present, absent, half-day
    notes = db.Column(db.String(200))

    __table_args__ = (db.UniqueConstraint('employee_id', 'date', name='uq_employee_date'),)

    def __repr__(self):
        return f'<Attendance {self.employee_id} {self.date} {self.status}>'


class Party(db.Model):
    """Supplier or customer party."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    party_type = db.Column(db.String(20), default='customer')  # supplier, customer, both
    phone = db.Column(db.String(15))
    address = db.Column(db.Text)
    gstin = db.Column(db.String(15))
    opening_balance = db.Column(db.Float, default=0)  # positive = they owe us, negative = we owe them
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inwards = db.relationship('MaterialInward', backref='party', lazy=True,
                              cascade='all, delete-orphan')
    outwards = db.relationship('MaterialOutward', backref='party', lazy=True,
                               cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='party', lazy=True,
                               cascade='all, delete-orphan')

    def get_outstanding(self):
        """Calculate outstanding amount for this party.
        Positive = party owes us (receivable), Negative = we owe party (payable).
        Outstanding = opening_balance + total_outward - total_inward - payments_received + payments_paid
        """
        total_outward = sum(m.amount for m in self.outwards) or 0
        total_inward = sum(m.amount for m in self.inwards) or 0
        payments_received = sum(p.amount for p in self.payments if p.payment_type == 'received') or 0
        payments_paid = sum(p.amount for p in self.payments if p.payment_type == 'paid') or 0
        return self.opening_balance + total_outward - total_inward - payments_received + payments_paid

    def __repr__(self):
        return f'<Party {self.name}>'


class MaterialInward(db.Model):
    """Record of material received from a supplier."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    material_type = db.Column(db.String(50), default='Fly Ash')
    quantity_mt = db.Column(db.Float, nullable=False)
    quantity_unit = db.Column(db.String(20), default='Ton')
    vehicle_no = db.Column(db.String(20))
    rate = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MaterialInward {self.date} {self.quantity_mt}MT>'


class MaterialOutward(db.Model):
    """Record of material dispatched to a customer."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    material_type = db.Column(db.String(50), default='Fly Ash')
    quantity_mt = db.Column(db.Float, nullable=False)
    quantity_unit = db.Column(db.String(20), default='Ton')
    vehicle_no = db.Column(db.String(20))
    rate = db.Column(db.Float, default=0)
    amount = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MaterialOutward {self.date} {self.quantity_mt}MT>'


class Payment(db.Model):
    """Payment received from or paid to a party."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    party_id = db.Column(db.Integer, db.ForeignKey('party.id'), nullable=False)
    payment_type = db.Column(db.String(20), nullable=False)  # received, paid
    amount = db.Column(db.Float, nullable=False)
    mode = db.Column(db.String(20), default='cash')  # cash, bank, upi, cheque
    reference_no = db.Column(db.String(50))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Payment {self.payment_type} ₹{self.amount}>'


class Expense(db.Model):
    """Daily operational and plant expense record."""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, default=date.today)
    category = db.Column(db.String(60), nullable=False, default='Diesel / Fuel')
    title = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_mode = db.Column(db.String(30), default='cash')  # cash, upi, bank, cheque
    paid_to = db.Column(db.String(100))  # Vendor / person name
    reference_no = db.Column(db.String(50))  # Bill / invoice / txn ref
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Expense {self.date} {self.category} ₹{self.amount}>'
