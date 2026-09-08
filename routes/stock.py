import io
import csv
from datetime import date, datetime, timedelta
import calendar
from flask import Blueprint, render_template, request, Response, url_for
from flask_login import login_required
from models import db, JobWageEntry, MaterialInward, MaterialOutward, JobRateSetting, EmployeeGroup, Employee
from sqlalchemy import func, distinct

bp = Blueprint('stock', __name__, url_prefix='/stock')

STANDARD_PRODUCTS = [
    'Fly Ash Brick 9"x4"x3" (Standard)',
    'Fly Ash Brick Modular (190 x 90 x 90 mm)',
    'Fly Ash Brick (230 x 110 x 70 mm)',
    'Heavy Duty Fly Ash Brick (Class 10/15)',
    'Interlocking Fly Ash Brick',
    'Solid Block 4"',
    'Solid Block 6"',
    'Solid Block 8"',
    'Hollow Block 4" (400 x 200 x 100 mm)',
    'Hollow Block 6" (400 x 200 x 150 mm)',
    'Hollow Block 8" (400 x 200 x 200 mm)',
    'Hollow Block 9" (400 x 200 x 225 mm)',
    'Hollow Block 12" (400 x 200 x 300 mm)',
    'Fly Ash Paver Blocks (60mm / 80mm)',
    'AAC Blocks'
]

STANDARD_RAW_MATERIALS = [
    'Fly Ash',
    'Class F Fly Ash',
    'Class C Fly Ash',
    'Cement',
    'Cement (OPC 53 Grade)',
    'Cement (PPC)',
    'Jelly (Blue Metal)',
    'Jelly 20mm (3/4" Jelly)',
    'Jelly 12mm (1/2" Jelly)',
    'Baby Jelly (6mm / 8mm Grit)',
    'Stone Dust / Quarry Dust',
    'M-Sand (Manufactured Sand)',
    'P-Sand (Plastering Sand)',
    'River Sand / Natural Sand',
    'Gypsum',
    'Quicklime',
    'Hydrated Lime / Slaked Lime',
    'GGBS (Ground Granulated Blast-furnace Slag)'
]


def get_all_finished_products():
    products_set = set(STANDARD_PRODUCTS)
    try:
        rates_prods = [r[0] for r in db.session.query(distinct(JobRateSetting.product_name)).all() if r[0]]
        products_set.update(rates_prods)
        job_prods = [r[0] for r in db.session.query(distinct(JobWageEntry.product_name)).all() if r[0]]
        products_set.update(job_prods)
        out_prods = [r[0] for r in db.session.query(distinct(MaterialOutward.material_type)).all() if r[0]]
        for p in out_prods:
            if any(term in p.lower() for term in ['brick', 'block', 'paver', 'aac', 'modular', 'solid', 'hollow']):
                products_set.update([p])
    except Exception:
        pass
    custom = sorted([p for p in products_set if p not in STANDARD_PRODUCTS])
    return STANDARD_PRODUCTS + custom


def get_all_raw_materials():
    mats_set = set(STANDARD_RAW_MATERIALS)
    try:
        in_mats = [r[0] for r in db.session.query(distinct(MaterialInward.material_type)).all() if r[0]]
        mats_set.update(in_mats)
    except Exception:
        pass
    custom = sorted([m for m in mats_set if m not in STANDARD_RAW_MATERIALS])
    return STANDARD_RAW_MATERIALS + custom


def resolve_date_period(period_param, from_date_str, to_date_str):
    """Resolve presets like this_week, last_week, this_month, last_month, this_year."""
    today = date.today()
    if period_param == 'today':
        return today.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period_param == 'this_week':
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        return mon.strftime('%Y-%m-%d'), sun.strftime('%Y-%m-%d')
    elif period_param == 'last_week':
        last_mon = today - timedelta(days=today.weekday() + 7)
        last_sun = last_mon + timedelta(days=6)
        return last_mon.strftime('%Y-%m-%d'), last_sun.strftime('%Y-%m-%d')
    elif period_param == 'this_month':
        first_day = today.replace(day=1)
        last_day = today.replace(day=calendar.monthrange(today.year, today.month)[1])
        return first_day.strftime('%Y-%m-%d'), last_day.strftime('%Y-%m-%d')
    elif period_param == 'last_month':
        first_this = today.replace(day=1)
        prev_month_last = first_this - timedelta(days=1)
        prev_month_first = prev_month_last.replace(day=1)
        return prev_month_first.strftime('%Y-%m-%d'), prev_month_last.strftime('%Y-%m-%d')
    elif period_param == 'this_year':
        return f"{today.year}-01-01", f"{today.year}-12-31"
    elif period_param == 'all':
        return '', ''
    
    # Custom or fallback
    if not from_date_str and not to_date_str:
        # Default to 1st of current month to today
        first_day = today.replace(day=1)
        return first_day.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    return from_date_str, to_date_str


