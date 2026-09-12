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
from models import db, Employee, Attendance, JobWageEntry, EmployeeJobAllocation, JobRateSetting, EmployeeGroup, AlertSettings
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

    # Calculate live attendance counters
    present_cnt = sum(1 for a in existing_attendance if a.status == 'present')
    absent_cnt = sum(1 for a in existing_attendance if a.status == 'absent')
    half_day_cnt = sum(1 for a in existing_attendance if a.status == 'half-day')
    unmarked_cnt = max(0, len(employees) - len(existing_attendance))
    
    alert_settings = AlertSettings.query.first()

    groups = EmployeeGroup.query.filter_by(is_active=True).all()
    groups_data = {str(g.id): {'id': g.id, 'name': g.name, 'member_ids': [m.id for m in g.members]} for g in groups}

    return render_template('employees/attendance.html', 
                           employees=employees, 
                           groups=groups,
                           groups_data=groups_data,
                           selected_date=selected_date, 
                           today=date.today(),
                           attendance_map=attendance_map,
                           present_cnt=present_cnt,
                           absent_cnt=absent_cnt,
                           half_day_cnt=half_day_cnt,
                           unmarked_cnt=unmarked_cnt,
                           total_workers=len(employees),
                           alert_settings=alert_settings)


@bp.route('/attendance/send-telegram-reminder', methods=['POST'])
@login_required
def send_telegram_reminder():
    """Manual 1-click trigger to send morning or evening work attendance reminder to Telegram."""
    reminder_type = request.form.get('reminder_type', 'morning')
    date_str = request.form.get('date', '')
    target_date = date.today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    from utils.telegram_service import build_morning_reminder, build_evening_reminder, send_telegram_message

    settings = AlertSettings.query.first()
    bot_token = settings.get_telegram_token() if settings else ''
    chat_id = settings.get_telegram_chat_id() if settings else ''

    if not bot_token or not chat_id:
        flash("Telegram Bot Token or Chat ID is not configured! Please click 'Telegram Settings' to enter your Bot Token and Chat ID.", "error")
        return redirect(url_for('employees.attendance', date=target_date.strftime('%Y-%m-%d')))

    app_base_url = request.host_url.rstrip('/')
    if reminder_type == 'morning':
        msg = build_morning_reminder(app_base_url)
        action_name = "Morning Start Work Reminder"
    else:
        msg = build_evening_reminder(app_base_url, target_date=target_date)
        action_name = "Evening Work Complete Reminder"

    success, res = send_telegram_message(msg, bot_token=bot_token, chat_id=chat_id)
    if success:
        flash(f"⚡ {action_name} sent successfully to Telegram chat/channel!", "success")
    else:
        flash(f"Failed to send Telegram reminder: {res}", "error")

    return redirect(url_for('employees.attendance', date=target_date.strftime('%Y-%m-%d')))


@bp.route('/attendance/telegram-settings', methods=['POST'])
@login_required
def update_telegram_settings():
    """Configure Telegram Bot Token, Chat ID, and Morning (7 AM) & Evening (7 PM) reminder times."""
    settings = AlertSettings.query.first()
    if not settings:
        settings = AlertSettings()
        db.session.add(settings)

    settings.telegram_bot_token = request.form.get('telegram_bot_token', '').strip()
    settings.telegram_chat_id = request.form.get('telegram_chat_id', '').strip()
    settings.telegram_morning_reminder_time = request.form.get('telegram_morning_reminder_time', '07:00').strip()
    settings.telegram_morning_reminder_enabled = request.form.get('telegram_morning_reminder_enabled') == 'on'
    settings.telegram_evening_reminder_time = request.form.get('telegram_evening_reminder_time', '19:00').strip()
    settings.telegram_evening_reminder_enabled = request.form.get('telegram_evening_reminder_enabled') == 'on'

    try:
        db.session.commit()
        flash("Telegram notification and schedule settings updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error saving Telegram settings: {str(e)}", "error")

    redirect_date = request.form.get('redirect_date', '')
    return redirect(url_for('employees.attendance', date=redirect_date) if redirect_date else url_for('employees.attendance'))


