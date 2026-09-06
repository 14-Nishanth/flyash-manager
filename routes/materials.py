from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, MaterialInward, MaterialOutward, Party
from datetime import datetime, date
from sqlalchemy import distinct

bp = Blueprint('materials', __name__, url_prefix='/materials')

# Comprehensive standard list of materials (Power Plants, Fly Ash, Cement, Minerals, Byproducts)
MATERIAL_TYPES = [
    # --- Regional & Thermal Power Plant Fly Ash ---
    'Fly Ash',
    'Mettur Flyash',
    'Tirupur Flyash',
    'Tuticorin Ash (TTPS)',
    'Neyveli Ash (NLC)',
    'North Chennai Ash (NCTPS)',
    'Ennore Ash (ETPS)',
    'Vallur Ash (NTECL)',
    'Bellary Ash (BTPS)',
    'Raichur Ash (RTPS)',
    'Kudgi Ash (NTPC)',
    'Ramagundam Ash (NTPC)',
    'Simhadri Ash (NTPC)',
    'Kothagudem Ash (KTPS)',
    'Vijayawada Ash (NTTPS)',
    'Rayalaseema Ash (RTPPS)',
    'Talcher Ash (NTPC)',
    'Jharsuguda Ash',
    'Vindhyachal Ash (NTPC)',
    'Singrauli Ash',
    'Korba Ash (NTPC)',
    'Sipat Ash (NTPC)',
    'Rihand Ash (NTPC)',
    'Dadri Ash (NTPC)',
    'Unchahar Ash',
    'Badarpur Ash',
    'Ropar Ash',
    'Panipat Ash',
    'Kota Ash',
    'Suratgarh Ash',
    'Chhabra Ash',
    'Mundra Ash',
    'Sasan Ash',
    'Wanakbori Ash',
    'Ukai Ash',
    'Gandhinagar Ash',
    'Chandrapur Ash',
    'Koradi Ash',
    'Khaperkheda Ash',
    'Bhusawal Ash',
    'Trombay Ash',
    'Kolaghat Ash',
    'Bakreswar Ash',
    'Farakka Ash (NTPC)',
    'Kahalgaon Ash (NTPC)',

    # --- Ash Classifications & Byproducts ---
    'Class F Fly Ash',
    'Class C Fly Ash',
    'Pond Ash',
    'Bottom Ash',
    'Cenospheres (Hollow Ash)',
    'Low Carbon Fly Ash',
    'High Carbon Fly Ash',
    'Dry Fly Ash',
    'Wet Fly Ash',
    'Micro / Ultrafine Fly Ash',
    'Rice Husk Ash (RHA)',
    'Biomass Ash / Wood Ash',
    'Bagasse Ash',
    'Coal Ash',

    # --- Coal, Dust & Carbon Materials ---
    'Cooldust / Coal Dust',
    'Stone Dust / Quarry Dust',
    'Mineral Dust',
    'Silica Dust',
    'Foundry Dust',
    'Boiler Ash Dust',
    'Raw Coal',
    'Thermal Steam Coal',
    'Imported Coal',
    'Indian G-Grade Coal',
    'Lignite',
    'Petcoke',
    'Anthracite',
    'Met Coke / Charcoal',
    'Carbon Black',

    # --- Cement & Pozzolanic Materials ---
    'Cement',
    'OPC 53 Grade',
    'OPC 43 Grade',
    'OPC 33 Grade',
    'PPC Cement',
    'PSC Slag Cement',
    'White Cement',
    'GGBS (Ground Granulated Blast-furnace Slag)',
    'GGBFS Slag',
    'Micro Silica / Silica Fume',
    'Metakaolin',
    'Calcined Clay (LC3)',
    'Gypsum (Mineral / Chemical / FGD)',
    'Clinker (Grey / White)',
    'Quicklime',
    'Hydrated Lime / Slaked Lime',
    'Limestone / Lime Powder',
    'Dolomite Powder',

    # --- Sand, Aggregates & Minerals ---
    'M-Sand (Manufactured Sand)',
    'P-Sand (Plastering Sand)',
    'River Sand / Natural Sand',
    'Silica Sand / Quartz Sand',
    'Crushed Aggregate 10mm',
    'Crushed Aggregate 20mm',
    'Crushed Aggregate 40mm',
    'Grit (6mm / 8mm)',
    'GSB (Granular Sub Base)',
    'WMM (Wet Mix Macadam)',
    'Bentonite',
    'Calcite Powder',
    'Marble Powder',
    'Red Mud',
    'Copper Slag (Grit)',
    'Iron / Steel Slag',

    # --- Your Finished Products: Hollow Blocks (All Sizes) ---
    'Hollow Block 4" (400 x 200 x 100 mm)',
    'Hollow Block 6" (400 x 200 x 150 mm)',
    'Hollow Block 8" (400 x 200 x 200 mm)',
    'Hollow Block 9" (400 x 200 x 225 mm)',
    'Hollow Block 12" (400 x 200 x 300 mm)',
    'Solid Block 4" (400 x 200 x 100 mm)',
    'Solid Block 6" (400 x 200 x 150 mm)',
    'Solid Block 8" (400 x 200 x 200 mm)',
    'Corner / Lintel Hollow Block',

    # --- Your Finished Products: Fly Ash Bricks (All Sizes) ---
    'Fly Ash Brick 9"x4"x3" (230 x 110 x 75 mm)',
    'Fly Ash Brick Modular (190 x 90 x 90 mm)',
    'Fly Ash Brick (230 x 110 x 70 mm)',
    'Heavy Duty Fly Ash Brick (Class 10/15)',
    'Interlocking Fly Ash Brick',
    'Fly Ash Paver Blocks (60mm / 80mm)',
    'AAC Blocks',
    'Other'
]

