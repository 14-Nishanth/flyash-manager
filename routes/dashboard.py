from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Employee, Party, MaterialInward, MaterialOutward, JobWageEntry, JobRateSetting, Expense, Payment, PartyAdjustment
from datetime import date, timedelta
from sqlalchemy import func
import calendar

bp = Blueprint('dashboard', __name__, url_prefix='/')


def format_quantity_summary(entries):
    """Summarizes quantities grouped by unit, e.g., '5,000 Pieces • 45.0 MT • 2 Loads'."""
    if not entries:
        return '0 Units'
    unit_totals = {}
    for e in entries:
        qty = e.quantity_mt or 0.0
        u = (e.quantity_unit or 'Pieces / Pcs').strip()
        u_lower = u.lower()
        if 'piece' in u_lower or 'pcs' in u_lower or 'nos' in u_lower:
            key = 'Pieces'
        elif 'ton' in u_lower or 'mt' in u_lower:
            key = 'MT'
        elif 'load' in u_lower or 'trip' in u_lower:
            key = 'Loads'
        elif 'bag' in u_lower:
            key = 'Bags'
        elif 'cft' in u_lower:
            key = 'CFT'
        elif 'kg' in u_lower:
            key = 'Kg'
        else:
            key = u
        unit_totals[key] = unit_totals.get(key, 0.0) + qty
    
    parts = []
    # Display pieces, MT, loads, bags first in standard ERP order
    for k in ['Pieces', 'MT', 'Loads', 'Bags', 'CFT', 'Kg']:
        if k in unit_totals and unit_totals[k] > 0:
            if k in ('Pieces', 'Bags'):
                parts.append(f"{unit_totals[k]:,.0f} {k}")
            else:
                parts.append(f"{unit_totals[k]:,.1f} {k}")
            del unit_totals[k]
    for k, v in unit_totals.items():
        if v > 0:
            parts.append(f"{v:,.1f} {k}")
    
    return " • ".join(parts) if parts else "0 Units"


