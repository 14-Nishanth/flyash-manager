import io
import csv
import urllib.parse
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from models import db, Party, MaterialInward, MaterialOutward, Payment

bp = Blueprint('parties', __name__, url_prefix='/parties')


def generate_whatsapp_url(party, outstanding):
    if not party.phone:
        return None
    
    clean_phone = ''.join(filter(str.isdigit, party.phone))
    if len(clean_phone) == 10:
        clean_phone = '91' + clean_phone
    elif len(clean_phone) > 10 and not clean_phone.startswith('91') and len(clean_phone) == 12:
        clean_phone = clean_phone
    elif len(clean_phone) < 10:
        return None

    if outstanding > 0:
        msg = f"Namaste {party.name} ji,\n\nThis is a gentle payment reminder from *FlyAsh Plant*. Your current outstanding balance is *₹{outstanding:,.2f}* (Debit).\n\nKindly arrange the settlement at your earliest convenience.\nThank you for your business!"
    elif outstanding < 0:
        msg = f"Namaste {party.name} ji,\n\nThis is a status update from *FlyAsh Plant*. Our ledger reflects a balance of *₹{abs(outstanding):,.2f}* payable to you.\n\nThank you!"
    else:
        msg = f"Namaste {party.name} ji, Your account balance with FlyAsh Plant is clear (₹0.00). Thank you!"

    encoded_msg = urllib.parse.quote(msg)
    return f"https://wa.me/{clean_phone}?text={encoded_msg}"


@bp.route('/')
@login_required
def list_parties():
    party_type = request.args.get('type', 'all')
    search = request.args.get('search', '').strip()
    
    query = Party.query
    if party_type != 'all':
        query = query.filter_by(party_type=party_type)
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (Party.name.ilike(search_fmt)) |
            (Party.phone.ilike(search_fmt)) |
            (Party.gstin.ilike(search_fmt))
        )
    
    parties = query.order_by(Party.name).all()
    
    total_receivable = 0.0
    total_payable = 0.0
    
    for party in parties:
        party.outstanding = party.get_outstanding()
        if party.outstanding > 0:
            total_receivable += party.outstanding
        else:
            total_payable += abs(party.outstanding)
            
    return render_template('parties/list.html', 
                           parties=parties, 
                           party_type=party_type,
                           search=search,
                           total_receivable=total_receivable,
                           total_payable=total_payable)


@bp.route('/outstanding')
@login_required
def party_outstanding():
    """Party-wise outstanding balance tracking with WhatsApp reminders."""
    filter_type = request.args.get('filter', 'all')  # all, receivable, payable, zero
    party_type = request.args.get('party_type', 'all')  # all, supplier, customer, both
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort', 'highest_due')  # highest_due, lowest_due, name_asc, name_desc

    query = Party.query
    if party_type != 'all':
        query = query.filter_by(party_type=party_type)
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (Party.name.ilike(search_fmt)) |
            (Party.phone.ilike(search_fmt)) |
            (Party.gstin.ilike(search_fmt))
        )

    all_parties = query.all()

    total_receivable = 0.0
    total_payable = 0.0
    receivable_count = 0
    payable_count = 0
    zero_count = 0

    processed_parties = []
    for p in all_parties:
        bal = p.get_outstanding()
        p.outstanding = bal
        p.wa_link = generate_whatsapp_url(p, bal)
        
        if bal > 0.01:
            total_receivable += bal
            receivable_count += 1
        elif bal < -0.01:
            total_payable += abs(bal)
            payable_count += 1
        else:
            zero_count += 1

        # Apply dues filter
        if filter_type == 'receivable' and bal <= 0.01:
            continue
        elif filter_type == 'payable' and bal >= -0.01:
            continue
        elif filter_type == 'zero' and abs(bal) > 0.01:
            continue

        processed_parties.append(p)

    # Sorting
    if sort_by == 'highest_due':
        processed_parties.sort(key=lambda x: x.outstanding, reverse=True)
    elif sort_by == 'lowest_due':
        processed_parties.sort(key=lambda x: x.outstanding)
    elif sort_by == 'name_desc':
        processed_parties.sort(key=lambda x: x.name.lower(), reverse=True)
    else:  # name_asc
        processed_parties.sort(key=lambda x: x.name.lower())

    net_balance = total_receivable - total_payable

    return render_template(
        'parties/outstanding.html',
        parties=processed_parties,
        filter_type=filter_type,
        party_type=party_type,
        search=search,
        sort_by=sort_by,
        total_receivable=total_receivable,
        total_payable=total_payable,
        net_balance=net_balance,
        receivable_count=receivable_count,
        payable_count=payable_count,
        zero_count=zero_count,
        total_count=len(all_parties)
    )


