from flask import Blueprint, render_template
from flask_login import login_required
from models import db, Employee, Party, MaterialInward, MaterialOutward
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
    
    # Today's Data
    today_inward_query = db.session.query(
        func.sum(MaterialInward.quantity_mt).label('qty'),
        func.sum(MaterialInward.amount).label('amount')
    ).filter(func.date(MaterialInward.date) == today).first()
    
    today_inward = today_inward_query.qty or 0.0
    today_inward_amount = today_inward_query.amount or 0.0

    today_outward_query = db.session.query(
        func.sum(MaterialOutward.quantity_mt).label('qty'),
        func.sum(MaterialOutward.amount).label('amount')
    ).filter(func.date(MaterialOutward.date) == today).first()
    
    today_outward = today_outward_query.qty or 0.0
    today_outward_amount = today_outward_query.amount or 0.0

    # Outstanding
    parties = Party.query.all()
    total_receivable = sum(p.get_outstanding() for p in parties if p.get_outstanding() > 0)
    total_payable = sum(abs(p.get_outstanding()) for p in parties if p.get_outstanding() < 0)

    # Recent records
    recent_inward = MaterialInward.query.order_by(MaterialInward.date.desc(), MaterialInward.id.desc()).limit(5).all()
    recent_outward = MaterialOutward.query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).limit(5).all()

    # Monthly data for the last 6 months
    month_labels = []
    inward_amounts = []
    outward_amounts = []

    for i in range(5, -1, -1):
        # Calculate the month and year
        d = today - timedelta(days=today.day - 1) # first day of current month
        for _ in range(i):
            d = d - timedelta(days=1)
            d = d - timedelta(days=d.day - 1)
        
        target_month = d.month
        target_year = d.year
        
        month_label = f"{calendar.month_abbr[target_month]} {target_year}"
        month_labels.append(month_label)
        
        # Monthly inward sum
        inward_sum = db.session.query(func.sum(MaterialInward.amount)).filter(
            func.extract('month', MaterialInward.date) == target_month,
            func.extract('year', MaterialInward.date) == target_year
        ).scalar() or 0.0
        inward_amounts.append(inward_sum)
        
        # Monthly outward sum
        outward_sum = db.session.query(func.sum(MaterialOutward.amount)).filter(
            func.extract('month', MaterialOutward.date) == target_month,
            func.extract('year', MaterialOutward.date) == target_year
        ).scalar() or 0.0
        outward_amounts.append(outward_sum)
        
    return render_template(
        'dashboard.html',
        total_employees=total_employees,
        total_parties=total_parties,
        today_inward=today_inward,
        today_outward=today_outward,
        today_inward_amount=today_inward_amount,
        today_outward_amount=today_outward_amount,
        total_receivable=total_receivable,
        total_payable=total_payable,
        recent_inward=recent_inward,
        recent_outward=recent_outward,
        month_labels=month_labels,
        inward_amounts=inward_amounts,
        outward_amounts=outward_amounts
    )
