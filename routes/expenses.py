import csv
import io
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from models import db, Expense

bp = Blueprint('expenses', __name__, url_prefix='/expenses')

EXPENSE_CATEGORIES = [
    'Diesel / Fuel',
    'Electricity & Power',
    'Machine & Vehicle Repairs',
    'Plant Maintenance & Spares',
    'Freight & Transportation',
    'Oil & Lubricants',
    'Site Rent & Taxes',
    'Office & Tea / Food',
    'Labor Contractor',
    'Miscellaneous Expense'
]

PAYMENT_MODES = ['Cash', 'UPI', 'Bank Transfer', 'Cheque']


@bp.route('/')
@login_required
def list_expenses():
    category = request.args.get('category', '').strip()
    payment_mode = request.args.get('payment_mode', '').strip()
    search = request.args.get('search', '').strip()
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()
    date_preset = request.args.get('preset', '').strip()

    today = date.today()
    if date_preset == 'today':
        from_date = today.strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    elif date_preset == 'this_week':
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        from_date = mon.strftime('%Y-%m-%d')
        to_date = sun.strftime('%Y-%m-%d')
    elif date_preset == 'last_week':
        last_mon = today - timedelta(days=today.weekday() + 7)
        last_sun = last_mon + timedelta(days=6)
        from_date = last_mon.strftime('%Y-%m-%d')
        to_date = last_sun.strftime('%Y-%m-%d')
    elif date_preset == 'this_month' or (not from_date and not to_date and not date_preset and False):
        from_date = today.replace(day=1).strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')
    elif date_preset == 'last_month':
        first_this = today.replace(day=1)
        prev_month_last = first_this - timedelta(days=1)
        prev_month_first = prev_month_last.replace(day=1)
        from_date = prev_month_first.strftime('%Y-%m-%d')
        to_date = prev_month_last.strftime('%Y-%m-%d')
    elif date_preset == 'this_year':
        from_date = f"{today.year}-01-01"
        to_date = f"{today.year}-12-31"
    elif date_preset == 'all':
        from_date = ''
        to_date = ''
    elif not from_date and not to_date and not date_preset:
        from_date = today.replace(day=1).strftime('%Y-%m-%d')
        to_date = today.strftime('%Y-%m-%d')

    query = Expense.query

    if category:
        query = query.filter(Expense.category == category)
    if payment_mode:
        query = query.filter(Expense.payment_mode.ilike(payment_mode))
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (Expense.title.ilike(search_fmt)) |
            (Expense.paid_to.ilike(search_fmt)) |
            (Expense.reference_no.ilike(search_fmt)) |
            (Expense.notes.ilike(search_fmt))
        )
    if from_date:
        try:
            f_d = datetime.strptime(from_date, '%Y-%m-%d').date()
            query = query.filter(Expense.date >= f_d)
        except ValueError:
            pass
    if to_date:
        try:
            t_d = datetime.strptime(to_date, '%Y-%m-%d').date()
            query = query.filter(Expense.date <= t_d)
        except ValueError:
            pass

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    total_amount = sum(e.amount for e in expenses)

    category_totals = {}
    for e in expenses:
        category_totals[e.category] = category_totals.get(e.category, 0.0) + e.amount

    first_of_month = today.replace(day=1)
    month_expenses = db.session.query(db.func.sum(Expense.amount)).filter(Expense.date >= first_of_month, Expense.date <= today).scalar() or 0.0
    today_expenses = db.session.query(db.func.sum(Expense.amount)).filter(Expense.date == today).scalar() or 0.0

    return render_template(
        'expenses/list.html',
        expenses=expenses,
        total_amount=total_amount,
        category_totals=category_totals,
        month_expenses=month_expenses,
        today_expenses=today_expenses,
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        selected_category=category,
        selected_mode=payment_mode,
        selected_search=search,
        from_date=from_date,
        to_date=to_date,
        date_preset=date_preset
    )


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_expense():
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()
        custom_category = request.form.get('custom_category', '').strip()
        title = request.form.get('title', '').strip()
        amount_str = request.form.get('amount', '0').strip()
        payment_mode = request.form.get('payment_mode', 'Cash').strip()
        paid_to = request.form.get('paid_to', '').strip()
        reference_no = request.form.get('reference_no', '').strip()
        notes = request.form.get('notes', '').strip()

        if category == 'Other' and custom_category:
            category = custom_category

        if not title:
            flash('Expense title/purpose is required.', 'danger')
            return redirect(url_for('expenses.add_expense'))

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            flash('Please enter a valid expense amount greater than 0.', 'danger')
            return redirect(url_for('expenses.add_expense'))

        try:
            exp_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
        except ValueError:
            exp_date = date.today()

        expense = Expense(
            date=exp_date,
            category=category or 'Miscellaneous Expense',
            title=title,
            amount=amount,
            payment_mode=payment_mode,
            paid_to=paid_to,
            reference_no=reference_no,
            notes=notes
        )
        db.session.add(expense)
        db.session.commit()
        flash(f'Expense ₹{amount:,.2f} recorded successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))

    return render_template(
        'expenses/form.html',
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        today=date.today().strftime('%Y-%m-%d'),
        expense=None
    )


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_expense(id):
    expense = Expense.query.get_or_404(id)
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        category = request.form.get('category', '').strip()
        custom_category = request.form.get('custom_category', '').strip()
        title = request.form.get('title', '').strip()
        amount_str = request.form.get('amount', '0').strip()
        payment_mode = request.form.get('payment_mode', 'Cash').strip()
        paid_to = request.form.get('paid_to', '').strip()
        reference_no = request.form.get('reference_no', '').strip()
        notes = request.form.get('notes', '').strip()

        if category == 'Other' and custom_category:
            category = custom_category

        if not title:
            flash('Expense title/purpose is required.', 'danger')
            return redirect(url_for('expenses.edit_expense', id=id))

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            flash('Please enter a valid expense amount greater than 0.', 'danger')
            return redirect(url_for('expenses.edit_expense', id=id))

        try:
            expense.date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else expense.date
        except ValueError:
            pass

        expense.category = category or expense.category
        expense.title = title
        expense.amount = amount
        expense.payment_mode = payment_mode
        expense.paid_to = paid_to
        expense.reference_no = reference_no
        expense.notes = notes

        db.session.commit()
        flash('Expense updated successfully!', 'success')
        return redirect(url_for('expenses.list_expenses'))

    return render_template(
        'expenses/form.html',
        categories=EXPENSE_CATEGORIES,
        payment_modes=PAYMENT_MODES,
        today=date.today().strftime('%Y-%m-%d'),
        expense=expense
    )


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_expense(id):
    expense = Expense.query.get_or_404(id)
    amount = expense.amount
    title = expense.title
    db.session.delete(expense)
    db.session.commit()
    flash(f'Expense "{title}" (₹{amount:,.2f}) deleted.', 'info')
    return redirect(url_for('expenses.list_expenses'))


@bp.route('/export')
@login_required
def export_csv():
    category = request.args.get('category', '').strip()
    payment_mode = request.args.get('payment_mode', '').strip()
    search = request.args.get('search', '').strip()
    from_date = request.args.get('from_date', '').strip()
    to_date = request.args.get('to_date', '').strip()

    query = Expense.query
    if category:
        query = query.filter(Expense.category == category)
    if payment_mode:
        query = query.filter(Expense.payment_mode.ilike(payment_mode))
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (Expense.title.ilike(search_fmt)) |
            (Expense.paid_to.ilike(search_fmt)) |
            (Expense.reference_no.ilike(search_fmt))
        )
    if from_date:
        try:
            f_d = datetime.strptime(from_date, '%Y-%m-%d').date()
            query = query.filter(Expense.date >= f_d)
        except ValueError:
            pass
    if to_date:
        try:
            t_d = datetime.strptime(to_date, '%Y-%m-%d').date()
            query = query.filter(Expense.date <= t_d)
        except ValueError:
            pass

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Date', 'Category', 'Title / Description', 'Amount (INR)', 'Payment Mode', 'Paid To', 'Reference / Bill No', 'Notes'])

    for e in expenses:
        writer.writerow([
            e.id,
            e.date.strftime('%Y-%m-%d'),
            e.category,
            e.title,
            f'{e.amount:.2f}',
            e.payment_mode,
            e.paid_to or '',
            e.reference_no or '',
            e.notes or ''
        ])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=plant_expenses_{date.today().strftime("%Y%m%d")}.csv'
    return response