# Comprehensive standard list of measuring units worldwide
QUANTITY_UNITS = [
    # Weight Units
    'Ton',
    'MT (Metric Tonne)',
    'KG (Kilogram)',
    'Quintal (100 KG)',
    'Gram (g)',
    'Pound (lbs)',

    # Bags & Packaging Units
    'Bags',
    'Bags (50 KG)',
    'Bags (25 KG)',
    'Bags (40 KG)',
    'Jumbo Bags (1 Ton FIBC)',
    'Sacks',
    'Pieces / Pcs',
    'Nos (Numbers)',
    'Unit',
    'Packets',
    'Bundles',
    'Boxes',
    'Pallets',
    'Barrels',
    'Drums',

    # Volume & Bulk Transport Units
    'CFT (Cubic Feet)',
    'Cubic Meter (m³)',
    'Brass (100 CFT)',
    'Trolley',
    'Tipper (10 Wheeler)',
    'Tipper (12 Wheeler)',
    'Tipper (14 Wheeler)',
    'Tipper (16 Wheeler)',
    'Dumper',
    'Hyva (18 Wheeler)',
    'Hyva (22 Wheeler)',
    'Bulker (Tanker)',
    'Tanker / Capsule',
    'Load',
    'Trip',
    'Truckload',
    'Lorry Load',

    # Liquid Units
    'Liter (L)',
    'KL (Kilo Liter)',
    'Gallon'
]


def get_available_materials():
    """Returns combined list of predefined materials + any custom materials saved in database."""
    materials_set = set(MATERIAL_TYPES)
    try:
        inward_mats = [r[0] for r in db.session.query(distinct(MaterialInward.material_type)).all() if r[0]]
        outward_mats = [r[0] for r in db.session.query(distinct(MaterialOutward.material_type)).all() if r[0]]
        materials_set.update(inward_mats)
        materials_set.update(outward_mats)
    except Exception:
        pass
    # Keep predefined in order, then append custom
    custom = sorted([m for m in materials_set if m not in MATERIAL_TYPES])
    return MATERIAL_TYPES + custom