@bp.route('/')
@login_required
def index():
    today = date.today()
    
    # 1. Basic Counts
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_parties = Party.query.count()
    
    # 2. Today's Inward & Outward (Accurate multi-unit breakdown)
    today_inward_entries = MaterialInward.query.filter(MaterialInward.date == today).all()
    today_inward_summary = format_quantity_summary(today_inward_entries)
    today_inward_amount = sum(e.amount for e in today_inward_entries if e.amount) or 0.0

    today_outward_entries = MaterialOutward.query.filter(MaterialOutward.date == today).all()
    today_outward_summary = format_quantity_summary(today_outward_entries)
    today_outward_amount = sum(e.amount for e in today_outward_entries if e.amount) or 0.0

    # 3. Operational Expenses
    first_of_month = today.replace(day=1)
    today_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0
    month_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= first_of_month, Expense.date <= today).scalar() or 0.0

    # 4. Piece-Rate Job Metrics (Separated into Production & Loading/Unloading)
    today_jobs_list = JobWageEntry.query.filter(JobWageEntry.date == today).all()
    today_jobs_count = len(today_jobs_list)
    today_prod_jobs = [j for j in today_jobs_list if j.is_production]
    today_load_jobs = [j for j in today_jobs_list if j.is_outward]

    from routes.employees import calculate_net_job_quantity
    today_prod_pieces = sum((j.gross_quantity if (j.gross_quantity and j.gross_quantity > 0) else j.quantity) for j in today_prod_jobs)
    today_prod_amount = sum(j.total_amount for j in today_prod_jobs)
    
    today_load_pieces = calculate_net_job_quantity(today_load_jobs)
    today_load_amount = sum(j.total_amount for j in today_load_jobs)

    today_jobs_pieces = calculate_net_job_quantity(today_jobs_list)
    today_jobs_amount = sum(j.total_amount for j in today_jobs_list)

    # 5. Fast Bulk Outstanding Calculation (0 loop queries)
    parties = Party.query.all()
    inward_sums = dict(db.session.query(MaterialInward.party_id, func.sum(MaterialInward.amount)).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(MaterialOutward.party_id, func.sum(MaterialOutward.amount)).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())
    debit_adjs = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_unpaid_due', 'debit'])).group_by(PartyAdjustment.party_id).all())
    credit_adjs = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_advance', 'discount_waiver', 'credit'])).group_by(PartyAdjustment.party_id).all())

    total_receivable = 0.0
    total_payable = 0.0
    for p in parties:
        bal = ((p.opening_balance or 0.0) 
               + outward_sums.get(p.id, 0.0) 
               - inward_sums.get(p.id, 0.0) 
               - rec_sums.get(p.id, 0.0) 
               + paid_sums.get(p.id, 0.0) 
               + debit_adjs.get(p.id, 0.0) 
               - credit_adjs.get(p.id, 0.0))
        if bal > 0.01:
            total_receivable += bal
        elif bal < -0.01:
            total_payable += abs(bal)

    # 6. Recent records
    recent_inward = MaterialInward.query.order_by(MaterialInward.date.desc(), MaterialInward.id.desc()).limit(5).all()
    recent_outward = MaterialOutward.query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).limit(5).all()
    recent_jobs = JobWageEntry.query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()

    # 7. Fast Material Stock Overview
    in_grouped = dict(db.session.query(MaterialInward.material_type, func.sum(MaterialInward.quantity_mt)).group_by(MaterialInward.material_type).all())
    out_grouped = dict(db.session.query(MaterialOutward.material_type, func.sum(MaterialOutward.quantity_mt)).group_by(MaterialOutward.material_type).all())

    stock_overview = []
    for mat in ['Cement', 'Jelly', 'Fly Ash', 'Sand']:
        in_qty = sum(qty for k, qty in in_grouped.items() if mat.lower() in (k or '').lower())
        out_qty = sum(qty for k, qty in out_grouped.items() if mat.lower() in (k or '').lower())
        stock_overview.append({
            'name': mat,
            'inward': in_qty,
            'outward': out_qty,
            'balance': round(in_qty - out_qty, 2)
        })

    # 8. Monthly performance data for last 6 months (Clean Tabular Data - 0 Graphs)
    monthly_performance = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=today.day - 1)
        for _ in range(i):
            d = d - timedelta(days=1)
            d = d - timedelta(days=d.day - 1)
        
        target_month = d.month
        target_year = d.year
        month_label = f"{calendar.month_abbr[target_month]} {target_year}"
        
        first_d = date(target_year, target_month, 1)
        last_d = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])

        in_entries = MaterialInward.query.filter(MaterialInward.date >= first_d, MaterialInward.date <= last_d).all()
        out_entries = MaterialOutward.query.filter(MaterialOutward.date >= first_d, MaterialOutward.date <= last_d).all()

        in_m = sum(e.amount for e in in_entries if e.amount) or 0.0
        out_m = sum(e.amount for e in out_entries if e.amount) or 0.0
        in_summary = format_quantity_summary(in_entries)
        out_summary = format_quantity_summary(out_entries)

        monthly_performance.append({
            'label': month_label,
            'inward_amount': round(in_m, 2),
            'outward_amount': round(out_m, 2),
            'inward_qty_summary': in_summary,
            'outward_qty_summary': out_summary,
            'net_balance': round(out_m - in_m, 2),
            'is_current': (target_month == today.month and target_year == today.year)
        })

    return render_template('dashboard.html',
                           total_employees=total_employees,
                           total_parties=total_parties,
                           today_inward_summary=today_inward_summary,
                           today_inward_amount=today_inward_amount,
                           today_outward_summary=today_outward_summary,
                           today_outward_amount=today_outward_amount,
                           today_jobs_count=today_jobs_count,
                           today_jobs_pieces=today_jobs_pieces,
                           today_jobs_amount=today_jobs_amount,
                           today_prod_pieces=today_prod_pieces,
                           today_prod_amount=today_prod_amount,
                           today_load_pieces=today_load_pieces,
                           today_load_amount=today_load_amount,
                           today_expenses=today_expenses,
                           month_expenses=month_expenses,
                           total_receivable=total_receivable,
                           total_payable=total_payable,
                           recent_inward=recent_inward,
                           recent_outward=recent_outward,
                           recent_jobs=recent_jobs,
                           recent_expenses=recent_expenses,
                           stock_overview=stock_overview,
                           monthly_performance=monthly_performance)