@bp.route('/')
@login_required
def index():
    """Main Stock & Yard Balance Sheet."""
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')

    all_products = get_all_finished_products()
    all_raw_mats = get_all_raw_materials()

    finished_goods_stock = []
    total_yard_pieces = 0.0
    total_produced_all = 0.0
    total_dispatched_all = 0.0

    for prod in all_products:
        if search and search.lower() not in prod.lower():
            continue

        produced_qty = db.session.query(func.sum(JobWageEntry.quantity)).filter(
            JobWageEntry.product_name.ilike(f'%{prod}%'),
            JobWageEntry.job_type.ilike('%Production%')
        ).scalar() or 0.0

        dispatched_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
            MaterialOutward.material_type.ilike(f'%{prod}%')
        ).scalar() or 0.0

        current_balance = produced_qty - dispatched_qty
        
        if current_balance > 3000:
            stock_status = 'In Stock'
            badge_class = 'bg-success bg-opacity-10 text-success'
        elif current_balance > 0:
            stock_status = 'Low Stock'
            badge_class = 'bg-warning bg-opacity-10 text-dark'
        elif current_balance == 0:
            stock_status = 'Zero Stock'
            badge_class = 'bg-secondary bg-opacity-10 text-secondary'
        else:
            stock_status = 'Negative Balance'
            badge_class = 'bg-danger bg-opacity-10 text-danger'

        if status_filter != 'all':
            if status_filter == 'in_stock' and current_balance <= 3000:
                continue
            elif status_filter == 'low_stock' and (current_balance <= 0 or current_balance > 3000):
                continue
            elif status_filter == 'out_of_stock' and current_balance != 0:
                continue
            elif status_filter == 'negative' and current_balance >= 0:
                continue

        if produced_qty > 0 or dispatched_qty > 0 or current_balance != 0 or prod in STANDARD_PRODUCTS[:5]:
            finished_goods_stock.append({
                'product_name': prod,
                'produced_qty': produced_qty,
                'dispatched_qty': dispatched_qty,
                'balance_qty': current_balance,
                'status': stock_status,
                'badge_class': badge_class,
                'unit': 'Pieces'
            })
            total_yard_pieces += current_balance
            total_produced_all += produced_qty
            total_dispatched_all += dispatched_qty

    raw_materials_stock = []
    total_raw_tons = 0.0

    for mat in all_raw_mats:
        if search and search.lower() not in mat.lower():
            continue

        inward_qty = db.session.query(func.sum(MaterialInward.quantity_mt)).filter(
            MaterialInward.material_type.ilike(f'%{mat}%')
        ).scalar() or 0.0

        outward_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
            MaterialOutward.material_type.ilike(f'%{mat}%')
        ).scalar() or 0.0

        current_balance = inward_qty - outward_qty

        if inward_qty > 0 or outward_qty > 0 or current_balance != 0 or mat in STANDARD_RAW_MATERIALS[:4]:
            raw_materials_stock.append({
                'material_name': mat,
                'inward_qty': inward_qty,
                'outward_qty': outward_qty,
                'balance_qty': current_balance,
                'unit': 'Tons (MT)'
            })
            total_raw_tons += current_balance

    recent_additions = JobWageEntry.query.filter(JobWageEntry.job_type.ilike('%Production%')).order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).limit(6).all()
    recent_deductions = MaterialOutward.query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).limit(6).all()

    return render_template(
        'stock/index.html',
        finished_goods=finished_goods_stock,
        raw_materials=raw_materials_stock,
        total_yard_pieces=total_yard_pieces,
        total_raw_tons=total_raw_tons,
        total_produced_all=total_produced_all,
        total_dispatched_all=total_dispatched_all,
        recent_additions=recent_additions,
        recent_deductions=recent_deductions,
        search=search,
        status_filter=status_filter
    )


