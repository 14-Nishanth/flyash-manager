import io
import csv
from datetime import date, datetime, timedelta
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


@bp.route('/')
@login_required
def index():
    """Main Stock & Yard Balance Sheet."""
    today = date.today()
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

        if status_filter == 'in_stock' and current_balance <= 0:
            continue
        elif status_filter == 'low_stock' and (current_balance <= 0 or current_balance > 3000):
            continue
        elif status_filter == 'out_of_stock' and current_balance > 0:
            continue

        if produced_qty > 0 or dispatched_qty > 0 or prod in STANDARD_PRODUCTS[:6]:
            finished_goods_stock.append({
                'name': prod,
                'produced': produced_qty,
                'dispatched': dispatched_qty,
                'balance': current_balance,
                'unit': 'Pieces / Pcs',
                'status': stock_status,
                'badge_class': badge_class
            })
            total_yard_pieces += max(0, current_balance)
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

        balance_tons = inward_qty - outward_qty

        if inward_qty > 0 or outward_qty > 0 or mat in ['Fly Ash', 'Cement', 'Jelly (Blue Metal)', 'Stone Dust / Quarry Dust', 'M-Sand (Manufactured Sand)']:
            raw_materials_stock.append({
                'name': mat,
                'inward': inward_qty,
                'outward': outward_qty,
                'balance': round(balance_tons, 2),
                'unit': 'Ton (MT)'
            })
            total_raw_tons += max(0, balance_tons)

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
    """Dedicated Production Sheet tracking all manufacturing output adding to stock (+)."""
    today = date.today()
    first_day = today.replace(day=1)

    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))
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
    
    # Month to date and today metrics
    today_produced = db.session.query(func.sum(JobWageEntry.quantity)).filter(
        JobWageEntry.date == today,
        JobWageEntry.job_type.ilike('%Production%')
    ).scalar() or 0.0

    month_produced = db.session.query(func.sum(JobWageEntry.quantity)).filter(
        JobWageEntry.date >= first_day,
        JobWageEntry.date <= today,
        JobWageEntry.job_type.ilike('%Production%')
    ).scalar() or 0.0

    # Product-wise summary in current filtered view
    product_summary = {}
    for e in entries:
        product_summary[e.product_name] = product_summary.get(e.product_name, 0.0) + e.quantity

    groups = EmployeeGroup.query.filter_by(is_active=True).all()
    all_products = get_all_finished_products()

    return render_template(
        'stock/production_sheet.html',
        entries=entries,
        total_production_qty=total_production_qty,
        total_labor_cost=total_labor_cost,
        today_produced=today_produced,
        month_produced=month_produced,
        product_summary=product_summary,
        groups=groups,
        all_products=all_products,
        from_date=from_date_str,
        to_date=to_date_str,
        selected_product=product_name,
        selected_group=group_id,
        search=search
    )


@bp.route('/loading')
@login_required
def loading_sheet():
    """Dedicated Loading & Dispatch Sheet tracking lorry/tractor loading deducting from stock (-)."""
    today = date.today()
    first_day = today.replace(day=1)

    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))
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
        all_products=all_products,
        from_date=from_date_str,
        to_date=to_date_str,
        selected_product=product_name,
        search=search
    )


@bp.route('/production/export')
@login_required
def export_production_csv():
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

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=production_sheet_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/loading/export')
@login_required
def export_loading_csv():
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    query = JobWageEntry.query.filter(
        (JobWageEntry.job_type.ilike('%Loading%')) | (JobWageEntry.job_type.ilike('%Unloading%'))
    )
    try:
        if from_date_str:
            query = query.filter(JobWageEntry.date >= datetime.strptime(from_date_str, '%Y-%m-%d').date())
        if to_date_str:
            query = query.filter(JobWageEntry.date <= datetime.strptime(to_date_str, '%Y-%m-%d').date())
    except ValueError:
        pass

    entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Date', 'Operation', 'Product', 'Quantity Loaded', 'Unit', 'Rate (INR)', 'Total Loading Wage (INR)', 'Vehicle No', 'Workers Count', 'Wage Per Worker (INR)', 'Notes'])

    for e in entries:
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

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=loading_sheet_{date.today().strftime("%Y%m%d")}.csv'
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