@bp.route('/outstanding/export')
@login_required
def export_outstanding_csv():
    filter_type = request.args.get('filter', 'all')
    party_type = request.args.get('party_type', 'all')
    search = request.args.get('search', '').strip()

    query = Party.query
    if party_type != 'all':
        query = query.filter_by(party_type=party_type)
    if search:
        search_fmt = f'%{search}%'
        query = query.filter(
            (Party.name.ilike(search_fmt)) |
            (Party.phone.ilike(search_fmt))
        )

    parties = query.all()
    rows = []
    for p in parties:
        bal = p.get_outstanding()
        if filter_type == 'receivable' and bal <= 0.01:
            continue
        elif filter_type == 'payable' and bal >= -0.01:
            continue
        elif filter_type == 'zero' and abs(bal) > 0.01:
            continue

        status = 'Receivable (Dr)' if bal > 0 else ('Payable (Cr)' if bal < 0 else 'Settled (₹0)')
        rows.append([
            p.id,
            p.name,
            p.party_type.capitalize(),
            p.phone or '',
            p.gstin or '',
            f'{p.opening_balance:.2f}',
            f'{abs(bal):.2f}',
            status
        ])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Party ID', 'Party Name', 'Party Type', 'Phone', 'GSTIN', 'Opening Balance', 'Outstanding Balance (INR)', 'Balance Status'])
    writer.writerows(rows)

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=party_outstanding_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_party():
    if request.method == 'POST':
        name = request.form.get('name')
        party_type = request.form.get('party_type')
        phone = request.form.get('phone')
        address = request.form.get('address')
        gstin = request.form.get('gstin')
        opening_balance = float(request.form.get('opening_balance') or 0)
        
        party = Party(
            name=name,
            party_type=party_type,
            phone=phone,
            address=address,
            gstin=gstin,
            opening_balance=opening_balance
        )
        db.session.add(party)
        db.session.commit()
        flash('Party added successfully.', 'success')
        return redirect(url_for('parties.list_parties'))
        
    return render_template('parties/form.html', action='Add', party=None)


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_party(id):
    party = Party.query.get_or_404(id)
    if request.method == 'POST':
        party.name = request.form.get('name')
        party.party_type = request.form.get('party_type')
        party.phone = request.form.get('phone')
        party.address = request.form.get('address')
        party.gstin = request.form.get('gstin')
        party.opening_balance = float(request.form.get('opening_balance') or 0)
        
        db.session.commit()
        flash('Party updated successfully.', 'success')
        return redirect(url_for('parties.list_parties'))
        
    return render_template('parties/form.html', action='Edit', party=party)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_party(id):
    party = Party.query.get_or_404(id)
    db.session.delete(party)
    db.session.commit()
    flash('Party deleted successfully.', 'success')
    return redirect(url_for('parties.list_parties'))