@bp.route('/production')
@login_required
def production_sheet():
    """Dedicated Production Sheet with Daily entries, Weekly basis summary, and Monthly basis summary."""
    today = date.today()
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')
    
    from_date_str, to_date_str = resolve_date_period(period_param, from_date_raw, to_date_raw)
    
    view_mode = request.args.get('view_mode', 'daily') # 'daily', 'weekly', 'monthly'
    product_name = request.args.get('product_name', '').strip()
    group_id = request.args.get('group_id', type=int)
    search = request.args.get('search', '').strip()

    query = JobWageEntry.query.filter(JobWageEntry.job_type.ilike('%Production%'))

    try:
        if from_date_str:
            f_d = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(JobWageEntry.date >= f_d)
        if to_date_str:
            t_d = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(JobWageEntry.date <= t_d)
    except ValueError:
        pass

    if product_name:
        query = query.filter(JobWageEntry.product_name == product_name)
    if group_id:
        query = query.filter(JobWageEntry.group_id == group_id)
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (JobWageEntry.product_name.ilike(search_fmt)) |
            (JobWageEntry.notes.ilike(search_fmt))
        )

    entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()

    total_production_qty = sum(e.quantity for e in entries)
    total_labor_cost = sum(e.total_amount for e in entries)
    
    # KPI Metrics
    today_produced = db.session.query(func.sum(JobWageEntry.quantity)).filter(
        JobWageEntry.date == today,
        JobWageEntry.job_type.ilike('%Production%')
    ).scalar() or 0.0

    first_day_of_month = today.replace(day=1)
    month_produced = db.session.query(func.sum(JobWageEntry.quantity)).filter(
        JobWageEntry.date >= first_day_of_month,
        JobWageEntry.date <= today,
        JobWageEntry.job_type.ilike('%Production%')
    ).scalar() or 0.0

    this_week_mon = today - timedelta(days=today.weekday())
    week_produced = db.session.query(func.sum(JobWageEntry.quantity)).filter(
        JobWageEntry.date >= this_week_mon,
        JobWageEntry.date <= today,
        JobWageEntry.job_type.ilike('%Production%')
    ).scalar() or 0.0

    # Product-wise breakdown in current view
    product_summary = {}
    for e in entries:
        product_summary[e.product_name] = product_summary.get(e.product_name, 0.0) + e.quantity

    # --- WEEKLY BREAKDOWN CALCULATION ---
    weekly_dict = {}
    for e in entries:
        mon = e.date - timedelta(days=e.date.weekday())
        sun = mon + timedelta(days=6)
        key = (mon, sun)
        if key not in weekly_dict:
            weekly_dict[key] = {
                'week_start': mon,
                'week_end': sun,
                'week_label': f"{mon.strftime('%d %b')} – {sun.strftime('%d %b %Y')}",
                'iso_week': f"Week {mon.isocalendar()[1]}",
                'total_qty': 0.0,
                'total_labor_cost': 0.0,
                'runs_count': 0,
                'dates_worked': set(),
                'products': {}
            }
        weekly_dict[key]['total_qty'] += e.quantity
        weekly_dict[key]['total_labor_cost'] += e.total_amount
        weekly_dict[key]['runs_count'] += 1
        weekly_dict[key]['dates_worked'].add(e.date)
        weekly_dict[key]['products'][e.product_name] = weekly_dict[key]['products'].get(e.product_name, 0.0) + e.quantity

    weekly_summary = []
    for key, data in sorted(weekly_dict.items(), key=lambda x: x[0][0], reverse=True):
        days_cnt = len(data['dates_worked'])
        avg_daily = data['total_qty'] / days_cnt if days_cnt else 0.0
        avg_labor_per_pc = data['total_labor_cost'] / data['total_qty'] if data['total_qty'] else 0.0
        top_prod = max(data['products'].items(), key=lambda x: x[1])[0] if data['products'] else 'N/A'
        weekly_summary.append({
            'week_label': data['week_label'],
            'iso_week': data['iso_week'],
            'week_start': data['week_start'].strftime('%Y-%m-%d'),
            'week_end': data['week_end'].strftime('%Y-%m-%d'),
            'total_qty': data['total_qty'],
            'total_labor_cost': data['total_labor_cost'],
            'runs_count': data['runs_count'],
            'days_worked': days_cnt,
            'avg_daily_qty': avg_daily,
            'avg_labor_per_pc': avg_labor_per_pc,
            'top_product': top_prod,
            'products': data['products']
        })

    # --- MONTHLY BREAKDOWN CALCULATION ---
    monthly_dict = {}
    for e in entries:
        key = (e.date.year, e.date.month)
        if key not in monthly_dict:
            monthly_dict[key] = {
                'year': e.date.year,
                'month': e.date.month,
                'month_label': datetime(e.date.year, e.date.month, 1).strftime('%B %Y'),
                'total_qty': 0.0,
                'total_labor_cost': 0.0,
                'runs_count': 0,
                'dates_worked': set(),
                'products': {}
            }
        monthly_dict[key]['total_qty'] += e.quantity
        monthly_dict[key]['total_labor_cost'] += e.total_amount
        monthly_dict[key]['runs_count'] += 1
        monthly_dict[key]['dates_worked'].add(e.date)
        monthly_dict[key]['products'][e.product_name] = monthly_dict[key]['products'].get(e.product_name, 0.0) + e.quantity

    monthly_summary = []
    for key, data in sorted(monthly_dict.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True):
        days_cnt = len(data['dates_worked'])
        avg_daily = data['total_qty'] / days_cnt if days_cnt else 0.0
        avg_labor_per_pc = data['total_labor_cost'] / data['total_qty'] if data['total_qty'] else 0.0
        top_prod = max(data['products'].items(), key=lambda x: x[1])[0] if data['products'] else 'N/A'
        first_day_m = date(data['year'], data['month'], 1)
        last_day_m = date(data['year'], data['month'], calendar.monthrange(data['year'], data['month'])[1])
        monthly_summary.append({
            'month_label': data['month_label'],
            'from_date': first_day_m.strftime('%Y-%m-%d'),
            'to_date': last_day_m.strftime('%Y-%m-%d'),
            'total_qty': data['total_qty'],
            'total_labor_cost': data['total_labor_cost'],
            'runs_count': data['runs_count'],
            'days_worked': days_cnt,
            'avg_daily_qty': avg_daily,
            'avg_labor_per_pc': avg_labor_per_pc,
            'top_product': top_prod,
            'products': data['products']
        })

    groups = EmployeeGroup.query.filter_by(is_active=True).all()
    all_products = get_all_finished_products()

    return render_template(
        'stock/production_sheet.html',
        entries=entries,
        total_production_qty=total_production_qty,
        total_labor_cost=total_labor_cost,
        today_produced=today_produced,
        week_produced=week_produced,
        month_produced=month_produced,
        product_summary=product_summary,
        weekly_summary=weekly_summary,
        monthly_summary=monthly_summary,
        groups=groups,
        all_products=all_products,
        from_date=from_date_str,
        to_date=to_date_str,
        period=period_param,
        view_mode=view_mode,
        selected_product=product_name,
        selected_group=group_id,
        search=search
    )


