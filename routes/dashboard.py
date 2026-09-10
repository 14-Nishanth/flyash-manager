from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Employee, Party, MaterialInward, MaterialOutward, JobWageEntry, Expense, Payment
from datetime import date
from sqlalchemy import func
import calendar

bp = Blueprint('dashboard', __name__, url_prefix='/')


@bp.route('/')
@login_required
def index():
    today = date.today()

    # Keep dashboard queries small: aggregate in SQL and avoid loading full tables.
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_parties = Party.query.count()

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

    first_of_month = today.replace(day=1)
    today_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0
    month_expenses = db.session.query(func.sum(Expense.amount)).filter(
        Expense.date >= first_of_month, Expense.date <= today
    ).scalar() or 0.0

    today_jobs_list = JobWageEntry.query.filter(JobWageEntry.date == today).all()
    today_jobs_count = len(today_jobs_list)
    from routes.employees import calculate_net_job_quantity
    today_jobs_pieces = calculate_net_job_quantity(today_jobs_list)
    today_jobs_amount = sum(j.total_amount for j in today_jobs_list)

    # Outstanding balances: aggregate once per transaction table, then combine in Python.
    parties = db.session.query(Party.id, Party.opening_balance).all()
    inward_sums = dict(db.session.query(
        MaterialInward.party_id, func.sum(MaterialInward.amount)
    ).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(
        MaterialOutward.party_id, func.sum(MaterialOutward.amount)
    ).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(
        Payment.party_id, func.sum(Payment.amount)
    ).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(
        Payment.party_id, func.sum(Payment.amount)
    ).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())

    total_receivable = 0.0
    total_payable = 0.0
    for party_id, opening_balance in parties:
        balance = (
            (opening_balance or 0.0)
            + inward_sums.get(party_id, 0.0)
            - outward_sums.get(party_id, 0.0)
            + paid_sums.get(party_id, 0.0)
            - rec_sums.get(party_id, 0.0)
        )
        if balance > 0:
            total_receivable += balance
        elif balance < 0:
            total_payable += abs(balance)

    recent_inward = MaterialInward.query.order_by(
        MaterialInward.date.desc(), MaterialInward.id.desc()
    ).limit(5).all()
    recent_outward = MaterialOutward.query.order_by(
        MaterialOutward.date.desc(), MaterialOutward.id.desc()
    ).limit(5).all()
    recent_jobs = JobWageEntry.query.order_by(
        JobWageEntry.date.desc(), JobWageEntry.id.desc()
    ).limit(5).all()
    recent_expenses = Expense.query.order_by(
        Expense.date.desc(), Expense.id.desc()
    ).limit(5).all()

    # Material stock overview: two grouped queries instead of scanning records in Python.
    in_grouped = dict(db.session.query(
        MaterialInward.material_type, func.sum(MaterialInward.quantity_mt)
    ).group_by(MaterialInward.material_type).all())
    out_grouped = dict(db.session.query(
        MaterialOutward.material_type, func.sum(MaterialOutward.quantity_mt)
    ).group_by(MaterialOutward.material_type).all())

    stock_overview = []
    for mat in ['Cement', 'Jelly', 'Fly Ash', 'Sand']:
        in_qty = sum(qty or 0 for key, qty in in_grouped.items() if mat.lower() in (key or '').lower())
        out_qty = sum(qty or 0 for key, qty in out_grouped.items() if mat.lower() in (key or '').lower())
        stock_overview.append({
            'name': mat,
            'inward': in_qty,
            'outward': out_qty,
            'balance': round(in_qty - out_qty, 2)
        })

    # Last six months: fetch each table's range once instead of 24 separate aggregate queries.
    month_starts = []
    year, month = today.year, today.month
    for _ in range(6):
        month_starts.append(date(year, month, 1))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_starts.reverse()

    range_start = month_starts[0]
    range_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

    inward_month_rows = db.session.query(
        MaterialInward.date, MaterialInward.amount, MaterialInward.quantity_mt
    ).filter(MaterialInward.date >= range_start, MaterialInward.date <= range_end).all()
    outward_month_rows = db.session.query(
        MaterialOutward.date, MaterialOutward.amount, MaterialOutward.quantity_mt
    ).filter(MaterialOutward.date >= range_start, MaterialOutward.date <= range_end).all()

    monthly_totals = {
        start: {'inward_amount': 0.0, 'outward_amount': 0.0, 'inward_qty': 0.0, 'outward_qty': 0.0}
        for start in month_starts
    }

    def month_start_for(record_date):
        return date(record_date.year, record_date.month, 1)

    for row in inward_month_rows:
        bucket = monthly_totals.get(month_start_for(row.date))
        if bucket:
            bucket['inward_amount'] += row.amount or 0.0
            bucket['inward_qty'] += row.quantity_mt or 0.0

    for row in outward_month_rows:
        bucket = monthly_totals.get(month_start_for(row.date))
        if bucket:
            bucket['outward_amount'] += row.amount or 0.0
            bucket['outward_qty'] += row.quantity_mt or 0.0

    monthly_performance = []
    for start in month_starts:
        totals = monthly_totals[start]
        monthly_performance.append({
            'label': f'{calendar.month_abbr[start.month]} {start.year}',
            'inward_amount': round(totals['inward_amount'], 2),
            'outward_amount': round(totals['outward_amount'], 2),
            'inward_qty': round(totals['inward_qty'], 1),
            'outward_qty': round(totals['outward_qty'], 1),
            'net_balance': round(totals['outward_amount'] - totals['inward_amount'], 2),
            'is_current': start.year == today.year and start.month == today.month
        })

    return render_template(
        'dashboard.html',
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
        monthly_performance=monthly_performance
    )
