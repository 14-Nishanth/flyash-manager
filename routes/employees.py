import io
import csv
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from models import db, Employee, Attendance, JobWageEntry, EmployeeJobAllocation
from datetime import datetime, date
from sqlalchemy import func

bp = Blueprint('employees', __name__, url_prefix='/employees')

JOB_TYPES = [
    'Production (Per Piece)',
    'Loading Only',
    'Both Loading & Unloading',
    'Unloading Only',
    'Stacking & Curing',
    'Raw Material Shifting',
    'General Work / Maintenance'
]

JOB_PRODUCTS = [
    'Hollow Block 4" (400 x 200 x 100 mm)',
    'Hollow Block 6" (400 x 200 x 150 mm)',
    'Hollow Block 8" (400 x 200 x 200 mm)',
    'Hollow Block 9" (400 x 200 x 225 mm)',
    'Hollow Block 12" (400 x 200 x 300 mm)',
    'Solid Block 4"',
    'Solid Block 6"',
    'Solid Block 8"',
    'Fly Ash Brick 9"x4"x3" (Standard)',
    'Fly Ash Brick Modular (190 x 90 x 90 mm)',
    'Fly Ash Brick Non-Modular',
    'Heavy Duty Fly Ash Brick',
    'Fly Ash Paver Blocks',
    'Fly Ash (Bulker / Loose)',
    'Cement Bags',
    'Stone Dust / Cooldust',
    'Other Work'
]

JOB_UNITS = ['Pieces / Pcs', 'Nos (Numbers)', 'Bags', 'Ton', 'Load', 'Trip', 'Trolley', 'Brass', 'Hours', 'Day']


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
        flash('Error deleting employee. They may have related records.', 'error')
    return redirect(url_for('employees.list_employees'))


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
    
    # Get existing attendance for this date
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
    
    # Calculate summary if filtered
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
# PIECE-RATE JOB WAGES & SALARY DISTRIBUTION SYSTEM
# ==============================================================================

@bp.route('/job-wages')
@login_required
def job_wages_list():
    today = date.today()
    first_day = today.replace(day=1)
    
    from_date_str = request.args.get('from_date', first_day.strftime('%Y-%m-%d'))
    to_date_str = request.args.get('to_date', today.strftime('%Y-%m-%d'))
    job_type = request.args.get('job_type')
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

    if employee_id:
        query = query.join(JobWageEntry.allocations).filter(EmployeeJobAllocation.employee_id == employee_id)

    entries = query.order_by(JobWageEntry.date.desc(), JobWageEntry.id.desc()).all()
    total_amount = sum(e.total_amount for e in entries)
    total_qty = sum(e.quantity for e in entries)
    
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    return render_template('employees/job_wages_list.html',
                           entries=entries,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           job_type=job_type,
                           employee_id=employee_id,
                           employees=employees,
                           job_types=JOB_TYPES,
                           total_amount=total_amount,
                           total_qty=total_qty)


@bp.route('/job-wages/add', methods=['GET', 'POST'])
@login_required
def job_wages_add():
    employees = Employee.query.filter_by(is_active=True).order_by(Employee.name).all()

    if request.method == 'POST':
        try:
            entry_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
            job_type = request.form.get('job_type')
            product_name = request.form.get('product_name')
            quantity = float(request.form.get('quantity') or 0.0)
            unit = request.form.get('unit', 'Pieces / Pcs')
            rate_per_unit = float(request.form.get('rate_per_unit') or 0.0)
            vehicle_no = request.form.get('vehicle_no')
            notes = request.form.get('notes')

            # Selected employees
            selected_emp_ids = request.form.getlist('employee_ids')
            if not selected_emp_ids:
                flash('Please select at least one employee who worked on this job.', 'error')
                return render_template('employees/job_wage_form.html',
                                       employees=employees,
                                       job_types=JOB_TYPES,
                                       job_products=JOB_PRODUCTS,
                                       job_units=JOB_UNITS)

            worker_count = len(selected_emp_ids)
            total_amount = round(quantity * rate_per_unit, 2)
            wage_per_worker = round(total_amount / worker_count, 2) if worker_count > 0 else 0.0

            entry = JobWageEntry(
                date=entry_date,
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
            db.session.flush()  # get entry.id

            # Allocate wage share to each assigned employee
            for emp_id in selected_emp_ids:
                alloc = EmployeeJobAllocation(
                    job_entry_id=entry.id,
                    employee_id=int(emp_id),
                    allocated_wage=wage_per_worker
                )
                db.session.add(alloc)

            db.session.commit()
            flash(f'Job recorded successfully! ₹{total_amount:,.2f} divided among {worker_count} workers (₹{wage_per_worker:,.2f} each).', 'success')
            return redirect(url_for('employees.job_wages_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error recording job wage: {str(e)}', 'error')

    return render_template('employees/job_wage_form.html',
                           employees=employees,
                           job_types=JOB_TYPES,
                           job_products=JOB_PRODUCTS,
                           job_units=JOB_UNITS)


@bp.route('/job-wages/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def job_wages_edit(id):
    entry = JobWageEntry.query.get_or_404(id)
    employees = Employee.query.order_by(Employee.name).all()
    assigned_emp_ids = [alloc.employee_id for alloc in entry.allocations]

    if request.method == 'POST':
        try:
            entry.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
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
            flash(f'Job updated! ₹{total_amount:,.2f} divided among {worker_count} workers (₹{wage_per_worker:,.2f} each).', 'success')
            return redirect(url_for('employees.job_wages_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating job: {str(e)}', 'error')

    return render_template('employees/job_wage_form.html',
                           entry=entry,
                           assigned_emp_ids=assigned_emp_ids,
                           employees=employees,
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


@bp.route('/salary-sheet')
@login_required
def salary_sheet():
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
    salary_data = []

    grand_piece_wage = 0.0
    grand_attendance_wage = 0.0
    grand_total_salary = 0.0

    for emp in employees:
        # Attendance calculation
        attendances = Attendance.query.filter(
            Attendance.employee_id == emp.id,
            Attendance.date >= from_date,
            Attendance.date <= to_date
        ).all()

        days_present = sum(1 for a in attendances if a.status == 'present')
        days_half = sum(1 for a in attendances if a.status == 'half-day')
        days_absent = sum(1 for a in attendances if a.status == 'absent')
        attendance_wages = (days_present * emp.daily_wage) + (days_half * emp.daily_wage * 0.5)

        # Piece-rate job allocations
        allocations = EmployeeJobAllocation.query.join(JobWageEntry).filter(
            EmployeeJobAllocation.employee_id == emp.id,
            JobWageEntry.date >= from_date,
            JobWageEntry.date <= to_date
        ).all()

        job_count = len(allocations)
        piece_rate_wages = sum(a.allocated_wage for a in allocations)

        # Net Salary
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