@bp.route('/loading')
@login_required
def loading_sheet():
    """Dedicated Loading & Dispatch Sheet with Daily logs, Weekly summary, and Monthly summary."""
    today = date.today()
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')

    from_date_str, to_date_str = resolve_date_period(period_param, from_date_raw, to_date_raw)
    
    view_mode = request.args.get('view_mode', 'daily') # 'daily', 'weekly', 'monthly'
    product_name = request.args.get('product_name', '').strip()
    search = request.args.get('search', '').strip()

    # Query piece-rate loading wage entries
    loading_wage_query = JobWageEntry.query.filter(
        (JobWageEntry.job_type.ilike('%Loading%')) | (JobWageEntry.job_type.ilike('%Unloading%'))
    )

    # Query material outward dispatches
    outward_query = MaterialOutward.query

    try:
        if from_date_str:
            f_d = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            loading_wage_query = loading_wage_query.filter(JobWageEntry.date >= f_d)
            outward_query = outward_query.filter(MaterialOutward.date >= f_d)
        if to_date_str:
            t_d = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            loading_wage_query = loading_wage_query.filter(JobWageEntry.date <= t_d)
            outward_query = outward_query.filter(MaterialOutward.date <= t_d)
    except ValueError:
        pass

    if product_name:
        loading_wage_query = loading_wage_query.filter(JobWageEntry.product_name == product_name)
        outward_query = outward_query.filter(MaterialOutward.material_type == product_name)
    if search:
        search_fmt = f'%{search}%'
        loading_wage_query = loading_wage_query.filter(
            (JobWageEntry.product_name.ilike(search_fmt)) |
            (JobWageEntry.vehicle_no.ilike(search_fmt)) |
            (JobWageEntry.notes.ilike(search_fmt))
        )
        outward_query = outward_query.filter(
            (MaterialOutward.material_type.ilike(search_fmt)) |
            (MaterialOutward.vehicle_no.ilike(search_fmt)) |
            (MaterialOutward.notes.ilike(search_fmt))
        )

    loading_entries = loading_wage_query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    outward_entries = outward_query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).all()

    total_loading_wages = sum(e.total_amount for e in loading_entries)
    total_loaded_pcs = sum(e.quantity for e in loading_entries if 'piece' in (e.unit or '').lower() or 'pcs' in (e.unit or '').lower())
    
    total_outward_pcs = sum(e.quantity_mt for e in outward_entries if 'piece' in (e.quantity_unit or '').lower() or 'pcs' in (e.quantity_unit or '').lower())
    total_outward_tons = sum(e.quantity_mt for e in outward_entries if 'ton' in (e.quantity_unit or '').lower() or 'mt' in (e.quantity_unit or '').lower())
    total_outward_revenue = sum(e.amount for e in outward_entries)

    # Week & Month to date metrics
    first_day_m = today.replace(day=1)
    month_outward_pcs = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
        MaterialOutward.date >= first_day_m,
        MaterialOutward.date <= today,
        (MaterialOutward.quantity_unit.ilike('%piece%')) | (MaterialOutward.quantity_unit.ilike('%pcs%'))
    ).scalar() or 0.0

    this_week_mon = today - timedelta(days=today.weekday())
    week_outward_pcs = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
        MaterialOutward.date >= this_week_mon,
        MaterialOutward.date <= today,
        (MaterialOutward.quantity_unit.ilike('%piece%')) | (MaterialOutward.quantity_unit.ilike('%pcs%'))
    ).scalar() or 0.0

    # --- WEEKLY LOADING BREAKDOWN ---
    weekly_dict = {}
    for o in outward_entries:
        mon = o.date - timedelta(days=o.date.weekday())
        sun = mon + timedelta(days=6)
        key = (mon, sun)
        if key not in weekly_dict:
            weekly_dict[key] = {
                'week_start': mon,
                'week_end': sun,
                'week_label': f"{mon.strftime('%d %b')} – {sun.strftime('%d %b %Y')}",
                'iso_week': f"Week {mon.isocalendar()[1]}",
                'outward_pcs': 0.0,
                'outward_tons': 0.0,
                'outward_revenue': 0.0,
                'dispatches_count': 0,
                'loading_wages': 0.0,
                'vehicles': set()
            }
        unit_str = (o.quantity_unit or '').lower()
        if 'piece' in unit_str or 'pcs' in unit_str:
            weekly_dict[key]['outward_pcs'] += o.quantity_mt
        elif 'ton' in unit_str or 'mt' in unit_str:
            weekly_dict[key]['outward_tons'] += o.quantity_mt
        else:
            weekly_dict[key]['outward_pcs'] += o.quantity_mt
            
        weekly_dict[key]['outward_revenue'] += o.amount
        weekly_dict[key]['dispatches_count'] += 1
        if o.vehicle_no:
            weekly_dict[key]['vehicles'].add(o.vehicle_no)

    for l in loading_entries:
        mon = l.date - timedelta(days=l.date.weekday())
        sun = mon + timedelta(days=6)
        key = (mon, sun)
        if key not in weekly_dict:
            weekly_dict[key] = {
                'week_start': mon,
                'week_end': sun,
                'week_label': f"{mon.strftime('%d %b')} – {sun.strftime('%d %b %Y')}",
                'iso_week': f"Week {mon.isocalendar()[1]}",
                'outward_pcs': 0.0,
                'outward_tons': 0.0,
                'outward_revenue': 0.0,
                'dispatches_count': 0,
                'loading_wages': 0.0,
                'vehicles': set()
            }
        weekly_dict[key]['loading_wages'] += l.total_amount
        if l.vehicle_no:
            weekly_dict[key]['vehicles'].add(l.vehicle_no)

    weekly_summary = []
    for key, data in sorted(weekly_dict.items(), key=lambda x: x[0][0], reverse=True):
        weekly_summary.append({
            'week_label': data['week_label'],
            'iso_week': data['iso_week'],
            'week_start': data['week_start'].strftime('%Y-%m-%d'),
            'week_end': data['week_end'].strftime('%Y-%m-%d'),
            'outward_pcs': data['outward_pcs'],
            'outward_tons': data['outward_tons'],
            'outward_revenue': data['outward_revenue'],
            'dispatches_count': data['dispatches_count'],
            'loading_wages': data['loading_wages'],
            'unique_vehicles': len(data['vehicles'])
        })

    # --- MONTHLY LOADING BREAKDOWN ---
    monthly_dict = {}
    for o in outward_entries:
        key = (o.date.year, o.date.month)
        if key not in monthly_dict:
            monthly_dict[key] = {
                'year': o.date.year,
                'month': o.date.month,
                'month_label': datetime(o.date.year, o.date.month, 1).strftime('%B %Y'),
                'outward_pcs': 0.0,
                'outward_tons': 0.0,
                'outward_revenue': 0.0,
                'dispatches_count': 0,
                'loading_wages': 0.0,
                'vehicles': set()
            }
        unit_str = (o.quantity_unit or '').lower()
        if 'piece' in unit_str or 'pcs' in unit_str:
            monthly_dict[key]['outward_pcs'] += o.quantity_mt
        elif 'ton' in unit_str or 'mt' in unit_str:
            monthly_dict[key]['outward_tons'] += o.quantity_mt
        else:
            monthly_dict[key]['outward_pcs'] += o.quantity_mt
            
        monthly_dict[key]['outward_revenue'] += o.amount
        monthly_dict[key]['dispatches_count'] += 1
        if o.vehicle_no:
            monthly_dict[key]['vehicles'].add(o.vehicle_no)

    for l in loading_entries:
        key = (l.date.year, l.date.month)
        if key not in monthly_dict:
            monthly_dict[key] = {
                'year': l.date.year,
                'month': l.date.month,
                'month_label': datetime(l.date.year, l.date.month, 1).strftime('%B %Y'),
                'outward_pcs': 0.0,
                'outward_tons': 0.0,
                'outward_revenue': 0.0,
                'dispatches_count': 0,
                'loading_wages': 0.0,
                'vehicles': set()
            }
        monthly_dict[key]['loading_wages'] += l.total_amount
        if l.vehicle_no:
            monthly_dict[key]['vehicles'].add(l.vehicle_no)

    monthly_summary = []
    for key, data in sorted(monthly_dict.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True):
        first_day_m = date(data['year'], data['month'], 1)
        last_day_m = date(data['year'], data['month'], calendar.monthrange(data['year'], data['month'])[1])
        monthly_summary.append({
            'month_label': data['month_label'],
            'from_date': first_day_m.strftime('%Y-%m-%d'),
            'to_date': last_day_m.strftime('%Y-%m-%d'),
            'outward_pcs': data['outward_pcs'],
            'outward_tons': data['outward_tons'],
            'outward_revenue': data['outward_revenue'],
            'dispatches_count': data['dispatches_count'],
            'loading_wages': data['loading_wages'],
            'unique_vehicles': len(data['vehicles'])
        })

    all_products = get_all_finished_products()

    return render_template(
        'stock/loading_sheet.html',
        loading_entries=loading_entries,
        outward_entries=outward_entries,
        total_loading_wages=total_loading_wages,
        total_loaded_pcs=total_loaded_pcs,
        total_outward_pcs=total_outward_pcs,
        total_outward_tons=total_outward_tons,
        total_outward_revenue=total_outward_revenue,
        week_outward_pcs=week_outward_pcs,
        month_outward_pcs=month_outward_pcs,
        weekly_summary=weekly_summary,
        monthly_summary=monthly_summary,
        all_products=all_products,
        from_date=from_date_str,
        to_date=to_date_str,
        period=period_param,
        view_mode=view_mode,
        selected_product=product_name,
        search=search
    )


