import io
import csv
import urllib.parse
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required
from models import db, Party, MaterialInward, MaterialOutward, Payment, PartyAdjustment, PartyProductRate
from sqlalchemy import func

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


def get_all_parties_outstanding_map():
    """Calculates outstanding balance for all parties in fast bulk SQL queries."""
    inward_sums = dict(db.session.query(MaterialInward.party_id, func.sum(MaterialInward.amount)).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(MaterialOutward.party_id, func.sum(MaterialOutward.amount)).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())
    debit_adjs = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_unpaid_due', 'debit'])).group_by(PartyAdjustment.party_id).all())
    credit_adjs = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_advance', 'discount_waiver', 'credit'])).group_by(PartyAdjustment.party_id).all())
    
    all_parties = Party.query.all()
    outstanding_map = {}
    for p in all_parties:
        bal = ((p.opening_balance or 0.0) 
               + outward_sums.get(p.id, 0.0) 
               - inward_sums.get(p.id, 0.0) 
               - rec_sums.get(p.id, 0.0) 
               + paid_sums.get(p.id, 0.0) 
               + debit_adjs.get(p.id, 0.0) 
               - credit_adjs.get(p.id, 0.0))
        outstanding_map[p.id] = round(bal, 2)
    return outstanding_map


def resolve_party_payment_period(period_param, from_date_str, to_date_str):
    import calendar
    from datetime import timedelta
    today = date.today()
    if period_param == 'today':
        return today.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')
    elif period_param == 'this_week' or (not period_param and not from_date_str and not to_date_str):
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
        mon = today - timedelta(days=today.weekday())
        sun = mon + timedelta(days=6)
        return mon.strftime('%Y-%m-%d'), sun.strftime('%Y-%m-%d')
    return from_date_str, to_date_str


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
    outstanding_map = get_all_parties_outstanding_map()
    
    total_receivable = 0.0
    total_payable = 0.0
    
    for party in parties:
        party.outstanding = outstanding_map.get(party.id, 0.0)
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
    """Party-wise outstanding balance tracking with WhatsApp reminders (Ultra-fast bulk aggregation)."""
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
    outstanding_map = get_all_parties_outstanding_map()

    total_receivable = 0.0
    total_payable = 0.0
    receivable_count = 0
    payable_count = 0
    zero_count = 0

    processed_parties = []
    for p in all_parties:
        bal = outstanding_map.get(p.id, 0.0)
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
        sort_by=sort_by,
        search=search,
        total_receivable=total_receivable,
        total_payable=total_payable,
        net_balance=net_balance,
        receivable_count=receivable_count,
        payable_count=payable_count,
        zero_count=zero_count,
        today=date.today()
    )


@bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_party():
    if request.method == 'POST':
        name = request.form.get('name')
        party_type = request.form.get('party_type')
        phone = request.form.get('phone')
        address = request.form.get('address')
        gstin = request.form.get('gstin')
        opening_balance = request.form.get('opening_balance')
        default_selling_rate = request.form.get('default_selling_rate')
        
        if not name or not party_type:
            flash('Party name and type are required.', 'error')
            return render_template('parties/form.html', party=None)
            
        try:
            party = Party(
                name=name,
                party_type=party_type,
                phone=phone,
                address=address,
                gstin=gstin,
                opening_balance=float(opening_balance) if opening_balance else 0.0,
                default_selling_rate=float(default_selling_rate) if default_selling_rate else 0.0
            )
            db.session.add(party)
            db.session.commit()
            flash('Party added successfully.', 'success')
            return redirect(url_for('parties.list_parties'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding party: {str(e)}', 'error')
            
    return render_template('parties/form.html', party=None)


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
        opening_balance = request.form.get('opening_balance')
        party.opening_balance = float(opening_balance) if opening_balance else 0.0
        default_selling_rate = request.form.get('default_selling_rate')
        party.default_selling_rate = float(default_selling_rate) if default_selling_rate else 0.0
        
        if not party.name or not party.party_type:
            flash('Party name and type are required.', 'error')
            return render_template('parties/form.html', party=party)
            
        try:
            db.session.commit()
            flash('Party updated successfully.', 'success')
            return redirect(url_for('parties.list_parties'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating party: {str(e)}', 'error')
            
    return render_template('parties/form.html', party=party)


@bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete_party(id):
    party = Party.query.get_or_404(id)
    try:
        db.session.delete(party)
        db.session.commit()
        flash('Party deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting party: {str(e)}', 'error')
    return redirect(url_for('parties.list_parties'))


@bp.route('/<int:id>/ledger')
@login_required
def party_ledger(id):
    party = Party.query.get_or_404(id)
    from_date_str = request.args.get('from_date', '')
    to_date_str = request.args.get('to_date', '')
    
    inwards_query = MaterialInward.query.filter_by(party_id=party.id)
    outwards_query = MaterialOutward.query.filter_by(party_id=party.id)
    payments_query = Payment.query.filter_by(party_id=party.id)
    adjs_query = PartyAdjustment.query.filter_by(party_id=party.id)
    
    if from_date_str:
        try:
            f_d = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            inwards_query = inwards_query.filter(MaterialInward.date >= f_d)
            outwards_query = outwards_query.filter(MaterialOutward.date >= f_d)
            payments_query = payments_query.filter(Payment.date >= f_d)
            adjs_query = adjs_query.filter(PartyAdjustment.date >= f_d)
        except ValueError:
            pass
            
    if to_date_str:
        try:
            t_d = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            inwards_query = inwards_query.filter(MaterialInward.date <= t_d)
            outwards_query = outwards_query.filter(MaterialOutward.date <= t_d)
            payments_query = payments_query.filter(Payment.date <= t_d)
            adjs_query = adjs_query.filter(PartyAdjustment.date <= t_d)
        except ValueError:
            pass
            
    inwards = inwards_query.all()
    outwards = outwards_query.all()
    payments = payments_query.all()
    adjustments = adjs_query.all()
    
    transactions = []
    
    # 1. Outward Goods Dispatch to Customer (Debit: Customer owes money)
    for m in outwards:
        unit = m.quantity_unit if hasattr(m, 'quantity_unit') and m.quantity_unit else 'MT'
        transactions.append({
            'id': f'out_{m.id}',
            'date': m.date,
            'type': 'Outward (Sales Dispatch)',
            'description': f'{m.material_type} - {m.quantity_mt} {unit}',
            'debit': m.amount,
            'credit': 0.0,
            'vehicle': m.vehicle_no or '',
            'is_adj': False
        })

    # 2. Inward Raw Material from Supplier (Credit: Plant owes supplier)
    for m in inwards:
        unit = m.quantity_unit if hasattr(m, 'quantity_unit') and m.quantity_unit else 'MT'
        transactions.append({
            'id': f'in_{m.id}',
            'date': m.date,
            'type': 'Inward (Material Purchase)',
            'description': f'{m.material_type} - {m.quantity_mt} {unit}',
            'debit': 0.0,
            'credit': m.amount,
            'vehicle': m.vehicle_no or '',
            'is_adj': False
        })
        
    # 3. Payments
    for p in payments:
        if p.payment_type == 'received':
            # Payment Received from Customer (Credit: reduces customer debt)
            transactions.append({
                'id': f'pay_{p.id}',
                'payment_id': p.id,
                'date': p.date,
                'type': 'Payment Received',
                'description': f'{p.mode.upper()} - {p.reference_no or "Receipt"} {f"({p.notes})" if p.notes else ""}',
                'debit': 0.0,
                'credit': p.amount,
                'vehicle': '',
                'is_adj': False,
                'is_payment': True,
                'amount': p.amount
            })
        else:
            # Payment Paid to Supplier (Debit: settles supplier debt)
            transactions.append({
                'id': f'pay_{p.id}',
                'payment_id': p.id,
                'date': p.date,
                'type': 'Payment Paid (Supplier Settlement)',
                'description': f'{p.mode.upper()} - {p.reference_no or "Paid"} {f"({p.notes})" if p.notes else ""}',
                'debit': p.amount,
                'credit': 0.0,
                'vehicle': '',
                'is_adj': False,
                'is_payment': True,
                'amount': p.amount
            })

    # 4. Past Unpaid Dues / Adjustments from Before Software
    for a in adjustments:
        if a.adjustment_type in ('past_unpaid_due', 'debit'):
            transactions.append({
                'id': f'adj_{a.id}',
                'adj_id': a.id,
                'date': a.date,
                'type': 'Past Unpaid Due (Before Software)',
                'description': f'{a.reason} {f"[Ref: {a.reference_no}]" if a.reference_no else ""}',
                'debit': a.amount,
                'credit': 0.0,
                'vehicle': '',
                'is_adj': True
            })
        elif a.adjustment_type == 'past_advance':
            transactions.append({
                'id': f'adj_{a.id}',
                'adj_id': a.id,
                'date': a.date,
                'type': 'Past Advance Received',
                'description': f'{a.reason} {f"[Ref: {a.reference_no}]" if a.reference_no else ""}',
                'debit': 0.0,
                'credit': a.amount,
                'vehicle': '',
                'is_adj': True
            })
        else:
            transactions.append({
                'id': f'adj_{a.id}',
                'adj_id': a.id,
                'date': a.date,
                'type': 'Discount / Settlement Waiver',
                'description': f'{a.reason} {f"[Ref: {a.reference_no}]" if a.reference_no else ""}',
                'debit': 0.0,
                'credit': a.amount,
                'vehicle': '',
                'is_adj': True
            })
            
    transactions.sort(key=lambda x: x['date'])
    
    running_balance = party.opening_balance or 0.0
    for t in transactions:
        running_balance = running_balance + t['debit'] - t['credit']
        t['balance'] = running_balance
        
    total_debit = sum(t['debit'] for t in transactions)
    total_credit = sum(t['credit'] for t in transactions)
    
    cur_outstanding = party.get_outstanding()
    
    return render_template('parties/ledger.html',
                           party=party,
                           transactions=transactions,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           total_debit=total_debit,
                           total_credit=total_credit,
                           closing_balance=running_balance,
                           cur_outstanding=cur_outstanding,
                           today=date.today())


@bp.route('/<int:id>/settle-full', methods=['POST'])
@login_required
def settle_full(id):
    """1-Click Full Settlement of party account to clear balance to ₹0.00."""
    party = Party.query.get_or_404(id)
    cur_bal = party.get_outstanding()
    
    mode = request.form.get('mode', 'bank')
    reference_no = request.form.get('reference_no', '').strip()
    notes = request.form.get('notes', '').strip()
    settle_date_str = request.form.get('date', '')
    
    settle_date = date.today()
    if settle_date_str:
        try:
            settle_date = datetime.strptime(settle_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass
            
    if cur_bal < -0.01:
        # Plant owes supplier -> Plant pays in full
        pay_amount = abs(cur_bal)
        payment = Payment(
            date=settle_date,
            party_id=party.id,
            payment_type='paid',
            amount=round(pay_amount, 2),
            mode=mode,
            reference_no=reference_no or 'Full Settlement',
            notes=notes or f"Full account payment settlement to {party.name} (₹{pay_amount:,.2f} paid in full)"
        )
        db.session.add(payment)
        db.session.commit()
        flash(f"Account Settled! Paid ₹{pay_amount:,.2f} in full to {party.name}. Balance is now ₹0.00 (Clear).", 'success')
    elif cur_bal > 0.01:
        # Customer owes plant -> Full payment received from customer
        rec_amount = cur_bal
        payment = Payment(
            date=settle_date,
            party_id=party.id,
            payment_type='received',
            amount=round(rec_amount, 2),
            mode=mode,
            reference_no=reference_no or 'Full Settlement',
            notes=notes or f"Full payment receipt from {party.name} (₹{rec_amount:,.2f} received in full)"
        )
        db.session.add(payment)
        db.session.commit()
        flash(f"Account Settled! Received ₹{rec_amount:,.2f} in full from {party.name}. Balance is now ₹0.00 (Clear).", 'success')
    else:
        flash(f"Account balance for {party.name} is already ₹0.00 (Fully Settled).", 'info')
        
    redirect_url = request.form.get('redirect_to') or request.referrer or url_for('parties.party_ledger', id=party.id)
    return redirect(redirect_url)


@bp.route('/<int:id>/add-past-due', methods=['POST'])
@login_required
def add_past_due(id):
    """Add past unpaid dues from before software or old balance adjustments."""
    party = Party.query.get_or_404(id)
    
    amount_str = request.form.get('amount', '').strip()
    adj_type = request.form.get('adjustment_type', 'past_unpaid_due')
    reason = request.form.get('reason', '').strip()
    ref_no = request.form.get('reference_no', '').strip()
    due_date_str = request.form.get('date', '').strip()
    
    if not amount_str or not reason:
        flash("Amount and description/reason are required to record a past due / balance adjustment.", "error")
        return redirect(request.referrer or url_for('parties.party_ledger', id=party.id))
        
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(request.referrer or url_for('parties.party_ledger', id=party.id))
            
        due_date = date.today()
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
            
        adj = PartyAdjustment(
            party_id=party.id,
            date=due_date,
            adjustment_type=adj_type,
            amount=round(amount, 2),
            reason=reason,
            reference_no=ref_no
        )
        db.session.add(adj)
        db.session.commit()
        
        if adj_type == 'past_unpaid_due':
            flash(f"Successfully added previous unpaid due of ₹{amount:,.2f} for {party.name}. Added to customer dues!", "success")
        elif adj_type == 'past_advance':
            flash(f"Successfully recorded past advance of ₹{amount:,.2f} for {party.name}.", "success")
        else:
            flash(f"Successfully recorded adjustment of ₹{amount:,.2f} for {party.name}.", "success")
            
    except Exception as e:
        db.session.rollback()
        flash(f"Error recording past due adjustment: {str(e)}", "error")
        
    redirect_url = request.form.get('redirect_to') or request.referrer or url_for('parties.party_ledger', id=party.id)
    return redirect(redirect_url)


@bp.route('/adjustments/<int:id>/delete', methods=['POST'])
@login_required
def delete_adjustment(id):
    """Delete a past due adjustment record."""
    adj = PartyAdjustment.query.get_or_404(id)
    party_id = adj.party_id
    try:
        db.session.delete(adj)
        db.session.commit()
        flash("Past due adjustment deleted successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting adjustment: {str(e)}", "error")
    return redirect(request.referrer or url_for('parties.party_ledger', id=party_id))


@bp.route('/api/<int:id>/balance')
@login_required
def api_party_balance(id):
    """API endpoint to get party balance and fast settlement details."""
    party = Party.query.get_or_404(id)
    bal = party.get_outstanding()
    return jsonify({
        'party_id': party.id,
        'party_name': party.name,
        'party_type': party.party_type,
        'phone': party.phone or '',
        'outstanding': round(bal, 2),
        'abs_outstanding': round(abs(bal), 2),
        'is_receivable': bal > 0.01,
        'is_payable': bal < -0.01,
        'is_settled': abs(bal) <= 0.01,
        'formatted': f"₹{abs(bal):,.2f} {'(Customer Due Dr)' if bal > 0.01 else ('(Supplier Due Cr)' if bal < -0.01 else '(Settled)')}"
    })


@bp.route('/api/check-duplicate-payment')
@login_required
def check_duplicate_payment():
    party_id = request.args.get('party_id', type=int)
    date_str = request.args.get('date', '').strip()
    amount_str = request.args.get('amount', '').strip()
    payment_type = request.args.get('payment_type', '').strip()
    exclude_id = request.args.get('exclude_id', type=int)

    if not party_id or not date_str or not amount_str:
        return jsonify({'is_duplicate': False, 'count': 0})

    try:
        p_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        amt = float(amount_str)
    except (ValueError, TypeError):
        return jsonify({'is_duplicate': False, 'count': 0})

    query = Payment.query.filter(
        Payment.party_id == party_id,
        Payment.date == p_date,
        func.abs(Payment.amount - amt) < 0.01
    )
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    if exclude_id:
        query = query.filter(Payment.id != exclude_id)

    matches = query.all()
    if not matches:
        return jsonify({'is_duplicate': False, 'count': 0})

    party = Party.query.get(party_id)
    party_name = party.name if party else f"Party #{party_id}"
    
    match_details = []
    for m in matches:
        match_details.append({
            'id': m.id,
            'date': m.date.strftime('%Y-%m-%d'),
            'amount': m.amount,
            'payment_type': m.payment_type,
            'type_label': 'Paid to Supplier' if m.payment_type == 'paid' else 'Received from Customer',
            'mode': m.mode.upper() if m.mode else 'N/A',
            'reference_no': m.reference_no or 'None',
            'notes': m.notes or 'None',
            'created_at': m.created_at.strftime('%d-%b-%Y %H:%M') if m.created_at else ''
        })

    first_m = match_details[0]
    msg = (f"⚠️ Duplicate Alert: A {first_m['type_label']} payment of ₹{amt:,.2f} "
           f"for {party_name} on {date_str} already exists in the records! "
           f"(Mode: {first_m['mode']}, Ref: {first_m['reference_no']}).")

    return jsonify({
        'is_duplicate': True,
        'count': len(matches),
        'party_name': party_name,
        'date': date_str,
        'amount': amt,
        'message': msg,
        'matches': match_details
    })


@bp.route('/payments')
@login_required
def payments_list():
    from datetime import timedelta
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')
    from_date_str, to_date_str = resolve_party_payment_period(period_param, from_date_raw, to_date_raw)

    party_id = request.args.get('party_id', type=int)
    payment_type = request.args.get('payment_type', '').strip()
    mode = request.args.get('mode', '').strip()

    query = Payment.query

    from_d = None
    to_d = None
    if from_date_str:
        try:
            from_d = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(Payment.date >= from_d)
        except ValueError:
            pass

    if to_date_str:
        try:
            to_d = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(Payment.date <= to_d)
        except ValueError:
            pass

    if party_id:
        query = query.filter(Payment.party_id == party_id)

    if payment_type and payment_type != 'all':
        query = query.filter(Payment.payment_type == payment_type)

    if mode and mode != 'all':
        query = query.filter(Payment.mode == mode)

    payments = query.order_by(Payment.date.desc(), Payment.id.desc()).all()
    parties = Party.query.order_by(Party.name).all()

    total_paid_suppliers = sum(p.amount for p in payments if p.payment_type == 'paid')
    total_received_customers = sum(p.amount for p in payments if p.payment_type == 'received')
    total_amount = sum(p.amount for p in payments)

    # Calculate previous & next week date strings for week switcher navigation
    if from_d and to_d:
        prev_week_from = (from_d - timedelta(days=7)).strftime('%Y-%m-%d')
        prev_week_to = (to_d - timedelta(days=7)).strftime('%Y-%m-%d')
        next_week_from = (from_d + timedelta(days=7)).strftime('%Y-%m-%d')
        next_week_to = (to_d + timedelta(days=7)).strftime('%Y-%m-%d')
    else:
        today = date.today()
        cur_mon = today - timedelta(days=today.weekday())
        cur_sun = cur_mon + timedelta(days=6)
        prev_week_from = (cur_mon - timedelta(days=7)).strftime('%Y-%m-%d')
        prev_week_to = (cur_sun - timedelta(days=7)).strftime('%Y-%m-%d')
        next_week_from = (cur_mon + timedelta(days=7)).strftime('%Y-%m-%d')
        next_week_to = (cur_sun + timedelta(days=7)).strftime('%Y-%m-%d')

    return render_template('parties/payments_list.html',
                           payments=payments,
                           parties=parties,
                           from_date=from_date_str,
                           to_date=to_date_str,
                           period=period_param,
                           prev_week_from=prev_week_from,
                           prev_week_to=prev_week_to,
                           next_week_from=next_week_from,
                           next_week_to=next_week_to,
                           selected_party=party_id,
                           selected_type=payment_type,
                           selected_mode=mode,
                           total_amount=total_amount,
                           total_paid_suppliers=total_paid_suppliers,
                           total_received_customers=total_received_customers,
                           today=date.today().strftime('%Y-%m-%d'))


@bp.route('/payments/export')
@login_required
def export_payments_csv():
    period_param = request.args.get('period', '')
    from_date_raw = request.args.get('from_date', '')
    to_date_raw = request.args.get('to_date', '')
    from_date_str, to_date_str = resolve_party_payment_period(period_param, from_date_raw, to_date_raw)

    party_id = request.args.get('party_id', type=int)
    payment_type = request.args.get('payment_type', '').strip()
    mode = request.args.get('mode', '').strip()

    query = Payment.query

    if from_date_str:
        try:
            f_d = datetime.strptime(from_date_str, '%Y-%m-%d').date()
            query = query.filter(Payment.date >= f_d)
        except ValueError:
            pass

    if to_date_str:
        try:
            t_d = datetime.strptime(to_date_str, '%Y-%m-%d').date()
            query = query.filter(Payment.date <= t_d)
        except ValueError:
            pass

    if party_id:
        query = query.filter(Payment.party_id == party_id)

    if payment_type and payment_type != 'all':
        query = query.filter(Payment.payment_type == payment_type)

    if mode and mode != 'all':
        query = query.filter(Payment.mode == mode)

    payments = query.order_by(Payment.date.desc(), Payment.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        '#', 'Payment Date', 'Party / Beneficiary', 'Party Type', 'Payment Type',
        'Amount (₹)', 'Payment Mode', 'Reference / UTR / Cheque No', 'Notes / Remarks', 'Created At'
    ])

    for idx, p in enumerate(payments, start=1):
        p_name = p.party.name if p.party else 'N/A'
        p_type = p.party.party_type.capitalize() if p.party and p.party.party_type else 'N/A'
        p_type_label = 'Paid (To Supplier)' if p.payment_type == 'paid' else 'Received (From Customer)'
        writer.writerow([
            idx,
            p.date.strftime('%Y-%m-%d') if p.date else '',
            p_name,
            p_type,
            p_type_label,
            f"{p.amount:.2f}",
            p.mode.capitalize() if p.mode else '',
            p.reference_no or '',
            p.notes or '',
            p.created_at.strftime('%Y-%m-%d %H:%M:%S') if p.created_at else ''
        ])

    output.seek(0)
    filename = f"payment_statement_{from_date_str or 'all'}_to_{to_date_str or 'all'}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )


@bp.route('/payments/add', methods=['GET', 'POST'])
@login_required
def payment_add():
    parties = Party.query.order_by(Party.name).all()

    if request.method == 'POST':
        date_str = request.form.get('date')
        party_id = request.form.get('party_id')
        payment_type = request.form.get('payment_type')
        amount = request.form.get('amount')
        mode = request.form.get('mode')
        reference_no = request.form.get('reference_no', '').strip()
        notes = request.form.get('notes', '').strip()
        confirm_duplicate = request.form.get('confirm_duplicate') in ('1', 'true', 'yes', 'on')

        if not date_str or not party_id or not payment_type or not amount or not mode:
            flash('All mandatory fields (Date, Party, Payment Type, Amount, Mode) are required.', 'error')
            return render_template('parties/payment_form.html', parties=parties, today=date.today().strftime('%Y-%m-%d'))

        try:
            p_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            amt_val = float(amount)
            p_id_int = int(party_id)
            p_obj = Party.query.get(p_id_int)
            p_name = p_obj.name if p_obj else 'Party'

            # Duplicate detection: same person, same amount, same date
            existing_dup = Payment.query.filter(
                Payment.party_id == p_id_int,
                Payment.date == p_date,
                func.abs(Payment.amount - amt_val) < 0.01
            ).first()

            if existing_dup and not confirm_duplicate:
                dup_type = 'Paid to Supplier' if existing_dup.payment_type == 'paid' else 'Received from Customer'
                flash(
                    f'⚠️ DUPLICATE PAYMENT NOTICE: A payment of ₹{amt_val:,.2f} ({dup_type}) for {p_name} '
                    f'on {date_str} was already recorded (Ref: {existing_dup.reference_no or "None"}, Mode: {existing_dup.mode.upper()}). '
                    f'If this is an intentional repeat transaction, please check "Confirm Duplicate" to record.',
                    'warning'
                )
                return render_template(
                    'parties/payment_form.html',
                    parties=parties,
                    today=date.today().strftime('%Y-%m-%d'),
                    duplicate_alert={
                        'party_name': p_name,
                        'date': date_str,
                        'amount': amt_val,
                        'existing_ref': existing_dup.reference_no or 'None',
                        'existing_mode': existing_dup.mode.upper(),
                        'existing_type': dup_type
                    },
                    form_data=request.form
                )

            payment = Payment(
                date=p_date,
                party_id=p_id_int,
                payment_type=payment_type,
                amount=amt_val,
                mode=mode,
                reference_no=reference_no or None,
                notes=notes or None
            )
            db.session.add(payment)
            db.session.commit()
            
            type_label = 'paid to supplier' if payment_type == 'paid' else 'received from customer'
            dup_suffix = ' (Duplicate Confirmed)' if existing_dup else ''
            flash(f'Payment of ₹{amt_val:,.2f} {type_label} ({p_name}) recorded successfully{dup_suffix}.', 'success')
            return redirect(url_for('parties.payments_list'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error recording payment: {str(e)}', 'error')

    return render_template('parties/payment_form.html', parties=parties, today=date.today().strftime('%Y-%m-%d'))


@bp.route('/payments/<int:id>/delete', methods=['POST'])
@login_required
def payment_delete(id):
    payment = Payment.query.get_or_404(id)
    try:
        amt = payment.amount
        p_name = payment.party.name if payment.party else 'Party'
        p_type = 'Payment Received' if payment.payment_type == 'received' else 'Payment Paid (Supplier)'
        party_id = payment.party_id
        db.session.delete(payment)
        db.session.commit()
        flash(f'🗑️ {p_type} of ₹{amt:,.2f} for {p_name} deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payment: {str(e)}', 'error')

    next_url = request.form.get('next') or request.args.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('parties.payments_list'))


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
            (Party.phone.ilike(search_fmt)) |
            (Party.gstin.ilike(search_fmt))
        )

    all_parties = query.all()
    outstanding_map = get_all_parties_outstanding_map()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Party ID', 'Party Name', 'Party Type', 'Phone', 'GSTIN', 'Outstanding Balance (INR)', 'Balance Type', 'Status'])

    for p in all_parties:
        bal = outstanding_map.get(p.id, 0.0)
        if filter_type == 'receivable' and bal <= 0.01:
            continue
        elif filter_type == 'payable' and bal >= -0.01:
            continue
        elif filter_type == 'zero' and abs(bal) > 0.01:
            continue

        bal_type = 'Debit (Receivable from Party)' if bal > 0 else ('Credit (Payable to Party)' if bal < 0 else 'Clear')
        status = 'DUE' if bal > 0 else ('ADVANCE' if bal < 0 else 'NIL')
        writer.writerow([p.id, p.name, p.party_type, p.phone or '', p.gstin or '', f"{abs(bal):.2f}", bal_type, status])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=party_outstanding_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/<int:id>/rates/update', methods=['POST'])
@login_required
def update_party_rate(id):
    """Create or update an agreed selling rate for a specific product and party."""
    party = Party.query.get_or_404(id)
    product_name = request.form.get('product_name', '').strip()
    rate_val = request.form.get('rate', '').strip()
    unit = request.form.get('unit', 'Pieces / Pcs').strip()
    notes = request.form.get('notes', '').strip()

    if not product_name:
        flash('Product name is required to set agreed rate.', 'error')
        return redirect(url_for('parties.party_ledger', id=party.id))

    try:
        rate = float(rate_val) if rate_val else 0.0
    except ValueError:
        flash('Invalid rate amount.', 'error')
        return redirect(url_for('parties.party_ledger', id=party.id))

    # Check if rate already exists for this party and product
    existing = PartyProductRate.query.filter_by(party_id=party.id, product_name=product_name).first()
    try:
        if existing:
            existing.rate = rate
            existing.unit = unit
            existing.notes = notes
        else:
            new_rate = PartyProductRate(
                party_id=party.id,
                product_name=product_name,
                rate=rate,
                unit=unit,
                notes=notes
            )
            db.session.add(new_rate)
        db.session.commit()
        flash(f'Agreed selling rate of ₹{rate:,.2f} for "{product_name}" saved for {party.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error saving agreed rate: {str(e)}', 'error')

    return redirect(url_for('parties.party_ledger', id=party.id))


@bp.route('/rates/<int:rate_id>/delete', methods=['POST'])
@login_required
def delete_party_rate(rate_id):
    """Delete a configured agreed selling rate."""
    rate_entry = PartyProductRate.query.get_or_404(rate_id)
    party_id = rate_entry.party_id
    try:
        db.session.delete(rate_entry)
        db.session.commit()
        flash('Agreed selling rate removed successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error removing rate: {str(e)}', 'error')

    return redirect(url_for('parties.party_ledger', id=party_id))


@bp.route('/api/<int:id>/rates', methods=['GET'])
@login_required
def api_party_rates(id):
    """JSON API to fetch all agreed rates for a given party."""
    party = Party.query.get_or_404(id)
    rates_list = PartyProductRate.query.filter_by(party_id=party.id).all()
    
    rates_dict = {}
    for r in rates_list:
        rates_dict[r.product_name] = {
            'rate': r.rate,
            'unit': r.unit,
            'notes': r.notes or ''
        }

    return jsonify({
        'party_id': party.id,
        'party_name': party.name,
        'default_selling_rate': party.default_selling_rate or 0.0,
        'rates': rates_dict
    })




# ==============================================================================
# PARTY EARLY EXPENSES, PREVIOUS BALANCES & OUTSTANDING SHEET
# ==============================================================================

@bp.route('/early-statement')
@login_required
def early_statement():
    """Comprehensive statement of party initial opening balances, early expenses, past unpaid dues, and live ledger balances."""
    filter_type = request.args.get('filter', 'all')  # all, receivable, payable, has_early, zero
    party_type = request.args.get('type', 'all')      # all, customer, supplier, both
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

    all_parties = query.order_by(Party.name).all()
    all_parties_list = Party.query.order_by(Party.name).all()

    # Fast bulk aggregate queries
    inward_sums = dict(db.session.query(MaterialInward.party_id, func.sum(MaterialInward.amount)).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(MaterialOutward.party_id, func.sum(MaterialOutward.amount)).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())
    
    # Early Expenses and Past Dues (+ Debit)
    early_expenses_sums = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_unpaid_due', 'debit', 'early_expense'])).group_by(PartyAdjustment.party_id).all())
    
    # Early Advances & Waivers (- Credit)
    early_advances_sums = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_advance', 'discount_waiver', 'credit'])).group_by(PartyAdjustment.party_id).all())

    statement_rows = []
    total_opening_bal = 0.0
    total_early_expenses = 0.0
    total_early_advances = 0.0
    total_net_prior = 0.0
    total_inward_all = 0.0
    total_outward_all = 0.0
    total_rec_all = 0.0
    total_paid_all = 0.0
    total_net_outstanding = 0.0
    total_receivable = 0.0
    total_payable = 0.0

    for p in all_parties:
        op_bal = round(p.opening_balance or 0.0, 2)
        early_exp = round(early_expenses_sums.get(p.id, 0.0), 2)
        early_adv = round(early_advances_sums.get(p.id, 0.0), 2)
        net_prior = round(op_bal + early_exp - early_adv, 2)
        
        inw = round(inward_sums.get(p.id, 0.0), 2)
        outw = round(outward_sums.get(p.id, 0.0), 2)
        p_rec = round(rec_sums.get(p.id, 0.0), 2)
        p_paid = round(paid_sums.get(p.id, 0.0), 2)
        
        # Outstanding Formula: opening_balance + outward - inward - rec + paid + early_exp - early_adv
        outstanding = round(op_bal + outw - inw - p_rec + p_paid + early_exp - early_adv, 2)
        abs_outstanding = abs(outstanding)

        # Apply filter_type
        if filter_type == 'receivable' and outstanding <= 0.01:
            continue
        if filter_type == 'payable' and outstanding >= -0.01:
            continue
        if filter_type == 'has_early' and early_exp == 0 and early_adv == 0 and op_bal == 0:
            continue
        if filter_type == 'zero' and abs_outstanding > 0.01:
            continue

        total_opening_bal += op_bal
        total_early_expenses += early_exp
        total_early_advances += early_adv
        total_net_prior += net_prior
        total_inward_all += inw
        total_outward_all += outw
        total_rec_all += p_rec
        total_paid_all += p_paid
        total_net_outstanding += outstanding

        if outstanding > 0:
            total_receivable += outstanding
        else:
            total_payable += abs_outstanding

        whatsapp_url = generate_whatsapp_url(p, outstanding)

        statement_rows.append({
            'party': p,
            'opening_balance': op_bal,
            'early_expenses': early_exp,
            'early_advances': early_adv,
            'net_prior': net_prior,
            'inward_amount': inw,
            'outward_amount': outw,
            'payments_rec': p_rec,
            'payments_paid': p_paid,
            'outstanding': outstanding,
            'abs_outstanding': abs_outstanding,
            'whatsapp_url': whatsapp_url
        })

    return render_template(
        'parties/early_statement.html',
        statement_rows=statement_rows,
        all_parties_list=all_parties_list,
        filter_type=filter_type,
        party_type=party_type,
        search=search,
        total_opening_bal=round(total_opening_bal, 2),
        total_early_expenses=round(total_early_expenses, 2),
        total_early_advances=round(total_early_advances, 2),
        total_net_prior=round(total_net_prior, 2),
        total_inward_all=round(total_inward_all, 2),
        total_outward_all=round(total_outward_all, 2),
        total_rec_all=round(total_rec_all, 2),
        total_paid_all=round(total_paid_all, 2),
        total_net_outstanding=round(total_net_outstanding, 2),
        total_receivable=round(total_receivable, 2),
        total_payable=round(total_payable, 2),
        today=date.today()
    )


@bp.route('/early-statement/export')
@login_required
def early_statement_export():
    """Export Party Early Expenses, Previous Balances & Outstanding Sheet to CSV/Excel."""
    filter_type = request.args.get('filter', 'all')
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

    all_parties = query.order_by(Party.name).all()

    inward_sums = dict(db.session.query(MaterialInward.party_id, func.sum(MaterialInward.amount)).group_by(MaterialInward.party_id).all())
    outward_sums = dict(db.session.query(MaterialOutward.party_id, func.sum(MaterialOutward.amount)).group_by(MaterialOutward.party_id).all())
    paid_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'paid').group_by(Payment.party_id).all())
    rec_sums = dict(db.session.query(Payment.party_id, func.sum(Payment.amount)).filter(Payment.payment_type == 'received').group_by(Payment.party_id).all())
    early_expenses_sums = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_unpaid_due', 'debit', 'early_expense'])).group_by(PartyAdjustment.party_id).all())
    early_advances_sums = dict(db.session.query(PartyAdjustment.party_id, func.sum(PartyAdjustment.amount)).filter(PartyAdjustment.adjustment_type.in_(['past_advance', 'discount_waiver', 'credit'])).group_by(PartyAdjustment.party_id).all())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Party ID', 'Party Name', 'Party Type', 'Phone', 'GSTIN',
        'Initial Opening Balance (₹)', 'Early Expenses & Past Dues (₹)', 'Early Advances & Credits (₹)',
        'Net Prior Balance (₹)', 'Inward Amount (₹)', 'Outward Amount (₹)',
        'Payments Received (₹)', 'Payments Paid (₹)', 'Current Outstanding (₹)', 'Balance Type', 'Status'
    ])

    for p in all_parties:
        op_bal = round(p.opening_balance or 0.0, 2)
        early_exp = round(early_expenses_sums.get(p.id, 0.0), 2)
        early_adv = round(early_advances_sums.get(p.id, 0.0), 2)
        net_prior = round(op_bal + early_exp - early_adv, 2)
        
        inw = round(inward_sums.get(p.id, 0.0), 2)
        outw = round(outward_sums.get(p.id, 0.0), 2)
        p_rec = round(rec_sums.get(p.id, 0.0), 2)
        p_paid = round(paid_sums.get(p.id, 0.0), 2)
        
        outstanding = round(op_bal + outw - inw - p_rec + p_paid + early_exp - early_adv, 2)
        abs_outstanding = abs(outstanding)

        if filter_type == 'receivable' and outstanding <= 0.01:
            continue
        if filter_type == 'payable' and outstanding >= -0.01:
            continue
        if filter_type == 'has_early' and early_exp == 0 and early_adv == 0 and op_bal == 0:
            continue
        if filter_type == 'zero' and abs_outstanding > 0.01:
            continue

        bal_type = 'Debit (Dr)' if outstanding > 0 else ('Credit (Cr)' if outstanding < 0 else 'Nil')
        status = 'Customer Due' if outstanding > 0 else ('Supplier Advance / Payable' if outstanding < 0 else 'Settled')

        writer.writerow([
            p.id, p.name, p.party_type, p.phone or '', p.gstin or '',
            f"{op_bal:.2f}", f"{early_exp:.2f}", f"{early_adv:.2f}",
            f"{net_prior:.2f}", f"{inw:.2f}", f"{outw:.2f}",
            f"{p_rec:.2f}", f"{p_paid:.2f}", f"{abs_outstanding:.2f}", bal_type, status
        ])

    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename=party_early_statement_{date.today().strftime("%Y%m%d")}.csv'
    return response


