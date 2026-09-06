import io
import csv
from datetime import datetime
from flask import Blueprint, render_template, request, Response
from flask_login import login_required
from models import db, Party, MaterialInward, MaterialOutward, Payment

bp = Blueprint('reports', __name__, url_prefix='/reports')

def get_report_data(report_type, from_date, to_date, party_id):
    data = {}
    
    from_d = datetime.strptime(from_date, '%Y-%m-%d').date() if from_date else None
    to_d = datetime.strptime(to_date, '%Y-%m-%d').date() if to_date else None

    if report_type == 'stock_summary':
        inward_query = db.session.query(MaterialInward.material_type, db.func.sum(MaterialInward.quantity_mt).label('total_inward'))
        outward_query = db.session.query(MaterialOutward.material_type, db.func.sum(MaterialOutward.quantity_mt).label('total_outward'))
        
        if from_d:
            inward_query = inward_query.filter(MaterialInward.date >= from_d)
            outward_query = outward_query.filter(MaterialOutward.date >= from_d)
        if to_d:
            inward_query = inward_query.filter(MaterialInward.date <= to_d)
            outward_query = outward_query.filter(MaterialOutward.date <= to_d)
            
        inward_totals = inward_query.group_by(MaterialInward.material_type).all()
        outward_totals = outward_query.group_by(MaterialOutward.material_type).all()
        
        materials = set([r[0] for r in inward_totals] + [r[0] for r in outward_totals])
        
        results = []
        for mat in materials:
            in_qty = next((r[1] for r in inward_totals if r[0] == mat), 0) or 0
            out_qty = next((r[1] for r in outward_totals if r[0] == mat), 0) or 0
            results.append({
                'material_type': mat,
                'inward_qty': in_qty,
                'outward_qty': out_qty,
                'balance': in_qty - out_qty
            })
        data['results'] = results
        
    elif report_type == 'outstanding':
        parties = Party.query.all()
        results = []
        for party in parties:
            results.append({
                'party_name': party.name,
                'party_type': party.party_type,
                'outstanding': party.get_outstanding()
            })
        results.sort(key=lambda x: x['outstanding'], reverse=True)
        data['results'] = results
        
    elif report_type == 'daily':
        dates = set()
        
        inward_query = db.session.query(MaterialInward.date, db.func.sum(MaterialInward.quantity_mt).label('qty'), db.func.sum(MaterialInward.amount).label('amt'))
        outward_query = db.session.query(MaterialOutward.date, db.func.sum(MaterialOutward.quantity_mt).label('qty'), db.func.sum(MaterialOutward.amount).label('amt'))
        
        if from_d:
            inward_query = inward_query.filter(MaterialInward.date >= from_d)
            outward_query = outward_query.filter(MaterialOutward.date >= from_d)
        if to_d:
            inward_query = inward_query.filter(MaterialInward.date <= to_d)
            outward_query = outward_query.filter(MaterialOutward.date <= to_d)
            
        inward_totals = inward_query.group_by(MaterialInward.date).all()
        outward_totals = outward_query.group_by(MaterialOutward.date).all()
        
        for r in inward_totals:
            dates.add(r[0])
        for r in outward_totals:
            dates.add(r[0])
            
        results = []
        for d in sorted(list(dates)):
            in_row = next((r for r in inward_totals if r[0] == d), None)
            out_row = next((r for r in outward_totals if r[0] == d), None)
            results.append({
                'date': d,
                'inward_qty': in_row[1] if in_row else 0,
                'inward_amt': in_row[2] if in_row else 0,
                'outward_qty': out_row[1] if out_row else 0,
                'outward_amt': out_row[2] if out_row else 0
            })
        data['results'] = results
        
    elif report_type == 'party_wise' and party_id:
        party = Party.query.get(party_id)
        if party:
            inward_query = db.session.query(db.func.sum(MaterialInward.quantity_mt).label('qty'), db.func.sum(MaterialInward.amount).label('amt')).filter_by(party_id=party_id)
            outward_query = db.session.query(db.func.sum(MaterialOutward.quantity_mt).label('qty'), db.func.sum(MaterialOutward.amount).label('amt')).filter_by(party_id=party_id)
            payments_received_query = db.session.query(db.func.sum(Payment.amount)).filter_by(party_id=party_id, payment_type='received')
            payments_paid_query = db.session.query(db.func.sum(Payment.amount)).filter_by(party_id=party_id, payment_type='paid')
            
            if from_d:
                inward_query = inward_query.filter(MaterialInward.date >= from_d)
                outward_query = outward_query.filter(MaterialOutward.date >= from_d)
                payments_received_query = payments_received_query.filter(Payment.date >= from_d)
                payments_paid_query = payments_paid_query.filter(Payment.date >= from_d)
            if to_d:
                inward_query = inward_query.filter(MaterialInward.date <= to_d)
                outward_query = outward_query.filter(MaterialOutward.date <= to_d)
                payments_received_query = payments_received_query.filter(Payment.date <= to_d)
                payments_paid_query = payments_paid_query.filter(Payment.date <= to_d)
                
            inward_totals = inward_query.first()
            outward_totals = outward_query.first()
            payments_received = payments_received_query.scalar() or 0
            payments_paid = payments_paid_query.scalar() or 0
            
            data['summary'] = {
                'party_name': party.name,
                'total_inward_qty': inward_totals[0] or 0,
                'total_inward_amt': inward_totals[1] or 0,
                'total_outward_qty': outward_totals[0] or 0,
                'total_outward_amt': outward_totals[1] or 0,
                'total_received': payments_received,
                'total_paid': payments_paid,
                'outstanding': party.get_outstanding()
            }
            data['results'] = [data['summary']]
    
    return data

