"""
Seed data script to populate all initial/historical data:
- Parties: BALAJI, MVS, MVS Builders & Infra, Buildcon, Supplier Co, etc.
- Employees: Murugan Loading Master, Ramesh Operator, Suresh Loader, etc.
- User Accounts: admin, ramesh_op, operator_2275, testadmin_stock
- Employee Groups & Piece Rates
- Material Inward, Outward, Payments & Adjustments
"""

from datetime import date, datetime
from werkzeug.security import generate_password_hash
from app import app
from models import (
    db, User, Party, Employee, EmployeeGroup, 
    JobRateSetting, MaterialInward, MaterialOutward, 
    Payment, Expense, PartyAdjustment, PartyProductRate,
    DashboardPreference, AlertSettings, Attendance, JobWageEntry
)

def seed_all_data():
    with app.app_context():
        print("--- Seeding All Historical Data into Database ---")
        db.create_all()

        # 1. Users
        users_data = [
            ('admin', 'admin123', 'admin', 'Nishanth (Owner)', 'nishanthissan1515@gmail.com', '8072416903'),
            ('ramesh_op', 'ramesh123', 'operator', 'Ramesh Operator', 'ramesh@plant.com', '9876543210'),
            ('operator_2275', 'operator123', 'operator', 'Operator 2275', 'operator_2275@plant.com', '9876543210'),
            ('testadmin_stock', 'admin123', 'owner', 'Stock Admin', 'stockadmin@plant.com', '9876543211')
        ]
        for uname, pwd, role, name, email, phone in users_data:
            u = User.query.filter_by(username=uname).first()
            if not u:
                u = User(
                    username=uname,
                    password_hash=generate_password_hash(pwd),
                    role=role,
                    name=name,
                    email=email,
                    phone=phone,
                    is_active=True
                )
                db.session.add(u)
            else:
                u.password_hash = generate_password_hash(pwd)
                u.role = role
                u.name = name
                u.email = email
                u.phone = phone
                u.is_active = True

        db.session.commit()
        print("[OK] Users seeded")

        # 2. Parties (including BALAJI, MVS, etc.)
        parties_data = [
            (1, 'BALAJI', 'both', '', '', '', 0.0, 0.0),
            (2, 'MVS', 'both', '9840012345', 'Site 4, Industrial Estate', '33AAACM1234F1Z5', 0.0, 5.5),
            (3, 'MVS Builders & Infra', 'customer', '9840012346', 'Highway Project Yard', '', 25000.0, 6.0),
            (4, 'Test Customer Buildcon', 'customer', '9876543210', '', '', 0.0, 0.0),
            (5, 'Test Ash Supplier Co', 'supplier', '9123456780', '', '', 0.0, 0.0),
            (6, 'AutoSave Party', 'customer', '9876543211', '', '', 0.0, 12.5),
            (7, 'TEST Early Dues Party', 'customer', '9876543210', '', '', 7500.0, 0.0),
            (8, 'Test Master Customer', 'customer', '9112233445', '', '', 5000.0, 5.5),
            (9, 'Test Master Supplier', 'supplier', '9112233446', '', '', -15000.0, 0.0),
            (10, 'Test Master Both', 'both', '9112233447', '', '', 0.0, 0.0),
        ]
        for pid, name, ptype, phone, addr, gstin, obal, srate in parties_data:
            p = Party.query.filter((Party.id == pid) | (Party.name == name)).first()
            if not p:
                p = Party(
                    id=pid,
                    name=name,
                    party_type=ptype,
                    phone=phone,
                    address=addr,
                    gstin=gstin,
                    opening_balance=obal,
                    default_selling_rate=srate
                )
                db.session.add(p)
            else:
                p.party_type = ptype
                if phone: p.phone = phone
                if obal: p.opening_balance = obal
                if srate: p.default_selling_rate = srate

        db.session.commit()
        print("[OK] Parties seeded (BALAJI, MVS, etc.)")

        # 3. Employees
        employees_data = [
            (1, 'Murugan Loading Master', 'Loading Gang Leader', '9876543210', 0.0, date(2026, 9, 1), True),
            (2, 'Ramesh Operator', 'Operator', '9876543210', 400.0, date(2026, 9, 12), True),
            (3, 'Suresh Loader', 'Loader', '9876543212', 350.0, date(2026, 9, 12), True),
            (4, 'Worker 1', 'Helper', '', 500.0, date(2026, 9, 7), True),
            (5, 'Master Worker A', 'Operator', '9988776651', 0.0, date(2026, 9, 12), True),
            (6, 'Master Worker B', 'Loader', '9988776652', 0.0, date(2026, 9, 12), False),
            (7, 'TEST Bot Worker', 'Operator', '9123456780', 500.0, date(2026, 9, 12), True),
            (8, 'TEST Gang Worker 1', 'Operator', '9000000001', 500.0, date(2026, 9, 12), True),
            (9, 'TEST Gang Worker 2', 'Loader', '9000000002', 450.0, date(2026, 9, 12), True),
            (10, 'Test Worker A', 'Operator', '', 0.0, date(2026, 9, 8), True),
            (11, 'Test Worker B', 'Loader', '', 0.0, date(2026, 9, 8), True),
            (12, 'Test Worker C', 'Helper', '', 0.0, date(2026, 9, 8), True),
            (13, 'Worker Stock 1', 'Molder', '', 0.0, date(2026, 9, 8), True),
        ]
        for eid, name, role, phone, wage, jdate, active in employees_data:
            e = Employee.query.filter((Employee.id == eid) | (Employee.name == name)).first()
            if not e:
                e = Employee(
                    id=eid,
                    name=name,
                    role=role,
                    phone=phone,
                    daily_wage=wage,
                    joining_date=jdate,
                    is_active=active
                )
                db.session.add(e)
            else:
                e.role = role
                if phone: e.phone = phone
                e.daily_wage = wage
                e.is_active = active

        db.session.commit()
        print("[OK] Employees seeded")

        # 4. Employee Groups
        groups_data = [
            (1, 'Brick Production Team (Gang 1)', 'Group dedicated to daily Fly Ash Brick manufacturing', 'Production (Per Piece)', 'Fly Ash Brick 9"x4"x3" (Standard)'),
            (2, 'Solid & Hollow Block Gang (Gang 2)', 'Group for solid and hollow block machine production', 'Production (Per Piece)', 'Solid Block 6"'),
            (3, 'Loading & Vehicle Dispatch Team', 'Labor gang for vehicle loading and transport', 'Loading Only', 'Fly Ash Brick 9"x4"x3" (Standard)'),
            (4, 'Unloading & Material Handling Gang', 'Labor team for unloading raw materials and bricks', 'Unloading Only', 'Fly Ash Brick 9"x4"x3" (Standard)'),
            (5, 'TEST Brick Production Gang', 'Production team for 9x4x3 bricks', None, None)
        ]
        for gid, gname, desc, jtype, prod in groups_data:
            g = EmployeeGroup.query.filter((EmployeeGroup.id == gid) | (EmployeeGroup.name == gname)).first()
            if not g:
                g = EmployeeGroup(
                    id=gid,
                    name=gname,
                    description=desc,
                    default_job_type=jtype,
                    default_product_name=prod,
                    is_active=True
                )
                db.session.add(g)

        db.session.commit()
        print("[OK] Employee Groups seeded")

        # 5. Group Memberships
        g1 = EmployeeGroup.query.get(1)
        g2 = EmployeeGroup.query.get(2)
        g3 = EmployeeGroup.query.get(3)
        g4 = EmployeeGroup.query.get(4)
        emps = Employee.query.filter(Employee.id.in_([1, 2, 3, 4, 5])).all()
        for g in [g1, g2, g3, g4]:
            if g:
                for emp in emps:
                    if emp not in g.members:
                        g.members.append(emp)

        db.session.commit()

        # 6. Job Rate Settings (Piece rates)
        standard_rates = [
            ('Fly Ash Brick 9"x4"x3" (Standard)', 'Production (Per Piece)', 0.60, 'Pieces / Pcs', 105.0, 5.0),
            ('Fly Ash Brick 9"x4"x3" (Standard)', 'Loading Only', 0.25, 'Pieces / Pcs', 105.0, 5.0),
            ('Fly Ash Brick 9"x4"x3" (Standard)', 'Unloading Only', 0.20, 'Pieces / Pcs', 105.0, 5.0),
            ('Fly Ash Brick 9"x4"x3" (Standard)', 'Both Loading & Unloading', 0.45, 'Pieces / Pcs', 105.0, 5.0),
            ('Fly Ash Brick Modular (190 x 90 x 90 mm)', 'Production (Per Piece)', 0.55, 'Pieces / Pcs', 105.0, 5.0),
            ('Fly Ash Brick Modular (190 x 90 x 90 mm)', 'Both Loading & Unloading', 0.40, 'Pieces / Pcs', 105.0, 5.0),
            ('Solid Block 4"', 'Production (Per Piece)', 1.20, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 4"', 'Loading Only', 0.35, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 4"', 'Unloading Only', 0.30, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 4"', 'Both Loading & Unloading', 0.65, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 6"', 'Production (Per Piece)', 1.60, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 6"', 'Loading Only', 0.45, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 6"', 'Unloading Only', 0.40, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 6"', 'Both Loading & Unloading', 0.85, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 8"', 'Production (Per Piece)', 2.00, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 8"', 'Loading Only', 0.55, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 8"', 'Unloading Only', 0.50, 'Pieces / Pcs', 60.0, 3.0),
            ('Solid Block 8"', 'Both Loading & Unloading', 1.05, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 4" (400 x 200 x 100 mm)', 'Production (Per Piece)', 1.00, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 4" (400 x 200 x 100 mm)', 'Both Loading & Unloading', 0.55, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 6" (400 x 200 x 150 mm)', 'Production (Per Piece)', 1.40, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 6" (400 x 200 x 150 mm)', 'Loading Only', 0.40, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 6" (400 x 200 x 150 mm)', 'Unloading Only', 0.35, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 6" (400 x 200 x 150 mm)', 'Both Loading & Unloading', 0.75, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 8" (400 x 200 x 200 mm)', 'Production (Per Piece)', 1.80, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 8" (400 x 200 x 200 mm)', 'Both Loading & Unloading', 0.95, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 9" (400 x 200 x 225 mm)', 'Production (Per Piece)', 2.00, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 9" (400 x 200 x 225 mm)', 'Both Loading & Unloading', 1.05, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 12" (400 x 200 x 300 mm)', 'Production (Per Piece)', 2.50, 'Pieces / Pcs', 60.0, 3.0),
            ('Hollow Block 12" (400 x 200 x 300 mm)', 'Both Loading & Unloading', 1.35, 'Pieces / Pcs', 60.0, 3.0),
        ]
        for prod, job, rate, unit, tray, waste in standard_rates:
            setting = JobRateSetting.query.filter_by(product_name=prod, job_type=job).first()
            if not setting:
                setting = JobRateSetting(
                    product_name=prod,
                    job_type=job,
                    rate_per_piece=rate,
                    unit=unit,
                    pieces_per_tray=tray,
                    wastage_per_tray=waste
                )
                db.session.add(setting)

        db.session.commit()
        print("[OK] Piece Rates seeded")

        # 7. Material Inward
        inward_samples = [
            (1, date(2026, 9, 18), 1, 'Fly Ash', 35.5, 'Ton', 'TN-34-AB-1234', 850.0, 30175.0, 'Thermal Plant Fly Ash'),
            (2, date(2026, 9, 17), 5, 'Cement', 200.0, 'Bags', 'TN-34-CD-5678', 380.0, 76000.0, 'OPC 53 Grade Cement'),
            (3, date(2026, 9, 16), 5, 'Stone Dust', 25.0, 'Ton', 'TN-34-EF-9012', 450.0, 11250.0, 'Quarry dust batch')
        ]
        for iid, idate, pid, mtype, qty, unit, vno, rate, amt, notes in inward_samples:
            if not MaterialInward.query.get(iid):
                db.session.add(MaterialInward(
                    id=iid,
                    date=idate,
                    party_id=pid,
                    material_type=mtype,
                    quantity_mt=qty,
                    quantity_unit=unit,
                    vehicle_no=vno,
                    rate=rate,
                    amount=amt,
                    notes=notes
                ))

        # 8. Material Outward
        outward_samples = [
            (1, date(2026, 9, 18), 1, 'Fly Ash Brick', 4500.0, 'Pieces / Pcs', 'TN-34-GH-3456', 5.5, 24750.0, 'Site 1 delivery (BALAJI)'),
            (2, date(2026, 9, 18), 2, 'Paver Block', 2.0, 'Load / Trip', 'TN-34-IJ-7890', 6000.0, 12000.0, 'Commercial complex delivery (MVS)'),
            (3, date(2026, 9, 17), 3, 'Solid Block 6"', 1200.0, 'Pieces / Pcs', 'TN-34-KL-1122', 32.0, 38400.0, 'MVS Builders Project')
        ]
        for oid, odate, pid, mtype, qty, unit, vno, rate, amt, notes in outward_samples:
            if not MaterialOutward.query.get(oid):
                db.session.add(MaterialOutward(
                    id=oid,
                    date=odate,
                    party_id=pid,
                    material_type=mtype,
                    quantity_mt=qty,
                    quantity_unit=unit,
                    vehicle_no=vno,
                    rate=rate,
                    amount=amt,
                    notes=notes
                ))

        # 9. Payments
        payments_samples = [
            (1, date(2026, 9, 18), 1, 'received', 15000.0, 'upi', 'UPI-BALAJI-901', 'Partial dispatch settlement'),
            (2, date(2026, 9, 18), 2, 'received', 12000.0, 'bank_transfer', 'NEFT-MVS-402', 'Full payment for paver blocks'),
            (3, date(2026, 9, 17), 8, 'received', 5000.0, 'upi', 'UPI-TEST-1234', 'Test Full Settlement')
        ]
        for pay_id, pdate, pid, ptype, amt, mode, ref, notes in payments_samples:
            if not Payment.query.get(pay_id):
                db.session.add(Payment(
                    id=pay_id,
                    date=pdate,
                    party_id=pid,
                    payment_type=ptype,
                    amount=amt,
                    mode=mode,
                    reference_no=ref,
                    notes=notes
                ))

        # 10. Expenses
        expenses_samples = [
            (1, date(2026, 9, 7), 'Diesel / Fuel', 'Diesel for Generator & Forklift (50 Liters)', 4750.0, 'Cash', 'Indian Oil Petrol Pump', 'IOCL-9842', 'Generator power backup fuel'),
            (2, date(2026, 9, 7), 'Electricity & Power', 'Monthly Plant Electricity Bill', 12500.0, 'Bank Transfer', 'TANGEDCO / Electricity Board', 'EB-SEP-2026', 'Plant main HT power line')
        ]
        for eid, edate, cat, title, amt, pmode, pto, ref, notes in expenses_samples:
            if not Expense.query.get(eid):
                db.session.add(Expense(
                    id=eid,
                    date=edate,
                    category=cat,
                    title=title,
                    amount=amt,
                    payment_mode=pmode,
                    paid_to=pto,
                    reference_no=ref,
                    notes=notes
                ))

        # 11. Party Adjustments
        adj_samples = [
            (1, 1, date(2026, 9, 1), 'past_unpaid_due', 15000.0, 'Opening August site supply balance', 'BALAJI-AUG-01'),
            (2, 2, date(2026, 9, 1), 'past_unpaid_due', 20000.0, 'August project dues', 'MVS-AUG-02')
        ]
        for aid, pid, adate, atype, amt, reason, ref in adj_samples:
            if not PartyAdjustment.query.get(aid):
                db.session.add(PartyAdjustment(
                    id=aid,
                    party_id=pid,
                    date=adate,
                    adjustment_type=atype,
                    amount=amt,
                    reason=reason,
                    reference_no=ref
                ))

        # 12. Alert Settings & Dashboard Preference
        if not AlertSettings.query.get(1):
            db.session.add(AlertSettings(
                id=1,
                email_enabled=True,
                telegram_enabled=True,
                anti_spam_enabled=True,
                frequency='instant',
                cooldown_minutes=15,
                max_alerts_per_day=50,
                digest_delivery_time='19:00',
                alert_roles='owner,admin'
            ))

        if not DashboardPreference.query.filter_by(user_id=1).first():
            db.session.add(DashboardPreference(
                user_id=1,
                show_today_inward=True,
                show_today_outward=True,
                show_expenses=True,
                show_outstanding=True,
                show_production_labor=True,
                show_stock_overview=True,
                show_weekly_performance=True,
                show_recent_inward=True,
                show_recent_outward=True,
                show_recent_jobs=True,
                show_recent_expenses=True,
                show_quick_actions=True
            ))

        db.session.commit()
        print("[OK] All transactions, expenses, payments and settings successfully seeded!")

if __name__ == '__main__':
    seed_all_data()