@bp.route('/<int:id>/ledger')
@login_required
def party_ledger(id):
    party = Party.query.get_or_404(id)
    
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    inwards_query = MaterialInward.query.filter_by(party_id=id)
    outwards_query = MaterialOutward.query.filter_by(party_id=id)
    payments_query = Payment.query.filter_by(party_id=id)
    
    if from_date:
        from_d = datetime.strptime(from_date, '%Y-%m-%d').date()
        inwards_query = inwards_query.filter(MaterialInward.date >= from_d)
        outwards_query = outwards_query.filter(MaterialOutward.date >= from_d)
        payments_query = payments_query.filter(Payment.date >= from_d)
        
    if to_date:
        to_d = datetime.strptime(to_date, '%Y-%m-%d').date()
        inwards_query = inwards_query.filter(MaterialInward.date <= to_d)
        outwards_query = outwards_query.filter(MaterialOutward.date <= to_d)
        payments_query = payments_query.filter(Payment.date <= to_d)
        
    inwards = inwards_query.all()
    outwards = outwards_query.all()
    payments = payments_query.all()
    
    transactions = []
    for m in inwards:
        transactions.append({'date': m.date, 'type': 'Inward', 'description': f'{m.material_type} - {m.quantity_mt} MT', 'debit': m.amount, 'credit': 0, 'vehicle': m.vehicle_no})
    for m in outwards:
        transactions.append({'date': m.date, 'type': 'Outward', 'description': f'{m.material_type} - {m.quantity_mt} MT', 'debit': 0, 'credit': m.amount, 'vehicle': m.vehicle_no})
    for p in payments:
        if p.payment_type == 'received':
            transactions.append({'date': p.date, 'type': 'Payment Received', 'description': f'{p.mode} - {p.reference_no or ""}', 'debit': p.amount, 'credit': 0, 'vehicle': ''})
        else:
            transactions.append({'date': p.date, 'type': 'Payment Paid', 'description': f'{p.mode} - {p.reference_no or ""}', 'debit': 0, 'credit': p.amount, 'vehicle': ''})
            
    transactions.sort(key=lambda x: x['date'])
    
    return render_template('parties/ledger.html', 
                           party=party, 
                           transactions=transactions,
                           from_date=from_date,
                           to_date=to_date)


@bp.route('/payments')
@login_required
def payments_list():
    query = Payment.query
    
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    party_id = request.args.get('party_id')
    payment_type = request.args.get('payment_type', 'all')
    mode = request.args.get('mode', 'all')
    
    if from_date:
        query = query.filter(Payment.date >= datetime.strptime(from_date, '%Y-%m-%d').date())
    if to_date:
        query = query.filter(Payment.date <= datetime.strptime(to_date, '%Y-%m-%d').date())
    if party_id:
        query = query.filter_by(party_id=party_id)
    if payment_type != 'all':
        query = query.filter_by(payment_type=payment_type)
    if mode != 'all':
        query = query.filter_by(mode=mode)
        
    payments = query.order_by(Payment.date.desc()).all()
    parties = Party.query.order_by(Party.name).all()
    
    total = sum(p.amount for p in payments)
    
    return render_template('parties/payments_list.html', 
                           payments=payments, 
                           parties=parties,
                           total=total,
                           from_date=from_date,
                           to_date=to_date,
                           party_id=party_id,
                           payment_type=payment_type,
                           mode=mode)


@bp.route('/payments/add', methods=['GET', 'POST'])
@login_required
def payment_add():
    if request.method == 'POST':
        date_str = request.form.get('date')
        party_id = request.form.get('party_id')
        payment_type = request.form.get('payment_type')
        amount = float(request.form.get('amount') or 0)
        mode = request.form.get('mode')
        reference_no = request.form.get('reference_no')
        notes = request.form.get('notes')
        
        payment = Payment(
            date=datetime.strptime(date_str, '%Y-%m-%d').date(),
            party_id=party_id,
            payment_type=payment_type,
            amount=amount,
            mode=mode,
            reference_no=reference_no,
            notes=notes
        )
        db.session.add(payment)
        db.session.commit()
        flash('Payment recorded successfully.', 'success')
        return redirect(url_for('parties.payments_list'))
        
    party_id = request.args.get('party_id')
    default_type = request.args.get('type', 'received')
    parties = Party.query.order_by(Party.name).all()
    return render_template('parties/payment_form.html', parties=parties, today=datetime.now().strftime('%Y-%m-%d'), selected_party_id=int(party_id) if party_id else None, default_type=default_type)


@bp.route('/payments/<int:id>/delete', methods=['POST'])
@login_required
def payment_delete(id):
    payment = Payment.query.get_or_404(id)
    db.session.delete(payment)
    db.session.commit()
    flash('Payment deleted successfully.', 'success')
    return redirect(url_for('parties.payments_list'))
