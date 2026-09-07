from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from models import db, MaterialInward, MaterialOutward, Party
from datetime import datetime, date
from sqlalchemy import distinct

bp = Blueprint('materials', __name__, url_prefix='/materials')

# Comprehensive standard list of materials
MATERIAL_TYPES = [
    # --- Core Daily Raw Materials ---
    'Fly Ash',
    'Class F Fly Ash',
    'Class C Fly Ash',
    'Cement',
    'Cement (OPC 53 Grade)',
    'Cement (OPC 43 Grade)',
    'Cement (PPC)',
    'Cement (PSC Slag)',
    'White Cement',
    'Jelly (Blue Metal)',
    'Jelly 20mm (3/4" Jelly)',
    'Jelly 12mm (1/2" Jelly)',
    'Jelly 40mm (1.5" Jelly)',
    'Baby Jelly (6mm / 8mm Grit)',
    'Stone Dust / Quarry Dust',
    'Cooldust / Coal Dust',
    'M-Sand (Manufactured Sand)',
    'P-Sand (Plastering Sand)',
    'River Sand / Natural Sand',
    'Crushed Aggregate 10mm',
    'Crushed Aggregate 20mm',
    'Grit (6mm / 8mm)',
    'Gypsum (Mineral / Chemical / FGD)',
    'Quicklime',
    'Hydrated Lime / Slaked Lime',
    'Lime Powder / Limestone',
    'GGBS (Ground Granulated Blast-furnace Slag)',
    'GGBFS Slag',
    'Micro Silica / Silica Fume',

    # --- Finished Products: Hollow & Solid Blocks ---
    'Hollow Block 4" (400 x 200 x 100 mm)',
    'Hollow Block 6" (400 x 200 x 150 mm)',
    'Hollow Block 8" (400 x 200 x 200 mm)',
    'Hollow Block 9" (400 x 200 x 225 mm)',
    'Hollow Block 12" (400 x 200 x 300 mm)',
    'Solid Block 4" (400 x 200 x 100 mm)',
    'Solid Block 6" (400 x 200 x 150 mm)',
    'Solid Block 8" (400 x 200 x 200 mm)',
    'Corner / Lintel Hollow Block',

    # --- Finished Products: Fly Ash Bricks ---
    'Fly Ash Brick 9"x4"x3" (230 x 110 x 75 mm)',
    'Fly Ash Brick Modular (190 x 90 x 90 mm)',
    'Fly Ash Brick (230 x 110 x 70 mm)',
    'Heavy Duty Fly Ash Brick (Class 10/15)',
    'Interlocking Fly Ash Brick',
    'Fly Ash Paver Blocks (60mm / 80mm)',
    'AAC Blocks',

    # --- Regional Power Plant Ash ---
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
    'Korba Ash (NTPC)',
    'Sipat Ash (NTPC)'
]

QUANTITY_UNITS = [
    'Pieces / Pcs',
    'Ton',
    'Load / Trip',
    'Bags (50kg)',
    'Bags (40kg)',
    'CFT',
    'Cu.m',
    'Kg',
    'Quintal',
    'Truck Load',
    'Tractor Load',
    'Liters'
]


def get_available_materials():
    materials_set = set(MATERIAL_TYPES)
    try:
        inward_mats = [r[0] for r in db.session.query(distinct(MaterialInward.material_type)).all() if r[0]]
        outward_mats = [r[0] for r in db.session.query(distinct(MaterialOutward.material_type)).all() if r[0]]
        materials_set.update(inward_mats)
        materials_set.update(outward_mats)
    except Exception:
        pass
    custom = sorted([m for m in materials_set if m not in MATERIAL_TYPES])
    return MATERIAL_TYPES + custom


def get_available_units():
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
    
    total_tons = sum(e.quantity_mt for e in entries if e.quantity_mt and ('ton' in (e.quantity_unit or '').lower() or 'mt' in (e.quantity_unit or '').lower()))
    total_loads = sum(e.quantity_mt for e in entries if e.quantity_mt and ('load' in (e.quantity_unit or '').lower() or 'trip' in (e.quantity_unit or '').lower()))
    
    parties = Party.query.order_by(Party.name).all()
    
    return render_template('materials/inward_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           party_id=int(party_id) if party_id else None,
                           material_type=material_type,
                           parties=parties,
                           total_qty=total_qty,
                           total_tons=total_tons,
                           total_loads=total_loads,
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
                           quantity_units=get_available_units(),
                           today=date.today().strftime('%Y-%m-%d'),
                           entry=None)


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
                           quantity_units=get_available_units(),
                           today=date.today().strftime('%Y-%m-%d'))


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
    
    total_pieces = sum(e.quantity_mt for e in entries if e.quantity_mt and ('piece' in (e.quantity_unit or '').lower() or 'pcs' in (e.quantity_unit or '').lower() or 'nos' in (e.quantity_unit or '').lower()))
    total_tons = sum(e.quantity_mt for e in entries if e.quantity_mt and ('ton' in (e.quantity_unit or '').lower() or 'mt' in (e.quantity_unit or '').lower()))
    total_loads = sum(e.quantity_mt for e in entries if e.quantity_mt and ('load' in (e.quantity_unit or '').lower() or 'trip' in (e.quantity_unit or '').lower()))
    
    parties = Party.query.order_by(Party.name).all()
    
    return render_template('materials/outward_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           party_id=int(party_id) if party_id else None,
                           material_type=material_type,
                           parties=parties,
                           total_qty=total_qty,
                           total_pieces=total_pieces,
                           total_tons=total_tons,
                           total_loads=total_loads,
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
                quantity_unit=request.form.get('quantity_unit', 'Pieces / Pcs'),
                vehicle_no=request.form.get('vehicle_no'),
                rate=float(request.form['rate']) if request.form.get('rate') else 0.0,
                amount=float(request.form['amount']) if request.form.get('amount') else 0.0,
                notes=request.form.get('notes')
            )
            db.session.add(entry)
            db.session.commit()
            flash('Outward dispatch entry added successfully.', 'success')
            return redirect(url_for('materials.outward_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding entry: {str(e)}', 'error')
            
    parties = Party.query.filter(Party.party_type.in_(['customer', 'both'])).order_by(Party.name).all()
    return render_template('materials/outward_form.html',
                           parties=parties,
                           material_types=get_available_materials(),
                           quantity_units=get_available_units(),
                           today=date.today().strftime('%Y-%m-%d'),
                           entry=None)


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
            entry.quantity_unit = request.form.get('quantity_unit', 'Pieces / Pcs')
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
                           quantity_units=get_available_units(),
                           today=date.today().strftime('%Y-%m-%d'))


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
