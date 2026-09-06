import io
import csv
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required
from models import db, Party, MaterialInward, MaterialOutward, Payment

bp = Blueprint('parties', __name__, url_prefix='/parties')

@bp.route('/')
@login_required
def list_parties():
    party_type = request.args.get('type', 'all')
    query = Party.query
    if party_type != 'all':
        query = query.filter_by(party_type=party_type)
    
    parties = query.order_by(Party.name).all()
    
    total_receivable = 0
    total_payable = 0
    
    for party in parties:
        party.outstanding = party.get_outstanding()
        if party.outstanding > 0:
            total_receivable += party.outstanding
        else:
            total_payable += abs(party.outstanding)
            
    return render_template('parties/list.html', 
                           parties=parties, 
                           party_type=party_type,
                           total_receivable=total_receivable,
                           total_payable=total_payable)

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
        
    parties = Party.query.order_by(Party.name).all()
    return render_template('parties/payment_form.html', parties=parties, today=datetime.now().strftime('%Y-%m-%d'))

@bp.route('/payments/<int:id>/delete', methods=['POST'])
@login_required
def payment_delete(id):
    payment = Payment.query.get_or_404(id)
    db.session.delete(payment)
    db.session.commit()
    flash('Payment deleted successfully.', 'success')
    return redirect(url_for('parties.payments_list'))