@bp.route('/attendance/telegram-test', methods=['POST'])
@login_required
def test_telegram():
    """Send an immediate test message to Telegram."""
    from utils.telegram_service import send_telegram_message
    
    settings = AlertSettings.query.first()
    bot_token = request.form.get('telegram_bot_token', '').strip() or (settings.get_telegram_token() if settings else '')
    chat_id = request.form.get('telegram_chat_id', '').strip() or (settings.get_telegram_chat_id() if settings else '')

    if not bot_token or not chat_id:
        flash("Please enter both Telegram Bot Token and Chat ID to send a test message.", "error")
        return redirect(url_for('employees.attendance'))

    test_msg = (
        "🚀 <b>FlyAsh ERP - Telegram Bot Connection Test</b> 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ <b>Status:</b> Connected & Active!\n"
        f"⏰ <b>Server Time:</b> {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
        "🔔 <b>Automated Attendance Schedule:</b>\n"
        f" • ☀️ Morning Work Start: {settings.telegram_morning_reminder_time if settings else '07:00'} (Daily)\n"
        f" • 🌙 Evening Work Complete: {settings.telegram_evening_reminder_time if settings else '19:00'} (Daily)\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Ready to dispatch daily plant alerts!</i>"
    )
    success, res = send_telegram_message(test_msg, bot_token=bot_token, chat_id=chat_id)
    if success:
        flash("✅ Test message sent successfully to Telegram! Bot is connected.", "success")
    else:
        flash(f"❌ Telegram Test Failed: {res}", "error")

    redirect_date = request.form.get('redirect_date', '')
    return redirect(url_for('employees.attendance', date=redirect_date) if redirect_date else url_for('employees.attendance'))


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
    category = request.args.get('category', 'all')  # 'all', 'production', 'outward'

    query = JobRateSetting.query.filter_by(is_active=True)
    if product:
        query = query.filter(JobRateSetting.product_name.ilike(f'%{product}%'))
    if job_type:
        query = query.filter(JobRateSetting.job_type == job_type)

    all_rates = query.order_by(JobRateSetting.product_name, JobRateSetting.job_type).all()
    
    production_rates = [r for r in all_rates if r.is_production]
    outward_rates = [r for r in all_rates if r.is_outward]
    other_rates = [r for r in all_rates if not r.is_production and not r.is_outward]

    if category == 'production':
        rates = production_rates
    elif category == 'outward':
        rates = outward_rates
    else:
        rates = all_rates

    return render_template('employees/job_rates_list.html',
                           rates=rates,
                           all_rates=all_rates,
                           production_rates=production_rates,
                           outward_rates=outward_rates,
                           other_rates=other_rates,
                           category=category,
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

    category = request.args.get('category', 'all')  # 'all', 'production', 'outward'
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

    all_entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    
    # Categorize entries
    production_entries = [e for e in all_entries if e.is_production]
    outward_entries = [e for e in all_entries if e.is_outward]
    other_entries = [e for e in all_entries if not e.is_production and not e.is_outward]

    if category == 'production':
        entries = production_entries
    elif category == 'outward':
        entries = outward_entries
    else:
        entries = all_entries

    # Production Metrics
    prod_total_amount = sum(e.total_amount for e in production_entries)
    prod_gross_qty = sum((e.gross_quantity if (e.gross_quantity and e.gross_quantity > 0) else (e.tray_count * (e.pieces_per_tray or 105.0) if e.tray_count else e.quantity)) for e in production_entries)
    prod_net_qty = sum(e.quantity for e in production_entries)
    prod_total_trays = sum((e.tray_count or 0.0) for e in production_entries)
    prod_total_wastage = sum((e.total_wastage or 0.0) for e in production_entries)
    prod_wastage_amount = sum(e.calculated_wastage_amount for e in production_entries)

    # Outward / Loading Metrics
    outward_total_amount = sum(e.total_amount for e in outward_entries)
    outward_net_qty = calculate_net_job_quantity(outward_entries)
    outward_vehicle_count = len(set((e.date, (e.vehicle_no or '').strip().upper()) for e in outward_entries if e.vehicle_no))

    # Overall Totals
    total_amount = sum(e.total_amount for e in all_entries)
    total_qty = calculate_net_job_quantity(all_entries)
    
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()
    groups = EmployeeGroup.query.filter_by(is_active=True).all()

    return render_template('employees/job_wages_list.html',
                           entries=entries,
                           all_entries=all_entries,
                           production_entries=production_entries,
                           outward_entries=outward_entries,
                           other_entries=other_entries,
                           category=category,
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
                           total_qty=total_qty,
                           prod_total_amount=prod_total_amount,
                           prod_gross_qty=prod_gross_qty,
                           prod_net_qty=prod_net_qty,
                           prod_total_trays=prod_total_trays,
                           prod_total_wastage=prod_total_wastage,
                           prod_wastage_amount=prod_wastage_amount,
                           outward_total_amount=outward_total_amount,
                           outward_net_qty=outward_net_qty,
                           outward_vehicle_count=outward_vehicle_count)


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
            'pieces_per_tray': r.pieces_per_tray or (105.0 if 'Brick' in r.product_name else 60.0),
            'wastage_per_tray': r.wastage_per_tray if r.wastage_per_tray is not None else (5.0 if 'Brick' in r.product_name else 3.0),
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
            
            # Tray & Wastage fields
            tray_count = float(request.form.get('tray_count') or 0.0)
            pieces_per_tray = float(request.form.get('pieces_per_tray') or 105.0)
            wastage_per_tray = float(request.form.get('wastage_per_tray') or 5.0)
            gross_quantity = float(request.form.get('gross_quantity') or 0.0)
            total_wastage = float(request.form.get('total_wastage') or 0.0)
            quantity = float(request.form.get('quantity') or 0.0)

            if tray_count > 0:
                if gross_quantity <= 0:
                    gross_quantity = round(tray_count * pieces_per_tray, 2)
                if total_wastage <= 0:
                    total_wastage = round(tray_count * wastage_per_tray, 2)
                if quantity <= 0:
                    quantity = round(max(0, gross_quantity - total_wastage), 2)
            else:
                if gross_quantity <= 0:
                    gross_quantity = quantity

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
            gross_amount = round(gross_quantity * rate_per_unit, 2)
            wastage_amount = round(total_wastage * rate_per_unit, 2)
            total_amount = round(quantity * rate_per_unit, 2)
            wage_per_worker = round(total_amount / worker_count, 2) if worker_count > 0 else 0.0

            entry = JobWageEntry(
                date=entry_date,
                group_id=int(group_id) if (group_id and group_id.isdigit()) else None,
                job_type=job_type,
                product_name=product_name,
                tray_count=tray_count,
                pieces_per_tray=pieces_per_tray,
                wastage_per_tray=wastage_per_tray,
                total_wastage=total_wastage,
                gross_quantity=gross_quantity,
                quantity=quantity,
                unit=unit,
                rate_per_unit=rate_per_unit,
                gross_amount=gross_amount,
                wastage_amount=wastage_amount,
                total_amount=total_amount,
                worker_count=worker_count,
                wage_per_worker=wage_per_worker,
                vehicle_no=vehicle_no,
                notes=notes
            )
            db.session.add(entry)
            db.session.flush()

            # Allocate equal share and automatically grant FULL ATTENDANCE (Present) for all working workers
            for emp_id in selected_emp_ids:
                alloc = EmployeeJobAllocation(
                    job_entry_id=entry.id,
                    employee_id=int(emp_id),
                    allocated_wage=wage_per_worker
                )
                db.session.add(alloc)

                # Auto-mark Full Day Attendance (Present) for working workers on this day
                att = Attendance.query.filter_by(employee_id=int(emp_id), date=entry_date).first()
                if att:
                    att.status = 'present'
                    if not att.notes:
                        att.notes = f'Full day attendance auto-marked via {job_type}'
                else:
                    att = Attendance(
                        employee_id=int(emp_id),
                        date=entry_date,
                        status='present',
                        notes=f'Full day attendance auto-marked via {job_type}'
                    )
                    db.session.add(att)

            db.session.commit()
            if tray_count > 0:
                flash(f'✅ Production Recorded: {tray_count:g} Trays = {gross_quantity:,.0f} Bricks added to Stock. Deducted {total_wastage:,.0f} wastage -> Salary calculated for {quantity:,.0f} Bricks (₹{total_amount:,.2f} total, ₹{wage_per_worker:,.2f}/worker).', 'success')
            else:
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

    rates_map = {
        f"{r.product_name}___{r.job_type}": {
            'rate': r.rate_per_piece,
            'pieces_per_tray': r.pieces_per_tray or (105.0 if 'Brick' in r.product_name else 60.0),
            'wastage_per_tray': r.wastage_per_tray if r.wastage_per_tray is not None else (5.0 if 'Brick' in r.product_name else 3.0),
            'unit': r.unit
        } for r in rates
    }
    groups_map = {g.id: {'name': g.name, 'member_ids': [m.id for m in g.members], 'default_job': g.default_job_type or '', 'default_product': g.default_product_name or ''} for g in groups}

    if request.method == 'POST':
        try:
            entry.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            group_id = request.form.get('group_id')
            entry.group_id = int(group_id) if (group_id and group_id.isdigit()) else None
            entry.job_type = request.form.get('job_type')
            entry.product_name = request.form.get('product_name')
            
            entry.tray_count = float(request.form.get('tray_count') or 0.0)
            entry.pieces_per_tray = float(request.form.get('pieces_per_tray') or 105.0)
            entry.wastage_per_tray = float(request.form.get('wastage_per_tray') or 5.0)
            entry.gross_quantity = float(request.form.get('gross_quantity') or 0.0)
            entry.total_wastage = float(request.form.get('total_wastage') or 0.0)
            entry.quantity = float(request.form.get('quantity') or 0.0)

            if entry.tray_count > 0:
                if entry.gross_quantity <= 0:
                    entry.gross_quantity = round(entry.tray_count * entry.pieces_per_tray, 2)
                if entry.total_wastage <= 0:
                    entry.total_wastage = round(entry.tray_count * entry.wastage_per_tray, 2)
                if entry.quantity <= 0:
                    entry.quantity = round(max(0, entry.gross_quantity - entry.total_wastage), 2)
            else:
                if entry.gross_quantity <= 0:
                    entry.gross_quantity = entry.quantity

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
            gross_amount = round(entry.gross_quantity * entry.rate_per_unit, 2)
            wastage_amount = round(entry.total_wastage * entry.rate_per_unit, 2)
            total_amount = round(entry.quantity * entry.rate_per_unit, 2)
            wage_per_worker = round(total_amount / worker_count, 2) if worker_count > 0 else 0.0

            entry.gross_amount = gross_amount
            entry.wastage_amount = wastage_amount
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
    """Ultra-fast Bulk Salary Sheet with separate Production & Loading/Unloading Wage and Volume tracking."""
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

    # Bulk query 2: All piece-rate job allocations with JobWageEntry details
    alloc_rows = db.session.query(
        EmployeeJobAllocation.employee_id,
        EmployeeJobAllocation.allocated_wage,
        JobWageEntry.job_type,
        JobWageEntry.quantity,
        JobWageEntry.gross_quantity,
        JobWageEntry.tray_count,
        JobWageEntry.vehicle_no
    ).join(JobWageEntry, EmployeeJobAllocation.job_entry_id == JobWageEntry.id)\
     .filter(JobWageEntry.date >= from_date, JobWageEntry.date <= to_date).all()

    emp_prod_map = {}
    emp_load_map = {}

    for emp_id, alloc_wage, jt, qty, gross_qty, tray_cnt, veh_no in alloc_rows:
        jt_clean = (jt or '').lower()
        is_prod = 'production' in jt_clean or (tray_cnt is not None and tray_cnt > 0)
        
        vol = (gross_qty if (gross_qty and gross_qty > 0) else qty) or 0.0

        if is_prod:
            if emp_id not in emp_prod_map:
                emp_prod_map[emp_id] = {'jobs': 0, 'wage': 0.0, 'volume': 0.0}
            emp_prod_map[emp_id]['jobs'] += 1
            emp_prod_map[emp_id]['wage'] += (alloc_wage or 0.0)
            emp_prod_map[emp_id]['volume'] += vol
        else:
            if emp_id not in emp_load_map:
                emp_load_map[emp_id] = {'jobs': 0, 'wage': 0.0, 'volume': 0.0}
            emp_load_map[emp_id]['jobs'] += 1
            emp_load_map[emp_id]['wage'] += (alloc_wage or 0.0)
            emp_load_map[emp_id]['volume'] += (qty or 0.0)

    salary_data = []
    grand_prod_wage = 0.0
    grand_prod_volume = 0.0
    grand_prod_jobs = 0
    grand_load_wage = 0.0
    grand_load_volume = 0.0
    grand_load_jobs = 0
    grand_attendance_wage = 0.0
    grand_total_salary = 0.0

    for emp in employees:
        e_att = att_map.get(emp.id, {'present': 0, 'half-day': 0, 'absent': 0})
        days_present = e_att.get('present', 0)
        days_half = e_att.get('half-day', 0)
        days_absent = e_att.get('absent', 0)
        attendance_wages = (days_present * emp.daily_wage) + (days_half * emp.daily_wage * 0.5)

        p_info = emp_prod_map.get(emp.id, {'jobs': 0, 'wage': 0.0, 'volume': 0.0})
        l_info = emp_load_map.get(emp.id, {'jobs': 0, 'wage': 0.0, 'volume': 0.0})

        prod_jobs = p_info['jobs']
        prod_wage = p_info['wage']
        prod_volume = p_info['volume']

        load_jobs = l_info['jobs']
        load_wage = l_info['wage']
        load_volume = l_info['volume']

        net_salary = attendance_wages + prod_wage + load_wage

        grand_attendance_wage += attendance_wages
        grand_prod_wage += prod_wage
        grand_prod_volume += prod_volume
        grand_prod_jobs += prod_jobs
        grand_load_wage += load_wage
        grand_load_volume += load_volume
        grand_load_jobs += load_jobs
        grand_total_salary += net_salary

        salary_data.append({
            'employee': emp,
            'days_present': days_present,
            'days_half': days_half,
            'days_absent': days_absent,
            'attendance_wages': attendance_wages,
            'prod_jobs': prod_jobs,
            'prod_volume': prod_volume,
            'prod_wage': prod_wage,
            'load_jobs': load_jobs,
            'load_volume': load_volume,
            'load_wage': load_wage,
            'piece_rate_wages': prod_wage + load_wage,
            'net_salary': net_salary
        })

    return render_template('employees/salary_sheet.html',
                           salary_data=salary_data,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           period=period_param,
                           grand_attendance_wage=grand_attendance_wage,
                           grand_prod_wage=grand_prod_wage,
                           grand_prod_volume=grand_prod_volume,
                           grand_prod_jobs=grand_prod_jobs,
                           grand_load_wage=grand_load_wage,
                           grand_load_volume=grand_load_volume,
                           grand_load_jobs=grand_load_jobs,
                           grand_piece_wage=grand_prod_wage + grand_load_wage,
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
        'Attendance Wages (₹)', 
        'Production Jobs', 'Production Volume (Pcs)', 'Production Wage (₹)', 
        'Loading/Unloading Jobs', 'Loading Volume (Pcs)', 'Loading/Unloading Wage (₹)', 
        'Net Total Salary (₹)'
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

        prod_allocs = [a for a in allocations if a.job_entry.is_production]
        load_allocs = [a for a in allocations if a.job_entry.is_outward]

        prod_jobs = len(prod_allocs)
        prod_volume = sum((a.job_entry.gross_quantity if (a.job_entry.gross_quantity and a.job_entry.gross_quantity > 0) else a.job_entry.quantity) for a in prod_allocs)
        prod_wage = sum(a.allocated_wage for a in prod_allocs)

        load_jobs = len(load_allocs)
        load_volume = sum(a.job_entry.quantity for a in load_allocs)
        load_wage = sum(a.allocated_wage for a in load_allocs)

        net_salary = attendance_wages + prod_wage + load_wage

        writer.writerow([
            emp.name, emp.role or '', days_present, days_half, emp.daily_wage,
            f'{attendance_wages:.2f}', 
            prod_jobs, f'{prod_volume:,.0f}', f'{prod_wage:.2f}',
            load_jobs, f'{load_volume:,.0f}', f'{load_wage:.2f}',
            f'{net_salary:.2f}'
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



# ==============================================================================
# TELEGRAM BOT WEBHOOK & QUICK ATTENDANCE ACTIONS
# ==============================================================================

@bp.route('/attendance/mark-all-present', methods=['POST'])
@login_required
def mark_all_present():
    """Quick 1-click endpoint to mark all active employees as Present for a selected date."""
    date_str = request.form.get('date', '')
    target_date = date.today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    employees = Employee.query.filter_by(is_active=True).all()
    count = 0
    try:
        for emp in employees:
            att = Attendance.query.filter_by(employee_id=emp.id, date=target_date).first()
            if att:
                att.status = 'present'
            else:
                att = Attendance(
                    employee_id=emp.id,
                    date=target_date,
                    status='present',
                    notes='Marked present via Quick Attendance'
                )
                db.session.add(att)
            count += 1
        db.session.commit()
        flash(f"✅ Successfully marked all {count} active workers as PRESENT for {target_date.strftime('%d %b %Y')}!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error marking all present: {str(e)}", "error")

    return redirect(url_for('employees.attendance', date=target_date.strftime('%Y-%m-%d')))


@bp.route('/telegram-webhook', methods=['POST', 'GET'])
def telegram_webhook():
    """Public webhook endpoint to receive interactive commands directly from Telegram bot."""
    if request.method == 'GET':
        return jsonify({
            'status': 'ok',
            'message': 'FlyAsh Telegram Webhook is active and listening for 7 AM / 7 PM commands.'
        })

    try:
        data = request.get_json(force=True, silent=True)
        if not data:
            return jsonify({'ok': True, 'msg': 'No JSON payload'})

        # Telegram Message object
        msg_obj = data.get('message') or data.get('edited_message') or data.get('channel_post')
        if not msg_obj:
            return jsonify({'ok': True, 'msg': 'No message field'})

        chat = msg_obj.get('chat', {})
        chat_id = str(chat.get('id', ''))
        text = msg_obj.get('text', '').strip()

        if text and chat_id:
            from utils.telegram_service import handle_telegram_command
            host_url = request.host_url.rstrip('/')
            handle_telegram_command(text, chat_id, host_url=host_url)

        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 200


@bp.route('/groups/<int:id>/mark-attendance', methods=['POST'])
@login_required
def mark_group_attendance(id):
    """1-Click mark all active members of a labor group/gang as FULL PRESENT for the date."""
    group = EmployeeGroup.query.get_or_404(id)
    date_str = request.form.get('date', '')
    target_date = date.today()
    if date_str:
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    count = 0
    for emp in group.members:
        if emp.is_active:
            att = Attendance.query.filter_by(employee_id=emp.id, date=target_date).first()
            if att:
                att.status = 'present'
            else:
                att = Attendance(
                    employee_id=emp.id,
                    date=target_date,
                    status='present',
                    notes=f'Full day attendance auto-marked for group: {group.name}'
                )
                db.session.add(att)
            count += 1

    try:
        db.session.commit()
        flash(f"✅ Marked FULL ATTENDANCE (Present) for all {count} workers in '{group.name}' on {target_date.strftime('%d %b %Y')}! (No half/absent).", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error marking group attendance: {str(e)}", "error")

    redirect_url = request.form.get('redirect_to') or request.referrer or url_for('employees.attendance', date=target_date.strftime('%Y-%m-%d'))
    return redirect(redirect_url)
