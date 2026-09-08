from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Employee, Party, MaterialInward, MaterialOutward, JobWageEntry, JobRateSetting, Expense, Payment
from datetime import date, timedelta
from sqlalchemy import func
import calendar

bp = Blueprint('dashboard', __name__, url_prefix='/')

@bp.route('/')
@login_required
def index():
    today = date.today()
    
    # 1. Basic Counts
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_parties = Party.query.count()
    
    # 2. Today's Inward & Outward (Single queries)
    today_inward_query = db.session.query(
        func.sum(MaterialInward.quantity_mt).label('qty'),
        func.sum(MaterialInward.amount).label('amount')
    ).filter(MaterialInward.date == today).first()
    
    today_inward = today_inward_query.qty or 0.0
    today_inward_amount = today_inward_query.amount or 0.0

    today_outward_query = db.session.query(
        func.sum(MaterialOutward.quantity_mt).label('qty'),
        func.sum(MaterialOutward.amount).label('amount')
    ).filter(MaterialOutward.date == today).first()
    
    today_outward = today_outward_query.qty or 0.0
    today_outward_amount = today_outward_query.amount or 0.0

    # 3. Operational Expenses
    first_of_month = today.replace(day=1)
    today_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0
    month_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= first_of_month, Expense.date <= today).scalar() or 0.0

    # 4. Piece-Rate Job Metrics (Deduplicated so Group Loading + Group Unloading shows net physical pieces)
    today_jobs_list = JobWageEntry.query.filter(JobWageEntry.date == today).all()
    today_jobs_count = len(today_jobs_list)
    from routes.employees import calculate_net_job_quantity
    today_jobs_pieces = calculate_net_job_quantity(today_jobs_list)
    today_jobs_amount = sum(j.total_amount for j in today_jobs_list)

    # 5. Fast Bulk Outstanding Calculation (4 queries total, 0 loop queries)
    parties = Party.query.all()
    inward_sums = dict(db.session.query(MaterialInward.party_id, func.sum(MaterialInward.amount)).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(MaterialOutward.party_id, func.sum(MaterialOutward.amount)).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())

    total_receivable = 0.0
    total_payable = 0.0
    for p in parties:
        # supplier: debit = inward + paid, credit = received => balance = debit - credit
        # customer: debit = inward + paid, credit = outward + received
        bal = (p.opening_balance or 0.0) + inward_sums.get(p.id, 0.0) - outward_sums.get(p.id, 0.0) + paid_sums.get(p.id, 0.0) - rec_sums.get(p.id, 0.0)
        if bal > 0:
            total_receivable += bal
        elif bal < 0:
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

    # 8. Monthly data for last 6 months
    month_labels = []
    inward_amounts = []
    outward_amounts = []

    for i in range(5, -1, -1):
        d = today - timedelta(days=today.day - 1)
        for _ in range(i):
            d = d - timedelta(days=1)
            d = d - timedelta(days=d.day - 1)
        
        target_month = d.month
        target_year = d.year
        month_labels.append(f"{calendar.month_abbr[target_month]} {target_year}")
        
        first_d = date(target_year, target_month, 1)
        last_d = date(target_year, target_month, calendar.monthrange(target_year, target_month)[1])

        in_m = db.session.query(func.sum(MaterialInward.amount)).filter(MaterialInward.date >= first_d, MaterialInward.date <= last_d).scalar() or 0.0
        out_m = db.session.query(func.sum(MaterialOutward.amount)).filter(MaterialOutward.date >= first_d, MaterialOutward.date <= last_d).scalar() or 0.0
        inward_amounts.append(round(in_m, 2))
        outward_amounts.append(round(out_m, 2))

    return render_template('dashboard.html',
                           total_employees=total_employees,
                           total_parties=total_parties,
                           today_inward=today_inward,
                           today_inward_amount=today_inward_amount,
                           today_outward=today_outward,
                           today_outward_amount=today_outward_amount,
                           today_jobs_count=today_jobs_count,
                           today_jobs_pieces=today_jobs_pieces,
                           today_jobs_amount=today_jobs_amount,
                           today_expenses=today_expenses,
                           month_expenses=month_expenses,
                           total_receivable=total_receivable,
                           total_payable=total_payable,
                           recent_inward=recent_inward,
                           recent_outward=recent_outward,
                           recent_jobs=recent_jobs,
                           recent_expenses=recent_expenses,
                           stock_overview=stock_overview,
                           month_labels=month_labels,
                           inward_amounts=inward_amounts,
                           outward_amounts=outward_amounts)
