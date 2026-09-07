import io
import csv
from datetime import date, datetime
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from models import db, JobWageEntry, MaterialInward, MaterialOutward, JobRateSetting
from sqlalchemy import func, distinct

bp = Blueprint('stock', __name__, url_prefix='/stock')

# Standard Finished Products list for brick/block manufacturing
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
    """Get all finished product names registered across settings, production entries, and dispatches."""
    products_set = set(STANDARD_PRODUCTS)
    try:
        # From JobRateSetting
        rates_prods = [r[0] for r in db.session.query(distinct(JobRateSetting.product_name)).all() if r[0]]
        products_set.update(rates_prods)
        # From JobWageEntry
        job_prods = [r[0] for r in db.session.query(distinct(JobWageEntry.product_name)).all() if r[0]]
        products_set.update(job_prods)
        # From MaterialOutward with piece units
        out_prods = [r[0] for r in db.session.query(distinct(MaterialOutward.material_type)).all() if r[0]]
        for p in out_prods:
            if any(term in p.lower() for term in ['brick', 'block', 'paver', 'aac', 'modular', 'solid', 'hollow']):
                products_set.update([p])
    except Exception:
        pass
    
    # Keep standard in order first, then custom
    custom = sorted([p for p in products_set if p not in STANDARD_PRODUCTS])
    return STANDARD_PRODUCTS + custom


def get_all_raw_materials():
    """Get all raw materials registered across inward and outward."""
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
    today = date.today()
    search = request.args.get('search', '').strip()
    status_filter = request.args.get('status', 'all')  # all, in_stock, low_stock, out_of_stock

    all_products = get_all_finished_products()
    all_raw_mats = get_all_raw_materials()

    # 1. Finished Goods Stock (Pieces / Pcs)
    # Production adds to stock (+) | Outward minuses from stock (-)
    finished_goods_stock = []
    total_yard_pieces = 0.0
    total_produced_all = 0.0
    total_dispatched_all = 0.0

    for prod in all_products:
        if search and search.lower() not in prod.lower():
            continue

        # Total Produced (+)
        produced_qty = db.session.query(func.sum(JobWageEntry.quantity)).filter(
            JobWageEntry.product_name.ilike(f'%{prod}%'),
            JobWageEntry.job_type.ilike('%Production%')
        ).scalar() or 0.0

        # Total Dispatched (-)
        dispatched_qty = db.session.query(func.sum(MaterialOutward.quantity_mt)).filter(
            MaterialOutward.material_type.ilike(f'%{prod}%')
        ).scalar() or 0.0

        current_balance = produced_qty - dispatched_qty
        
        # Determine status
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

        # Filter by status
        if status_filter == 'in_stock' and current_balance <= 0:
            continue
        elif status_filter == 'low_stock' and (current_balance <= 0 or current_balance > 3000):
            continue
        elif status_filter == 'out_of_stock' and current_balance > 0:
            continue

        # Only include if there is activity or standard items
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

    # 2. Raw Materials Stock (Tons / MT)
    # Inward adds to stock (+) | Outward minuses from stock (-)
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

    # 3. Live Stock Movement Activity Feed (Last 6 Production + Last 6 Dispatches)
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


@bp.route('/export')
@login_required
def export_csv():
    all_products = get_all_finished_products()
    all_raw_mats = get_all_raw_materials()

    output = io.StringIO()
    writer = csv.writer(output)

    # Section 1: Finished Goods
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
    # Section 2: Raw Materials
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
