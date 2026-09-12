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
    mon = today - timedelta(days=today.weekday())
    sun = mon + timedelta(days=6)
    
    # 1. Basic Counts
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_parties = Party.query.count()
    
    # 2. Today's Inward & Outward
    today_inward_entries = MaterialInward.query.filter(MaterialInward.date == today).all()
    today_inward_summary = format_quantity_summary(today_inward_entries)
    today_inward_amount = sum(e.amount for e in today_inward_entries if e.amount) or 0.0

    today_outward_entries = MaterialOutward.query.filter(MaterialOutward.date == today).all()
    today_outward_summary = format_quantity_summary(today_outward_entries)
    today_outward_amount = sum(e.amount for e in today_outward_entries if e.amount) or 0.0

    # 3. Weekly Inward & Outward (Current Week: Mon-Sun)
    week_inward_entries = MaterialInward.query.filter(MaterialInward.date >= mon, MaterialInward.date <= sun).all()
    week_inward_summary = format_quantity_summary(week_inward_entries)
    week_inward_amount = sum(e.amount for e in week_inward_entries if e.amount) or 0.0

    week_outward_entries = MaterialOutward.query.filter(MaterialOutward.date >= mon, MaterialOutward.date <= sun).all()
    week_outward_summary = format_quantity_summary(week_outward_entries)
    week_outward_amount = sum(e.amount for e in week_outward_entries if e.amount) or 0.0

    # 4. Operational Expenses (Today, This Week, This Month)
    first_of_month = today.replace(day=1)
    today_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0
    week_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= mon, Expense.date <= sun).scalar() or 0.0
    month_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= first_of_month, Expense.date <= today).scalar() or 0.0

    # 5. Piece-Rate Job Metrics (Today & This Week)
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

    week_jobs_list = JobWageEntry.query.filter(JobWageEntry.date >= mon, JobWageEntry.date <= sun).all()
    week_prod_jobs = [j for j in week_jobs_list if j.is_production]
    week_load_jobs = [j for j in week_jobs_list if j.is_outward]
    week_prod_pieces = sum((j.gross_quantity if (j.gross_quantity and j.gross_quantity > 0) else j.quantity) for j in week_prod_jobs)
    week_prod_amount = sum(j.total_amount for j in week_prod_jobs)
    week_load_pieces = calculate_net_job_quantity(week_load_jobs)
    week_load_amount = sum(j.total_amount for j in week_load_jobs)
    week_wages_amount = sum(j.total_amount for j in week_jobs_list)

    # 6. Outstanding Dues
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

    # 7. Recent records
    recent_inward = MaterialInward.query.order_by(MaterialInward.date.desc(), MaterialInward.id.desc()).limit(5).all()
    recent_outward = MaterialOutward.query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).limit(5).all()
    recent_jobs = JobWageEntry.query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()

    # 8. Material Stock Overview
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

    # 9. Weekly Performance Representation (Last 6 Weeks Breakdown)
    weekly_performance = []
    for i in range(5, -1, -1):
        w_start = mon - timedelta(days=7 * i)
        w_end = w_start + timedelta(days=6)
        w_num = w_start.isocalendar()[1]
        w_label = f"Week {w_num} ({w_start.strftime('%d %b')} - {w_end.strftime('%d %b')})"

        w_in = MaterialInward.query.filter(MaterialInward.date >= w_start, MaterialInward.date <= w_end).all()
        w_out = MaterialOutward.query.filter(MaterialOutward.date >= w_start, MaterialOutward.date <= w_end).all()
        w_jobs = JobWageEntry.query.filter(JobWageEntry.date >= w_start, JobWageEntry.date <= w_end).all()
        w_exp = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= w_start, Expense.date <= w_end).scalar() or 0.0

        in_amt = sum(e.amount for e in w_in if e.amount) or 0.0
        out_amt = sum(e.amount for e in w_out if e.amount) or 0.0
        prod_pcs = sum((j.gross_quantity if (j.gross_quantity and j.gross_quantity > 0) else j.quantity) for j in w_jobs if j.is_production)
        load_pcs = sum(j.quantity for j in w_jobs if j.is_outward)
        wage_amt = sum(j.total_amount for j in w_jobs)

        weekly_performance.append({
            'week_number': w_num,
            'label': w_label,
            'from_date': w_start.strftime('%Y-%m-%d'),
            'to_date': w_end.strftime('%Y-%m-%d'),
            'inward_amount': round(in_amt, 2),
            'outward_amount': round(out_amt, 2),
            'inward_summary': format_quantity_summary(w_in),
            'outward_summary': format_quantity_summary(w_out),
            'prod_pieces': round(prod_pcs, 0),
            'load_pieces': round(load_pcs, 0),
            'wage_amount': round(wage_amt, 2),
            'expense_amount': round(w_exp, 2),
            'net_balance': round(out_amt - in_amt - wage_amt - w_exp, 2),
            'is_current': (i == 0)
        })

    return render_template('dashboard.html',
                           total_employees=total_employees,
                           total_parties=total_parties,
                           today_inward_summary=today_inward_summary,
                           today_inward_amount=today_inward_amount,
                           today_outward_summary=today_outward_summary,
                           today_outward_amount=today_outward_amount,
                           week_inward_summary=week_inward_summary,
                           week_inward_amount=week_inward_amount,
                           week_outward_summary=week_outward_summary,
                           week_outward_amount=week_outward_amount,
                           today_jobs_count=today_jobs_count,
                           today_jobs_pieces=today_jobs_pieces,
                           today_jobs_amount=today_jobs_amount,
                           today_prod_pieces=today_prod_pieces,
                           today_prod_amount=today_prod_amount,
                           today_load_pieces=today_load_pieces,
                           today_load_amount=today_load_amount,
                           week_prod_pieces=week_prod_pieces,
                           week_prod_amount=week_prod_amount,
                           week_load_pieces=week_load_pieces,
                           week_load_amount=week_load_amount,
                           week_wages_amount=week_wages_amount,
                           today_expenses=today_expenses,
                           week_expenses=week_expenses,
                           month_expenses=month_expenses,
                           total_receivable=total_receivable,
                           total_payable=total_payable,
                           recent_inward=recent_inward,
                           recent_outward=recent_outward,
                           recent_jobs=recent_jobs,
                           recent_expenses=recent_expenses,
                           stock_overview=stock_overview,
                           weekly_performance=weekly_performance,
                           current_week_from=mon.strftime('%Y-%m-%d'),
                           current_week_to=sun.strftime('%Y-%m-%d'))