@bp.route('/production/export')
@login_required
def export_production_csv():
    view_mode = request.args.get('view_mode', 'daily')
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')
    product_name = request.args.get('product_name')

    query = JobWageEntry.query.filter(JobWageEntry.job_type.ilike('%Production%'))
    try:
        if from_date_str:
            query = query.filter(JobWageEntry.date >= datetime.strptime(from_date_str, '%Y-%m-%d').date())
        if to_date_str:
            query = query.filter(JobWageEntry.date <= datetime.strptime(to_date_str, '%Y-%m-%d').date())
    except ValueError:
        pass
    if product_name:
        query = query.filter(JobWageEntry.product_name == product_name)

    entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)

    if view_mode == 'weekly':
        writer.writerow(['Week Period', 'ISO Week', 'Total Produced (Pcs)', 'Working Days', 'Avg Daily Output (Pcs/Day)', 'Total Labor Cost (INR)', 'Labor Cost Per Pc (INR)', 'Top Product Produced'])
        weekly_dict = {}
        for e in entries:
            mon = e.date - timedelta(days=e.date.weekday())
            sun = mon + timedelta(days=6)
            key = (mon, sun)
            if key not in weekly_dict:
                weekly_dict[key] = {
                    'label': f"{mon.strftime('%d %b %Y')} to {sun.strftime('%d %b %Y')}",
                    'iso_week': f"Week {mon.isocalendar()[1]}",
                    'qty': 0.0,
                    'cost': 0.0,
                    'dates': set(),
                    'prods': {}
                }
            weekly_dict[key]['qty'] += e.quantity
            weekly_dict[key]['cost'] += e.total_amount
            weekly_dict[key]['dates'].add(e.date)
            weekly_dict[key]['prods'][e.product_name] = weekly_dict[key]['prods'].get(e.product_name, 0.0) + e.quantity

        for key, data in sorted(weekly_dict.items(), key=lambda x: x[0][0], reverse=True):
            days = len(data['dates'])
            avg_d = data['qty'] / days if days else 0
            avg_c = data['cost'] / data['qty'] if data['qty'] else 0
            top_p = max(data['prods'].items(), key=lambda x: x[1])[0] if data['prods'] else 'N/A'
            writer.writerow([data['label'], data['iso_week'], f"{data['qty']:.0f}", days, f"{avg_d:.0f}", f"{data['cost']:.2f}", f"{avg_c:.2f}", top_p])

    elif view_mode == 'monthly':
        writer.writerow(['Month', 'Total Produced (Pcs)', 'Working Days', 'Avg Daily Output (Pcs/Day)', 'Total Labor Cost (INR)', 'Labor Cost Per Pc (INR)', 'Top Product Produced'])
        monthly_dict = {}
        for e in entries:
            key = (e.date.year, e.date.month)
            if key not in monthly_dict:
                monthly_dict[key] = {
                    'label': datetime(e.date.year, e.date.month, 1).strftime('%B %Y'),
                    'qty': 0.0,
                    'cost': 0.0,
                    'dates': set(),
                    'prods': {}
                }
            monthly_dict[key]['qty'] += e.quantity
            monthly_dict[key]['cost'] += e.total_amount
            monthly_dict[key]['dates'].add(e.date)
            monthly_dict[key]['prods'][e.product_name] = monthly_dict[key]['prods'].get(e.product_name, 0.0) + e.quantity

        for key, data in sorted(monthly_dict.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True):
            days = len(data['dates'])
            avg_d = data['qty'] / days if days else 0
            avg_c = data['cost'] / data['qty'] if data['qty'] else 0
            top_p = max(data['prods'].items(), key=lambda x: x[1])[0] if data['prods'] else 'N/A'
            writer.writerow([data['label'], f"{data['qty']:.0f}", days, f"{avg_d:.0f}", f"{data['cost']:.2f}", f"{avg_c:.2f}", top_p])

    else:
        writer.writerow(['ID', 'Date', 'Product Name', 'Operation Type', 'Quantity Produced (Pcs)', 'Piece Rate (INR)', 'Total Labor Cost (INR)', 'Workers Count', 'Wage Per Worker (INR)', 'Labor Group', 'Notes / Shift'])
        for e in entries:
            writer.writerow([
                e.id,
                e.date.strftime('%Y-%m-%d'),
                e.product_name,
                e.job_type,
                f'{e.quantity:.0f}',
                f'{e.rate_per_unit:.2f}',
                f'{e.total_amount:.2f}',
                e.worker_count,
                f'{e.wage_per_worker:.2f}',
                e.group.name if e.group else 'Individual',
                e.notes or ''
            ])

    filename_suffix = f"_{view_mode}" if view_mode != 'daily' else ""
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=production_sheet{filename_suffix}_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/loading/export')
@login_required
def export_loading_csv():
    view_mode = request.args.get('view_mode', 'daily')
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    loading_wage_query = JobWageEntry.query.filter(
        (JobWageEntry.job_type.ilike('%Loading%')) | (JobWageEntry.job_type.ilike('%Unloading%'))
    )
    outward_query = MaterialOutward.query

    try:
        if from_date_str:
            loading_wage_query = loading_wage_query.filter(JobWageEntry.date >= datetime.strptime(from_date_str, '%Y-%m-%d').date())
            outward_query = outward_query.filter(MaterialOutward.date >= datetime.strptime(from_date_str, '%Y-%m-%d').date())
        if to_date_str:
            loading_wage_query = loading_wage_query.filter(JobWageEntry.date <= datetime.strptime(to_date_str, '%Y-%m-%d').date())
            outward_query = outward_query.filter(MaterialOutward.date <= datetime.strptime(to_date_str, '%Y-%m-%d').date())
    except ValueError:
        pass

    loading_entries = loading_wage_query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    outward_entries = outward_query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)

    if view_mode == 'weekly':
        writer.writerow(['Week Period', 'ISO Week', 'Dispatched Pieces (Pcs)', 'Dispatched Bulk (MT)', 'Vehicle Trips', 'Loading Labor Paid (INR)', 'Sales Revenue (INR)'])
        weekly_dict = {}
        for o in outward_entries:
            mon = o.date - timedelta(days=o.date.weekday())
            sun = mon + timedelta(days=6)
            key = (mon, sun)
            if key not in weekly_dict:
                weekly_dict[key] = {
                    'label': f"{mon.strftime('%d %b %Y')} to {sun.strftime('%d %b %Y')}",
                    'iso_week': f"Week {mon.isocalendar()[1]}",
                    'pcs': 0.0,
                    'tons': 0.0,
                    'revenue': 0.0,
                    'trips': 0,
                    'wages': 0.0
                }
            unit_str = (o.quantity_unit or '').lower()
            if 'piece' in unit_str or 'pcs' in unit_str:
                weekly_dict[key]['pcs'] += o.quantity_mt
            elif 'ton' in unit_str or 'mt' in unit_str:
                weekly_dict[key]['tons'] += o.quantity_mt
            else:
                weekly_dict[key]['pcs'] += o.quantity_mt
            weekly_dict[key]['revenue'] += o.amount
            weekly_dict[key]['trips'] += 1

        for l in loading_entries:
            mon = l.date - timedelta(days=l.date.weekday())
            sun = mon + timedelta(days=6)
            key = (mon, sun)
            if key not in weekly_dict:
                weekly_dict[key] = {
                    'label': f"{mon.strftime('%d %b %Y')} to {sun.strftime('%d %b %Y')}",
                    'iso_week': f"Week {mon.isocalendar()[1]}",
                    'pcs': 0.0,
                    'tons': 0.0,
                    'revenue': 0.0,
                    'trips': 0,
                    'wages': 0.0
                }
            weekly_dict[key]['wages'] += l.total_amount

        for key, data in sorted(weekly_dict.items(), key=lambda x: x[0][0], reverse=True):
            writer.writerow([data['label'], data['iso_week'], f"{data['pcs']:.0f}", f"{data['tons']:.2f}", data['trips'], f"{data['wages']:.2f}", f"{data['revenue']:.2f}"])

    elif view_mode == 'monthly':
        writer.writerow(['Month', 'Dispatched Pieces (Pcs)', 'Dispatched Bulk (MT)', 'Vehicle Trips', 'Loading Labor Paid (INR)', 'Sales Revenue (INR)'])
        monthly_dict = {}
        for o in outward_entries:
            key = (o.date.year, o.date.month)
            if key not in monthly_dict:
                monthly_dict[key] = {
                    'label': datetime(o.date.year, o.date.month, 1).strftime('%B %Y'),
                    'pcs': 0.0,
                    'tons': 0.0,
                    'revenue': 0.0,
                    'trips': 0,
                    'wages': 0.0
                }
            unit_str = (o.quantity_unit or '').lower()
            if 'piece' in unit_str or 'pcs' in unit_str:
                monthly_dict[key]['pcs'] += o.quantity_mt
            elif 'ton' in unit_str or 'mt' in unit_str:
                monthly_dict[key]['tons'] += o.quantity_mt
            else:
                monthly_dict[key]['pcs'] += o.quantity_mt
            monthly_dict[key]['revenue'] += o.amount
            monthly_dict[key]['trips'] += 1

        for l in loading_entries:
            key = (l.date.year, l.date.month)
            if key not in monthly_dict:
                monthly_dict[key] = {
                    'label': datetime(l.date.year, l.date.month, 1).strftime('%B %Y'),
                    'pcs': 0.0,
                    'tons': 0.0,
                    'revenue': 0.0,
                    'trips': 0,
                    'wages': 0.0
                }
            monthly_dict[key]['wages'] += l.total_amount

        for key, data in sorted(monthly_dict.items(), key=lambda x: (x[0][0], x[0][1]), reverse=True):
            writer.writerow([data['label'], f"{data['pcs']:.0f}", f"{data['tons']:.2f}", data['trips'], f"{data['wages']:.2f}", f"{data['revenue']:.2f}"])

    else:
        writer.writerow(['ID', 'Date', 'Operation', 'Product', 'Quantity Loaded', 'Unit', 'Rate (INR)', 'Total Loading Wage (INR)', 'Vehicle No', 'Workers Count', 'Wage Per Worker (INR)', 'Notes'])
        for e in loading_entries:
            writer.writerow([
                e.id,
                e.date.strftime('%Y-%m-%d'),
                e.job_type,
                e.product_name,
                f'{e.quantity:.0f}',
                e.unit,
                f'{e.rate_per_unit:.2f}',
                f'{e.total_amount:.2f}',
                e.vehicle_no or '',
                e.worker_count,
                f'{e.wage_per_worker:.2f}',
                e.notes or ''
            ])

    filename_suffix = f"_{view_mode}" if view_mode != 'daily' else ""
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=loading_sheet{filename_suffix}_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/export')
@login_required
def export_csv():
    all_products = get_all_finished_products()
    all_raw_mats = get_all_raw_materials()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['--- FINISHED GOODS STOCK (BRICKS & BLOCKS) ---'])
    writer.writerow(['Product Name', 'Total Produced (Pcs)', 'Total Dispatched (Pcs)', 'Current Balance Stock (Pcs)', 'Unit', 'Stock Status'])

    for prod in all_products:
        produced_qty = db.session.query(func.sum(JobWageEntry.quantity)).filter(
            JobWageEntry.product_name.ilike(f'%{prod}%'),
            JobWageEntry.job_type.ilike('%Production%')
        ).scalar() or 0.0

        dispatched_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
            MaterialOutward.material_type.ilike(f'%{prod}%')
        ).scalar() or 0.0

        balance = produced_qty - dispatched_qty
        status = 'In Stock' if balance > 3000 else ('Low Stock' if balance > 0 else 'Out of Stock')

        if produced_qty > 0 or dispatched_qty > 0 or prod in STANDARD_PRODUCTS[:6]:
            writer.writerow([prod, f'{produced_qty:.0f}', f'{dispatched_qty:.0f}', f'{balance:.0f}', 'Pieces', status])

    writer.writerow([])
    writer.writerow(['--- RAW MATERIALS STOCK (TONS / MT) ---'])
    writer.writerow(['Material Name', 'Total Inward (MT)', 'Total Outward / Used (MT)', 'Current Balance (MT)', 'Unit'])

    for mat in all_raw_mats:
        inward_qty = db.session.query(func.sum(MaterialInward.quantity_mt)).filter(
            MaterialInward.material_type.ilike(f'%{mat}%')
        ).scalar() or 0.0

        outward_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
            MaterialOutward.material_type.ilike(f'%{mat}%')
        ).scalar() or 0.0

        balance = inward_qty - outward_qty
        if inward_qty > 0 or outward_qty > 0:
            writer.writerow([mat, f'{inward_qty:.2f}', f'{outward_qty:.2f}', f'{balance:.2f}', 'Ton'])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=plant_stock_inventory_{date.today().strftime("%Y%m%d")}.csv'
    return response