@bp.route('/<int:id>/update-opening-balance', methods=['POST'])
@login_required
def update_opening_balance(id):
    """Update party initial opening balance."""
    party = Party.query.get_or_404(id)
    opening_bal_val = request.form.get('opening_balance', '0').strip()
    try:
        opening_bal = float(opening_bal_val) if opening_bal_val else 0.0
        party.opening_balance = opening_bal
        db.session.commit()
        flash(f'Initial opening balance updated to ₹{opening_bal:,.2f} for {party.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating opening balance: {str(e)}', 'error')

    redirect_url = request.form.get('redirect_to') or url_for('parties.early_statement')
    return redirect(redirect_url)



@bp.route('/adjustments/add', methods=['POST'])
@login_required
def record_past_due_adjustment():
    """Add a past due, early expense, or past advance adjustment from any modal or sheet."""
    party_id = request.form.get('party_id')
    if not party_id:
        flash("Party is required to record early expense / past due.", "error")
        return redirect(request.form.get('redirect_to') or url_for('parties.early_statement'))

    party = Party.query.get_or_404(party_id)
    amount_str = request.form.get('amount', '').strip()
    adj_type = request.form.get('adjustment_type', 'past_unpaid_due')
    reason = request.form.get('reason', '').strip()
    ref_no = request.form.get('reference_no', '').strip()
    due_date_str = request.form.get('date', '').strip()

    if not amount_str or not reason:
        flash("Amount and reason are required.", "error")
        return redirect(request.form.get('redirect_to') or url_for('parties.early_statement'))

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", "error")
            return redirect(request.form.get('redirect_to') or url_for('parties.early_statement'))

        due_date = date.today()
        if due_date_str:
            due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()

        adj = PartyAdjustment(
            party_id=party.id,
            date=due_date,
            adjustment_type=adj_type,
            amount=round(amount, 2),
            reason=reason,
            reference_no=ref_no
        )
        db.session.add(adj)
        db.session.commit()
        flash(f"Successfully recorded adjustment of ₹{amount:,.2f} for {party.name}.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error recording adjustment: {str(e)}", "error")

    redirect_url = request.form.get('redirect_to') or url_for('parties.early_statement')
    return redirect(redirect_url)
