def resolve_employee_period(period_param, from_date_str, to_date_str):
    import calendar
    from datetime import timedelta
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
    if not from_date_str and not to_date_str:
        return today.replace(day=1).strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    return from_date_str, to_date_str

import io
import csv
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required
from models import db, Employee, Attendance, JobWageEntry, EmployeeJobAllocation, JobRateSetting, EmployeeGroup
from datetime import datetime, date
from sqlalchemy import func

bp = Blueprint('employees', __name__, url_prefix='/employees')

JOB_TYPES = [
    'Production (Per Piece)',
    'Loading Only',
    'Unloading Only',
    'Both Loading & Unloading',
    'Stacking & Curing',
    'Raw Material Shifting',
    'General Work / Custom'
]

JOB_PRODUCTS = [
    'Fly Ash Brick 9"x4"x3" (Standard)',
    'Fly Ash Brick Modular (190 x 90 x 90 mm)',
    'Fly Ash Brick Non-Modular',
    'Heavy Duty Fly Ash Brick',
    'Solid Block 4"',
    'Solid Block 6"',
    'Solid Block 8"',
    'Hollow Block 4" (400 x 200 x 100 mm)',
    'Hollow Block 6" (400 x 200 x 150 mm)',
    'Hollow Block 8" (400 x 200 x 200 mm)',
    'Hollow Block 9" (400 x 200 x 225 mm)',
    'Hollow Block 12" (400 x 200 x 300 mm)',
    'Fly Ash Paver Blocks (60mm / 80mm)',
    'Cement Bags Handling',
    'Other Work'
]

JOB_UNITS = ['Pieces / Pcs', 'Nos (Numbers)', 'Bags', 'Ton', 'Load', 'Trip', 'Trolley', 'Brass', 'Hours', 'Day']


# ==============================================================================
# EMPLOYEE MANAGEMENT
# ==============================================================================