def get_available_units():
    """Returns combined list of predefined units + any custom units saved in database."""
    units_set = set(QUANTITY_UNITS)
    try:
        inward_units = [r[0] for r in db.session.query(distinct(MaterialInward.quantity_unit)).all() if r[0]]
        outward_units = [r[0] for r in db.session.query(distinct(MaterialOutward.quantity_unit)).all() if r[0]]
        units_set.update(inward_units)
        units_set.update(outward_units)
    except Exception:
        pass
    custom = sorted([u for u in units_set if u not in QUANTITY_UNITS])
    return QUANTITY_UNITS + custom


@bp.route('/inward')
@login_required
def inward_list():
    today = date.today()
    first_day = today.replace(day=1)
    
    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))
    party_id = request.args.get('party_id')
    material_type = request.args.get('material_type')
    
    query = MaterialInward.query
    
    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        query = query.filter(MaterialInward.date >= from_date, MaterialInward.date <= to_date)
    except ValueError:
        pass
        
    if party_id:
        query = query.filter(MaterialInward.party_id == party_id)
        
    if material_type:
        query = query.filter(MaterialInward.material_type == material_type)
        
    entries = query.order_by(MaterialInward.date.desc(), MaterialInward.id.desc()).all()
    
    total_qty = sum(entry.quantity_mt for entry in entries if entry.quantity_mt)
    total_amount = sum(entry.amount for entry in entries if entry.amount)
    
    parties = Party.query.order_by(Party.name).all()
    
    return render_template('materials/inward_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           party_id=int(party_id) if party_id else None,
                           material_type=material_type,
                           parties=parties,
                           total_qty=total_qty,
                           total_amount=total_amount,
                           material_types=get_available_materials())