@bp.route('/')
@login_required
def index():
    report_type = request.args.get('report_type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    party_id = request.args.get('party_id')
    
    parties = Party.query.order_by(Party.name).all()
    
    data = {}
    if report_type:
        data = get_report_data(report_type, from_date, to_date, party_id)
        
    return render_template('reports/index.html', 
                           report_type=report_type, 
                           from_date=from_date, 
                           to_date=to_date, 
                           party_id=party_id,
                           parties=parties,
                           data=data)

@bp.route('/export')
@login_required
def export_csv():
    report_type = request.args.get('report_type')
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    party_id = request.args.get('party_id')
    
    data = get_report_data(report_type, from_date, to_date, party_id)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    if report_type == 'stock_summary' and 'results' in data:
        writer.writerow(['Material Type', 'Inward Qty (MT)', 'Outward Qty (MT)', 'Balance (MT)'])
        for row in data['results']:
            writer.writerow([row['material_type'], row['inward_qty'], row['outward_qty'], row['balance']])
            
    elif report_type == 'outstanding' and 'results' in data:
        writer.writerow(['Party Name', 'Party Type', 'Outstanding Amount'])
        for row in data['results']:
            writer.writerow([row['party_name'], row['party_type'].capitalize(), row['outstanding']])
            
    elif report_type == 'daily' and 'results' in data:
        writer.writerow(['Date', 'Inward Qty', 'Inward Amount', 'Outward Qty', 'Outward Amount'])
        for row in data['results']:
            writer.writerow([row['date'], row['inward_qty'], row['inward_amt'], row['outward_qty'], row['outward_amt']])
            
    elif report_type == 'party_wise' and 'summary' in data:
        s = data['summary']
        writer.writerow(['Party Name', 'Total Inward Qty', 'Total Inward Amount', 'Total Outward Qty', 'Total Outward Amount', 'Total Payments Received', 'Total Payments Paid', 'Outstanding Amount'])
        writer.writerow([s['party_name'], s['total_inward_qty'], s['total_inward_amt'], s['total_outward_qty'], s['total_outward_amt'], s['total_received'], s['total_paid'], s['outstanding']])
        
    response = Response(output.getvalue(), content_type='text/csv')
    response.headers["Content-Disposition"] = f"attachment; filename={report_type}_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    return response