@bp.route('/')
@login_required
def list_employees():
    status = request.args.get('status', 'active')
    
    query = Employee.query
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)
        
    employees = query.order_by(Employee.name).all()
    return render_template('employees/list.html', employees=employees, current_status=status)


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        role = request.form.get('role')
        daily_wage = request.form.get('daily_wage')
        joining_date = request.form.get('joining_date')
        is_active = request.form.get('is_active') == 'on'

        if not name:
            flash('Name is required.', 'error')
            return redirect(url_for('employees.add_employee'))

        try:
            emp = Employee(
                name=name,
                phone=phone,
                role=role,
                daily_wage=float(daily_wage) if daily_wage else 0.0,
                joining_date=datetime.strptime(joining_date, '%Y-%m-%d').date() if joining_date else None,
                is_active=is_active
            )
            db.session.add(emp)
            db.session.commit()
            flash('Employee added successfully.', 'success')
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding employee: {str(e)}', 'error')

    return render_template('employees/form.html', employee=None)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_employee(id):
    emp = Employee.query.get_or_404(id)
    if request.method == 'POST':
        emp.name = request.form.get('name')
        emp.phone = request.form.get('phone')
        emp.role = request.form.get('role')
        daily_wage = request.form.get('daily_wage')
        emp.daily_wage = float(daily_wage) if daily_wage else 0.0
        joining_date = request.form.get('joining_date')
        emp.joining_date = datetime.strptime(joining_date, '%Y-%m-%d').date() if joining_date else None
        emp.is_active = request.form.get('is_active') == 'on'

        if not emp.name:
            flash('Name is required.', 'error')
            return render_template('employees/form.html', employee=emp)

        try:
            db.session.commit()
            flash('Employee updated successfully.', 'success')
            return redirect(url_for('employees.list_employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating employee: {str(e)}', 'error')

    return render_template('employees/form.html', employee=emp)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_employee(id):
    emp = Employee.query.get_or_404(id)
    try:
        db.session.delete(emp)
        db.session.commit()
        flash('Employee deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting employee: {str(e)}', 'error')
    return redirect(url_for('employees.list_employees'))


# ==============================================================================
# ATTENDANCE MANAGEMENT
# ==============================================================================

@bp.route('/attendance', methods=['GET', 'POST'])
@login_required
def attendance():
    date_str = request.args.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    existing_attendance = Attendance.query.filter_by(date=selected_date).all()
    attendance_map = {a.employee_id: a for a in existing_attendance}

    if request.method == 'POST':
        try:
            for emp in employees:
                status = request.form.get(f'status_{emp.id}')
                notes = request.form.get(f'notes_{emp.id}')
                
                if status:
                    if emp.id in attendance_map:
                        att = attendance_map[emp.id]
                        att.status = status
                        att.notes = notes
                    else:
                        att = Attendance(
                            employee_id=emp.id,
                            date=selected_date,
                            status=status,
                            notes=notes
                        )
                        db.session.add(att)
            
            db.session.commit()
            flash('Attendance saved successfully.', 'success')
            return redirect(url_for('employees.attendance', date=selected_date.strftime('%Y-%m-%d')))
        except Exception as e:
            db.session.rollback()
            flash(f'Error saving attendance: {str(e)}', 'error')

    return render_template('employees/attendance.html', 
                           employees=employees, 
                           selected_date=selected_date, 
                           attendance_map=attendance_map)


@bp.route('/attendance/history')
@login_required
def attendance_history():
    employee_id = request.args.get('employee_id', type=int)
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')

    query = Attendance.query.join(Employee)

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if from_date_str:
        try:
            from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date >= from_date)
        except ValueError:
            pass
    if to_date_str:
        try:
            to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(Attendance.date <= to_date)
        except ValueError:
            pass

    records = query.order_by(Attendance.date.desc(), Employee.name).all()
    employees = Employee.query.order_by(Employee.name).all()
    
    summary = None
    if employee_id or from_date_str or to_date_str:
        total_present = 0
        total_absent = 0
        total_half_day = 0
        total_wages = 0.0

        for r in records:
            if r.status == 'present':
                total_present += 1
                total_wages += (r.employee.daily_wage or 0)
            elif r.status == 'absent':
                total_absent += 1
            elif r.status == 'half-day':
                total_half_day += 1
                total_wages += (r.employee.daily_wage or 0) / 2

        summary = {
            'present': total_present,
            'absent': total_absent,
            'half_day': total_half_day,
            'wages': total_wages
        }

    return render_template('employees/attendance_history.html', 
                           records=records, 
                           employees=employees, 
                           summary=summary,
                           current_emp=employee_id,
                           from_date=from_date_str,
                           to_date=to_date_str)


# ==============================================================================
# JOB RATE SETTINGS (PIECE RATES FOR PRODUCTION, LOADING, UNLOADING)
# ==============================================================================

@bp.route('/rates')
@login_required
def job_rates_list():
    product = request.args.get('product')
    job_type = request.args.get('job_type')

    query = JobRateSetting.query.filter_by(is_active=True)
    if product:
        query = query.filter(JobRateSetting.product_name.ilike(f'%{product}%'))
    if job_type:
        query = query.filter(JobRateSetting.job_type == job_type)

    rates = query.order_by(JobRateSetting.product_name, JobRateSetting.job_type).all()
    return render_template('employees/job_rates_list.html',
                           rates=rates,
                           job_products=JOB_PRODUCTS,
                           job_types=JOB_TYPES,
                           selected_product=product,
                           selected_job_type=job_type)


@bp.route('/rates/add', methods=['GET', 'POST'])
@login_required
def job_rate_add():
    if request.method == 'POST':
        product_name = request.form.get('product_name')
        job_type = request.form.get('job_type')
        rate_per_piece = float(request.form.get('rate_per_piece') or 0.0)
        unit = request.form.get('unit', 'Pieces / Pcs')
        notes = request.form.get('notes')

        if not product_name or not job_type:
            flash('Product name and Job type are required.', 'error')
            return redirect(url_for('employees.job_rate_add'))

        existing = JobRateSetting.query.filter_by(product_name=product_name, job_type=job_type).first()
        if existing:
            existing.rate_per_piece = rate_per_piece
            existing.unit = unit
            existing.notes = notes
            existing.is_active = True
            db.session.commit()
            flash(f'Updated rate for {product_name} ({job_type}) to ₹{rate_per_piece:.2f} per piece.', 'success')
            return redirect(url_for('employees.job_rates_list'))

        rate_obj = JobRateSetting(
            product_name=product_name,
            job_type=job_type,
            rate_per_piece=rate_per_piece,
            unit=unit,
            notes=notes
        )
        db.session.add(rate_obj)
        db.session.commit()
        flash(f'Piece rate of ₹{rate_per_piece:.2f} added for {product_name} ({job_type}).', 'success')
        return redirect(url_for('employees.job_rates_list'))

    return render_template('employees/job_rate_form.html',
                           rate=None,
                           job_products=JOB_PRODUCTS,
                           job_types=JOB_TYPES,
                           job_units=JOB_UNITS)