@bp.route('/inward/add', methods=['GET', 'POST'])
@login_required
def inward_add():
    if request.method == 'POST':
        try:
            entry = MaterialInward(
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                party_id=request.form['party_id'],
                material_type=request.form.get('material_type'),
                quantity_mt=float(request.form['quantity_mt']) if request.form.get('quantity_mt') else 0.0,
                quantity_unit=request.form.get('quantity_unit', 'Ton'),
                vehicle_no=request.form.get('vehicle_no'),
                rate=float(request.form['rate']) if request.form.get('rate') else 0.0,
                amount=float(request.form['amount']) if request.form.get('amount') else 0.0,
                notes=request.form.get('notes')
            )
            db.session.add(entry)
            db.session.commit()
            flash('Inward entry added successfully.', 'success')
            return redirect(url_for('materials.inward_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding entry: {str(e)}', 'error')
            
    parties = Party.query.filter(Party.party_type.in_(['supplier', 'both'])).order_by(Party.name).all()
    return render_template('materials/inward_form.html',
                           parties=parties,
                           material_types=get_available_materials(),
                           quantity_units=get_available_units())


@bp.route('/inward/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def inward_edit(id):
    entry = MaterialInward.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            entry.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            entry.party_id = request.form['party_id']
            entry.material_type = request.form.get('material_type')
            entry.quantity_mt = float(request.form['quantity_mt']) if request.form.get('quantity_mt') else 0.0
            entry.quantity_unit = request.form.get('quantity_unit', 'Ton')
            entry.vehicle_no = request.form.get('vehicle_no')
            entry.rate = float(request.form['rate']) if request.form.get('rate') else 0.0
            entry.amount = float(request.form['amount']) if request.form.get('amount') else 0.0
            entry.notes = request.form.get('notes')
            
            db.session.commit()
            flash('Inward entry updated successfully.', 'success')
            return redirect(url_for('materials.inward_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating entry: {str(e)}', 'error')
            
    parties = Party.query.filter(Party.party_type.in_(['supplier', 'both'])).order_by(Party.name).all()
    return render_template('materials/inward_form.html',
                           entry=entry,
                           parties=parties,
                           material_types=get_available_materials(),
                           quantity_units=get_available_units())


@bp.route('/inward/<int:id>/delete', methods=['POST'])
@login_required
def inward_delete(id):
    entry = MaterialInward.query.get_or_404(id)
    try:
        db.session.delete(entry)
        db.session.commit()
        flash('Inward entry deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting entry: {str(e)}', 'error')
    return redirect(url_for('materials.inward_list'))


@bp.route('/outward')
@login_required
def outward_list():
    today = date.today()
    first_day = today.replace(day=1)
    
    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))
    party_id = request.args.get('party_id')
    material_type = request.args.get('material_type')
    
    query = MaterialOutward.query
    
    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        query = query.filter(MaterialOutward.date >= from_date, MaterialOutward.date <= to_date)
    except ValueError:
        pass
        
    if party_id:
        query = query.filter(MaterialOutward.party_id == party_id)
        
    if material_type:
        query = query.filter(MaterialOutward.material_type == material_type)
        
    entries = query.order_by(MaterialOutward.date.desc(), MaterialOutward.id.desc()).all()
    
    total_qty = sum(entry.quantity_mt for entry in entries if entry.quantity_mt)
    total_amount = sum(entry.amount for entry in entries if entry.amount)
    
    parties = Party.query.order_by(Party.name).all()
    
    return render_template('materials/outward_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           party_id=int(party_id) if party_id else None,
                           material_type=material_type,
                           parties=parties,
                           total_qty=total_qty,
                           total_amount=total_amount,
                           material_types=get_available_materials())


@bp.route('/outward/add', methods=['GET', 'POST'])
@login_required
def outward_add():
    if request.method == 'POST':
        try:
            entry = MaterialOutward(
                date=datetime.strptime(request.form['date'], '%Y-%m-%d').date(),
                party_id=request.form['party_id'],
                material_type=request.form.get('material_type'),
                quantity_mt=float(request.form['quantity_mt']) if request.form.get('quantity_mt') else 0.0,
                quantity_unit=request.form.get('quantity_unit', 'Ton'),
                vehicle_no=request.form.get('vehicle_no'),
                rate=float(request.form['rate']) if request.form.get('rate') else 0.0,
                amount=float(request.form['amount']) if request.form.get('amount') else 0.0,
                notes=request.form.get('notes')
            )
            db.session.add(entry)
            db.session.commit()
            flash('Outward entry added successfully.', 'success')
            return redirect(url_for('materials.outward_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding entry: {str(e)}', 'error')
            
    parties = Party.query.filter(Party.party_type.in_(['customer', 'both'])).order_by(Party.name).all()
    return render_template('materials/outward_form.html',
                           parties=parties,
                           material_types=get_available_materials(),
                           quantity_units=get_available_units())


@bp.route('/outward/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def outward_edit(id):
    entry = MaterialOutward.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            entry.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            entry.party_id = request.form['party_id']
            entry.material_type = request.form.get('material_type')
            entry.quantity_mt = float(request.form['quantity_mt']) if request.form.get('quantity_mt') else 0.0
            entry.quantity_unit = request.form.get('quantity_unit', 'Ton')
            entry.vehicle_no = request.form.get('vehicle_no')
            entry.rate = float(request.form['rate']) if request.form.get('rate') else 0.0
            entry.amount = float(request.form['amount']) if request.form.get('amount') else 0.0
            entry.notes = request.form.get('notes')
            
            db.session.commit()
            flash('Outward entry updated successfully.', 'success')
            return redirect(url_for('materials.outward_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating entry: {str(e)}', 'error')
            
    parties = Party.query.filter(Party.party_type.in_(['customer', 'both'])).order_by(Party.name).all()
    return render_template('materials/outward_form.html',
                           entry=entry,
                           parties=parties,
                           material_types=get_available_materials(),
                           quantity_units=get_available_units())


@bp.route('/outward/<int:id>/delete', methods=['POST'])
@login_required
def outward_delete(id):
    entry = MaterialOutward.query.get_or_404(id)
    try:
        db.session.delete(entry)
        db.session.commit()
        flash('Outward entry deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting entry: {str(e)}', 'error')
    return redirect(url_for('materials.outward_list'))
