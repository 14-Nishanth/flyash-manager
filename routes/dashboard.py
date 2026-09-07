from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Employee, Party, MaterialInward, MaterialOutward, JobWageEntry, JobRateSetting, Expense
from datetime import date, timedelta
from sqlalchemy import func
import calendar

bp = Blueprint('dashboard', __name__, url_prefix='/')

@bp.route('/')
@login_required
def index():
    today = date.today()
    
    # Basic Stats
    total_employees = Employee.query.filter_by(is_active=True).count()
    total_parties = Party.query.count()
    
    # Today's Material Inward & Outward
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

    # Operational Expenses Today & This Month
    first_of_month = today.replace(day=1)
    today_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0
    month_expenses = db.session.query(func.sum(Expense.amount)).filter(Expense.date >= first_of_month, Expense.date <= today).scalar() or 0.0

    # Piece-Rate Job Metrics for Today
    today_jobs_query = db.session.query(
        func.count(JobWageEntry.id).label('count'),
        func.sum(JobWageEntry.quantity).label('pieces'),
        func.sum(JobWageEntry.total_amount).label('amount')
    ).filter(JobWageEntry.date == today).first()

    today_jobs_count = today_jobs_query.count or 0
    today_jobs_pieces = today_jobs_query.pieces or 0
    today_jobs_amount = today_jobs_query.amount or 0.0

    # Outstanding Balances
    parties = Party.query.all()
    total_receivable = sum(p.get_outstanding() for p in parties if p.get_outstanding() > 0)
    total_payable = sum(abs(p.get_outstanding()) for p in parties if p.get_outstanding() < 0)

    # Recent records
    recent_inward = MaterialInward.query.order_by(MaterialInward.date.desc(), MaterialInward.id.desc()).limit(5).all()
    recent_outward = MaterialOutward.query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).limit(5).all()
    recent_jobs = JobWageEntry.query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).limit(5).all()
    recent_expenses = Expense.query.order_by(Expense.date.desc(), Expense.id.desc()).limit(5).all()

    # Material Stock Balance Summary
    stock_overview = []
    for mat in ['Cement', 'Jelly', 'Fly Ash', 'Sand']:
        in_qty = db.session.query(func.sum(MaterialInward.quantity_mt)).filter(MaterialInward.material_type.ilike(f'%{mat}%')).scalar() or 0.0
        out_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(MaterialOutward.material_type.ilike(f'%{mat}%')).scalar() or 0.0
        stock_overview.append({
            'name': mat,
            'inward': in_qty,
            'outward': out_qty,
            'balance': round(in_qty - out_qty, 2)
        })

    # Monthly data for the last 6 months
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
        
        month_label = f"{calendar.month_abbr[target_month]} {target_year}"
        month_labels.append(month_label)
        
        try:
            inward_sum = db.session.query(func.sum(MaterialInward.amount)).filter(
                func.extract('month', MaterialInward.date) == target_month,
                func.extract('year', MaterialInward.date) == target_year
            ).scalar() or 0.0
        except Exception:
            inward_sum = 0.0
        inward_amounts.append(round(inward_sum, 2))
        
        try:
            outward_sum = db.session.query(func.sum(MaterialOutward.amount)).filter(
                func.extract('month', MaterialOutward.date) == target_month,
                func.extract('year', MaterialOutward.date) == target_year
            ).scalar() or 0.0
        except Exception:
            outward_sum = 0.0
        outward_amounts.append(round(outward_sum, 2))

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