@bp.route('/rates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def job_rate_edit(id):
    rate = JobRateSetting.query.get_or_404(id)
    if request.method == 'POST':
        rate.product_name = request.form.get('product_name')
        rate.job_type = request.form.get('job_type')
        rate.rate_per_piece = float(request.form.get('rate_per_piece') or 0.0)
        rate.unit = request.form.get('unit', 'Pieces / Pcs')
        rate.notes = request.form.get('notes')
        rate.is_active = request.form.get('is_active') == 'on'

        db.session.commit()
        flash(f'Rate for {rate.product_name} updated successfully.', 'success')
        return redirect(url_for('employees.job_rates_list'))

    return render_template('employees/job_rate_form.html',
                           rate=rate,
                           job_products=JOB_PRODUCTS,
                           job_types=JOB_TYPES,
                           job_units=JOB_UNITS)


@bp.route('/rates/<int:id>/delete', methods=['POST'])
@login_required
def job_rate_delete(id):
    rate = JobRateSetting.query.get_or_404(id)
    db.session.delete(rate)
    db.session.commit()
    flash('Job rate deleted successfully.', 'success')
    return redirect(url_for('employees.job_rates_list'))


# ==============================================================================
# EMPLOYEE GROUPS & LABOR GANGS (TEAM POOLING)
# ==============================================================================

@bp.route('/groups')
@login_required
def employee_groups_list():
    groups = EmployeeGroup.query.filter_by(is_active=True).order_by(EmployeeGroup.name).all()
    all_employees = Employee.query.filter_by(is_active=True).all()
    return render_template('employees/groups_list.html', groups=groups, all_employees=all_employees)


@bp.route('/groups/add', methods=['GET', 'POST'])
@login_required
def employee_group_add():
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        default_job_type = request.form.get('default_job_type')
        default_product_name = request.form.get('default_product_name')
        member_ids = request.form.getlist('employee_ids')

        if not name:
            flash('Group Name is required.', 'error')
            return render_template('employees/group_form.html',
                                   group=None,
                                   employees=employees,
                                   job_types=JOB_TYPES,
                                   job_products=JOB_PRODUCTS)

        grp = EmployeeGroup(
            name=name,
            description=description,
            default_job_type=default_job_type,
            default_product_name=default_product_name
        )
        if member_ids:
            selected_emps = Employee.query.filter(Employee.id.in_([int(i) for i in member_ids])).all()
            grp.members = selected_emps

        db.session.add(grp)
        db.session.commit()
        flash(f'Employee Group "{name}" created with {len(grp.members)} members.', 'success')
        return redirect(url_for('employees.employee_groups_list'))

    return render_template('employees/group_form.html',
                           group=None,
                           employees=employees,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS)


@bp.route('/groups/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def employee_group_edit(id):
    grp = EmployeeGroup.query.get_or_404(id)
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    member_ids = [m.id for m in grp.members]

    if request.method == 'POST':
        grp.name = request.form.get('name')
        grp.description = request.form.get('description')
        grp.default_job_type = request.form.get('default_job_type')
        grp.default_product_name = request.form.get('default_product_name')
        grp.is_active = request.form.get('is_active') == 'on'

        selected_member_ids = request.form.getlist('employee_ids')
        if selected_member_ids:
            grp.members = Employee.query.filter(Employee.id.in_([int(i) for i in selected_member_ids])).all()
        else:
            grp.members = []

        db.session.commit()
        flash(f'Employee Group "{grp.name}" updated successfully.', 'success')
        return redirect(url_for('employees.employee_groups_list'))

    return render_template('employees/group_form.html',
                           group=grp,
                           member_ids=member_ids,
                           employees=employees,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS)


@bp.route('/groups/<int:id>/delete', methods=['POST'])
@login_required
def employee_group_delete(id):
    grp = EmployeeGroup.query.get_or_404(id)
    db.session.delete(grp)
    db.session.commit()
    flash(f'Group "{grp.name}" deleted successfully.', 'success')
    return redirect(url_for('employees.employee_groups_list'))


# ==============================================================================
# PIECE-RATE DAILY JOB ENTRIES & EQUAL WAGE DIVISION
# ==============================================================================

def calculate_net_job_quantity(entries):
    """
    Calculates the true net physical quantity of bricks/blocks produced or handled
    without double-counting when one group loads and another group unloads the same batch.
    """
    if not entries:
        return 0.0

    non_loading_qty = 0.0
    load_groups = {}

    for e in entries:
        jt = (e.job_type or '').lower()
        if 'loading' in jt or 'unloading' in jt:
            v_norm = (e.vehicle_no or '').strip().upper()
            p_norm = (e.product_name or '').strip().lower()
            key = (e.date, v_norm, p_norm) if v_norm else (e.date, '__direct__', p_norm)
            
            if key not in load_groups:
                load_groups[key] = {
                    'loading': 0.0,
                    'unloading': 0.0,
                    'both': 0.0,
                    'other': 0.0
                }
            
            qty = e.quantity
            if 'both' in jt:
                load_groups[key]['both'] += qty
            elif 'unloading' in jt:
                load_groups[key]['unloading'] += qty
            elif 'loading' in jt:
                load_groups[key]['loading'] += qty
            else:
                load_groups[key]['other'] += qty
        else:
            non_loading_qty += e.quantity

    net_loading_qty = 0.0
    for key, data in load_groups.items():
        net_loading_qty += data['both'] + max(data['loading'], data['unloading']) + data['other']

    return non_loading_qty + net_loading_qty


@bp.route('/job-wages')
@login_required
def job_wages_list():
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')
    from_date_str, to_date_str = resolve_employee_period(period_param, from_date_raw, to_date_raw)

    job_type = request.args.get('job_type')
    product_name = request.args.get('product_name')
    employee_id = request.args.get('employee_id', type=int)

    query = JobWageEntry.query
    
    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
        query = query.filter(JobWageEntry.date >= from_date, JobWageEntry.date <= to_date)
    except ValueError:
        pass

    if job_type:
        query = query.filter(JobWageEntry.job_type == job_type)
    if product_name:
        query = query.filter(JobWageEntry.product_name.ilike(f'%{product_name}%'))
    if employee_id:
        query = query.join(JobWageEntry.allocations).filter(EmployeeJobAllocation.employee_id == employee_id)

    entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    total_amount = sum(e.total_amount for e in entries)
    total_qty = calculate_net_job_quantity(entries)
    
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    groups = EmployeeGroup.query.filter_by(is_active=True).all()

    return render_template('employees/job_wages_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           period=period_param,
                           job_type=job_type,
                           product_name=product_name,
                           employee_id=employee_id,
                           employees=employees,
                           groups=groups,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS,
                           total_amount=total_amount,
                           total_qty=total_qty)


@bp.route('/job-wages/add', methods=['GET', 'POST'])
@login_required
def job_wages_add():
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    groups = EmployeeGroup.query.filter_by(is_active=True).order_by(EmployeeGroup.name).all()
    rates = JobRateSetting.query.filter_by(is_active=True).all()

    # Create rates lookup dictionary for fast client-side JS auto-fill
    rates_map = {}
    for r in rates:
        key = f"{r.product_name}___{r.job_type}"
        rates_map[key] = {
            'rate': r.rate_per_piece,
            'unit': r.unit
        }

    # Group member mapping
    groups_map = {}
    for g in groups:
        groups_map[g.id] = {
            'name': g.name,
            'member_ids': [m.id for m in g.members],
            'default_job': g.default_job_type or '',
            'default_product': g.default_product_name or ''
        }

    if request.method == 'POST':
        try:
            entry_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            group_id = request.form.get('group_id')
            job_type = request.form.get('job_type')
            product_name = request.form.get('product_name')
            quantity = float(request.form.get('quantity') or 0.0)
            unit = request.form.get('unit', 'Pieces / Pcs')
            rate_per_unit = float(request.form.get('rate_per_unit') or 0.0)
            vehicle_no = request.form.get('vehicle_no')
            notes = request.form.get('notes')

            # Selected working employees on this day
            selected_emp_ids = request.form.getlist('employee_ids')
            if not selected_emp_ids:
                flash('Please select at least one employee who worked on this job.', 'error')
                return render_template('employees/job_wage_form.html',
                                       employees=employees,
                                       groups=groups,
                                       rates_map=rates_map,
                                       groups_map=groups_map,
                                       job_types=JOB_TYPES,
                                       job_products=JOB_PRODUCTS,
                                       job_units=JOB_UNITS)

            worker_count = len(selected_emp_ids)
            total_amount = round(quantity * rate_per_unit, 2)
            wage_per_worker = round(total_amount / worker_count, 2) if worker_count > 0 else 0.0

            entry = JobWageEntry(
                date=entry_date,
                group_id=int(group_id) if (group_id and group_id.isdigit()) else None,
                job_type=job_type,
                product_name=product_name,
                quantity=quantity,
                unit=unit,
                rate_per_unit=rate_per_unit,
                total_amount=total_amount,
                worker_count=worker_count,
                wage_per_worker=wage_per_worker,
                vehicle_no=vehicle_no,
                notes=notes
            )
            db.session.add(entry)
            db.session.flush()

            # Allocate equal share to each worker who worked that day
            for emp_id in selected_emp_ids:
                alloc = EmployeeJobAllocation(
                    job_entry_id=entry.id,
                    employee_id=int(emp_id),
                    allocated_wage=wage_per_worker
                )
                db.session.add(alloc)

            db.session.commit()
            flash(f'✅ Job Recorded: ₹{total_amount:,.2f} total divided equally among {worker_count} working employees (₹{wage_per_worker:,.2f} per employee).', 'success')
            return redirect(url_for('employees.job_wages_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error recording job wage: {str(e)}', 'error')

    return render_template('employees/job_wage_form.html',
                           entry=None,
                           employees=employees,
                           groups=groups,
                           rates_map=rates_map,
                           groups_map=groups_map,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS,
                           job_units=JOB_UNITS)


@bp.route('/job-wages/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def job_wages_edit(id):
    entry = JobWageEntry.query.get_or_404(id)
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    groups = EmployeeGroup.query.filter_by(is_active=True).order_by(EmployeeGroup.name).all()
    rates = JobRateSetting.query.filter_by(is_active=True).all()
    assigned_emp_ids = [alloc.employee_id for alloc in entry.allocations]

    rates_map = {f"{r.product_name}___{r.job_type}": {'rate': r.rate_per_piece, 'unit': r.unit} for r in rates}
    groups_map = {g.id: {'name': g.name, 'member_ids': [m.id for m in g.members], 'default_job': g.default_job_type or '', 'default_product': g.default_product_name or ''} for g in groups}

    if request.method == 'POST':
        try:
            entry.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            group_id = request.form.get('group_id')
            entry.group_id = int(group_id) if (group_id and group_id.isdigit()) else None
            entry.job_type = request.form.get('job_type')
            entry.product_name = request.form.get('product_name')
            entry.quantity = float(request.form.get('quantity') or 0.0)
            entry.unit = request.form.get('unit', 'Pieces / Pcs')
            entry.rate_per_unit = float(request.form.get('rate_per_unit') or 0.0)
            entry.vehicle_no = request.form.get('vehicle_no')
            entry.notes = request.form.get('notes')

            selected_emp_ids = request.form.getlist('employee_ids')
            if not selected_emp_ids:
                flash('Please select at least one employee.', 'error')
                return render_template('employees/job_wage_form.html',
                                       entry=entry,
                                       assigned_emp_ids=assigned_emp_ids,
                                       employees=employees,
                                       groups=groups,
                                       rates_map=rates_map,
                                       groups_map=groups_map,
                                       job_types=JOB_TYPES,
                                       job_products=JOB_PRODUCTS,
                                       job_units=JOB_UNITS)

            worker_count = len(selected_emp_ids)
            total_amount = round(entry.quantity * entry.rate_per_unit, 2)
            wage_per_worker = round(total_amount / worker_count, 2) if worker_count > 0 else 0.0

            entry.total_amount = total_amount
            entry.worker_count = worker_count
            entry.wage_per_worker = wage_per_worker

            # Clear old allocations and add updated ones
            EmployeeJobAllocation.query.filter_by(job_entry_id=entry.id).delete()
            for emp_id in selected_emp_ids:
                alloc = EmployeeJobAllocation(
                    job_entry_id=entry.id,
                    employee_id=int(emp_id),
                    allocated_wage=wage_per_worker
                )
                db.session.add(alloc)

            db.session.commit()
            flash(f'✅ Job Updated: ₹{total_amount:,.2f} divided among {worker_count} working employees (₹{wage_per_worker:,.2f} each).', 'success')
            return redirect(url_for('employees.job_wages_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating job: {str(e)}', 'error')

    return render_template('employees/job_wage_form.html',
                           entry=entry,
                           assigned_emp_ids=assigned_emp_ids,
                           employees=employees,
                           groups=groups,
                           rates_map=rates_map,
                           groups_map=groups_map,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS,
                           job_units=JOB_UNITS)


@bp.route('/job-wages/<int:id>/delete', methods=['POST'])
@login_required
def job_wages_delete(id):
    entry = JobWageEntry.query.get_or_404(id)
    try:
        db.session.delete(entry)
        db.session.commit()
        flash('Job wage entry deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting entry: {str(e)}', 'error')
    return redirect(url_for('employees.job_wages_list'))


# ==============================================================================
# SALARY SHEET & EXPORT
# ==============================================================================

@bp.route('/salary-sheet')
@login_required
def salary_sheet():
    """Ultra-fast Bulk Salary Sheet with Weekly and Monthly basis tracking."""
    today = date.today()
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')
    from_date_str, to_date_str = resolve_employee_period(period_param, from_date_raw, to_date_raw)

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date() if from_date_str else today.replace(day=1)
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date() if to_date_str else today
    except ValueError:
        from_date = today.replace(day=1)
        to_date = today

    employees = Employee.query.order_by(Employee.name).all()

    # Bulk query 1: Attendance counts per employee & status
    att_rows = db.session.query(
        Attendance.employee_id,
        Attendance.status,
        func.count(Attendance.id)
    ).filter(Attendance.date >= from_date, Attendance.date <= to_date).group_by(Attendance.employee_id, Attendance.status).all()

    att_map = {}
    for emp_id, st, cnt in att_rows:
        if emp_id not in att_map:
            att_map[emp_id] = {'present': 0, 'half-day': 0, 'absent': 0}
        att_map[emp_id][st] = cnt

    # Bulk query 2: Piece-rate job allocations per employee
    alloc_rows = db.session.query(
        EmployeeJobAllocation.employee_id,
        func.count(EmployeeJobAllocation.id),
        func.sum(EmployeeJobAllocation.allocated_wage)
    ).join(JobWageEntry).filter(JobWageEntry.date >= from_date, JobWageEntry.date <= to_date).group_by(EmployeeJobAllocation.employee_id).all()

    alloc_map = {}
    for emp_id, cnt, total_w in alloc_rows:
        alloc_map[emp_id] = {'count': cnt, 'wage': total_w or 0.0}

    salary_data = []
    grand_piece_wage = 0.0
    grand_attendance_wage = 0.0
    grand_total_salary = 0.0

    for emp in employees:
        e_att = att_map.get(emp.id, {'present': 0, 'half-day': 0, 'absent': 0})
        days_present = e_att.get('present', 0)
        days_half = e_att.get('half-day', 0)
        days_absent = e_att.get('absent', 0)
        attendance_wages = (days_present * emp.daily_wage) + (days_half * emp.daily_wage * 0.5)

        e_alloc = alloc_map.get(emp.id, {'count': 0, 'wage': 0.0})
        job_count = e_alloc.get('count', 0)
        piece_rate_wages = e_alloc.get('wage', 0.0)

        net_salary = attendance_wages + piece_rate_wages

        grand_attendance_wage += attendance_wages
        grand_piece_wage += piece_rate_wages
        grand_total_salary += net_salary

        salary_data.append({
            'employee': emp,
            'days_present': days_present,
            'days_half': days_half,
            'days_absent': days_absent,
            'attendance_wages': attendance_wages,
            'job_count': job_count,
            'piece_rate_wages': piece_rate_wages,
            'net_salary': net_salary
        })

    return render_template('employees/salary_sheet.html',
                           salary_data=salary_data,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           period=period_param,
                           grand_attendance_wage=grand_attendance_wage,
                           grand_piece_wage=grand_piece_wage,
                           grand_total_salary=grand_total_salary)


@bp.route('/salary-sheet/export')
@login_required
def salary_sheet_export():
    today = date.today()
    first_day = today.replace(day=1)
    
    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))

    try:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
    except ValueError:
        from_date = first_day
        to_date = today

    employees = Employee.query.order_by(Employee.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Employee Name', 'Role', 'Present Days', 'Half Days', 'Daily Wage Rate (₹)',
        'Attendance Wages (₹)', 'Job Count', 'Piece-Rate Job Wages (₹)', 'Net Total Salary (₹)'
    ])

    for emp in employees:
        attendances = Attendance.query.filter(
            Attendance.employee_id == emp.id,
            Attendance.date >= from_date,
            Attendance.date <= to_date
        ).all()
        days_present = sum(1 for a in attendances if a.status == 'present')
        days_half = sum(1 for a in attendances if a.status == 'half-day')
        attendance_wages = (days_present * emp.daily_wage) + (days_half * emp.daily_wage * 0.5)

        allocations = EmployeeJobAllocation.query.join(JobWageEntry).filter(
            EmployeeJobAllocation.employee_id == emp.id,
            JobWageEntry.date >= from_date,
            JobWageEntry.date <= to_date
        ).all()
        job_count = len(allocations)
        piece_rate_wages = sum(a.allocated_wage for a in allocations)
        net_salary = attendance_wages + piece_rate_wages

        writer.writerow([
            emp.name, emp.role or '', days_present, days_half, emp.daily_wage,
            f'{attendance_wages:.2f}', job_count, f'{piece_rate_wages:.2f}', f'{net_salary:.2f}'
        ])

    response = Response(output.getvalue(), content_type='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename=employee_salary_sheet_{from_date_str}_to_{to_date_str}.csv"
    return response

@bp.route('/api/check-duplicate-job')
@login_required
def check_duplicate_job():
    """API to check if a production/job entry already exists on the specified date."""
    from flask import jsonify
    date_str = request.args.get('date', '').strip()
    product_name = request.args.get('product_name', '').strip()
    job_type = request.args.get('job_type', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)

    if not date_str or not product_name or not job_type:
        return jsonify({'exists': False})

    try:
        check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'exists': False})

    query = JobWageEntry.query.filter(
        JobWageEntry.date == check_date,
        JobWageEntry.product_name == product_name,
        JobWageEntry.job_type == job_type
    )
    if exclude_id:
        query = query.filter(JobWageEntry.id != exclude_id)

    existing = query.first()
    if existing:
        return jsonify({
            'exists': True,
            'entry': {
                'id': existing.id,
                'date': existing.date.strftime('%d-%b-%Y'),
                'product_name': existing.product_name,
                'job_type': existing.job_type,
                'quantity': existing.quantity,
                'unit': existing.unit,
                'total_amount': existing.total_amount,
                'worker_count': existing.worker_count,
                'edit_url': url_for('employees.job_wages_edit', id=existing.id)
            }
        })

    return jsonify({'exists': False})
