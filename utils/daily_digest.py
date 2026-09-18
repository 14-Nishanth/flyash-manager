import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)


def format_unit_qty(qty, unit):
    """Formats numeric quantity with appropriate decimal precision and unit label."""
    if not qty:
        return f"0 {unit or 'Units'}"
    u_str = (unit or 'Units').strip()
    u_lower = u_str.lower()
    if any(k in u_lower for k in ['piece', 'pcs', 'nos', 'unit', 'bag', 'load', 'trip']):
        return f"{qty:,.0f} {u_str}"
    return f"{qty:,.2f} {u_str}"


def build_daily_work_digest(target_date=None, app_base_url="http://localhost:5000"):
    """
    Builds a complete, executive daily plant work digest.
    Returns:
        telegram_html (str): Beautifully formatted HTML message for Telegram Bot.
        email_html (str): Polished responsive HTML email with styled tables.
        email_text (str): Clean plain-text version for email fallbacks.
        summary_dict (dict): Raw metric aggregates for API / UI responses.
    """
    from models import (
        Employee, Attendance, MaterialInward, MaterialOutward,
        JobWageEntry, Payment, Expense, Party, AlertSettings, db
    )

    target_date = target_date or date.today()
    date_str = target_date.strftime('%d %b %Y')
    day_name = target_date.strftime('%A')
    app_url = (app_base_url or 'http://localhost:5000').rstrip('/')

    settings = AlertSettings.query.first()
    owner_name = settings.owner_name if settings and settings.owner_name else 'Plant Owner'

    # 1. Attendance Metrics
    active_emps = Employee.query.filter_by(is_active=True).all()
    total_staff = len(active_emps)
    attendances = Attendance.query.filter_by(date=target_date).all()
    present_cnt = sum(1 for a in attendances if a.status == 'present')
    absent_cnt = sum(1 for a in attendances if a.status == 'absent')
    half_day_cnt = sum(1 for a in attendances if a.status == 'half-day')
    unmarked_cnt = max(0, total_staff - len(attendances))

    # 2. Production Piece-Rate Work
    all_jobs = JobWageEntry.query.filter_by(date=target_date).all()
    prod_jobs = [j for j in all_jobs if j.is_production]
    load_jobs = [j for j in all_jobs if j.is_outward]

    prod_by_product = {}
    total_trays = 0.0
    total_gross_pcs = 0.0
    total_waste_pcs = 0.0
    total_net_pcs = 0.0
    total_prod_wages = 0.0

    for j in prod_jobs:
        p_name = j.product_name or 'Brick Production'
        if p_name not in prod_by_product:
            prod_by_product[p_name] = {
                'trays': 0.0,
                'gross': 0.0,
                'waste': 0.0,
                'net': 0.0,
                'wages': 0.0,
                'unit': j.unit or 'Pcs'
            }
        g_qty = j.gross_quantity if (j.gross_quantity and j.gross_quantity > 0) else j.quantity
        w_qty = j.total_wastage or 0.0
        n_qty = j.quantity or (g_qty - w_qty)
        prod_by_product[p_name]['trays'] += (j.tray_count or 0.0)
        prod_by_product[p_name]['gross'] += g_qty
        prod_by_product[p_name]['waste'] += w_qty
        prod_by_product[p_name]['net'] += n_qty
        prod_by_product[p_name]['wages'] += (j.total_amount or 0.0)

        total_trays += (j.tray_count or 0.0)
        total_gross_pcs += g_qty
        total_waste_pcs += w_qty
        total_net_pcs += n_qty
        total_prod_wages += (j.total_amount or 0.0)

    # 3. Material Outward & Sales Dispatches (Categorized by Party & Material with exact units)
    outward_entries = MaterialOutward.query.filter_by(date=target_date).all()
    total_outward_amount = sum(e.amount for e in outward_entries if e.amount) or 0.0
    outward_by_party = {}
    for e in outward_entries:
        p_name = e.party.name if e.party else 'Walk-in / Unassigned Customer'
        if p_name not in outward_by_party:
            outward_by_party[p_name] = []
        outward_by_party[p_name].append({
            'material': e.material_type,
            'qty': e.quantity_mt,
            'unit': e.quantity_unit or 'Ton',
            'rate': e.rate or 0.0,
            'amount': e.amount or 0.0,
            'vehicle': e.vehicle_no or '-'
        })

    # 4. Material Inward & Raw Material Receipts (Categorized by Supplier)
    inward_entries = MaterialInward.query.filter_by(date=target_date).all()
    total_inward_amount = sum(e.amount for e in inward_entries if e.amount) or 0.0
    inward_by_supplier = {}
    for e in inward_entries:
        s_name = e.party.name if e.party else 'Unassigned Supplier'
        if s_name not in inward_by_supplier:
            inward_by_supplier[s_name] = []
        inward_by_supplier[s_name].append({
            'material': e.material_type,
            'qty': e.quantity_mt,
            'unit': e.quantity_unit or 'Ton',
            'rate': e.rate or 0.0,
            'amount': e.amount or 0.0,
            'vehicle': e.vehicle_no or '-'
        })

    # 5. Loading & Unloading Labor Work
    total_load_wages = sum(j.total_amount for j in load_jobs) or 0.0
    load_jobs_summary = []
    for j in load_jobs:
        p_name = j.party.name if j.party else 'Unassigned Party'
        status_label = '🟢 Received' if j.payment_status == 'received' else ('🟡 Due' if j.payment_status == 'pending' else 'N/A')
        load_jobs_summary.append({
            'job_type': j.job_type,
            'product': j.product_name,
            'qty': j.quantity,
            'unit': j.unit or 'Pcs',
            'wage': j.total_amount,
            'vehicle': j.vehicle_no or '-',
            'party': p_name,
            'status': status_label
        })

    # 6. Financial Collections, Supplier Payments & Expenses
    payments_received = Payment.query.filter_by(date=target_date, payment_type='received').all()
    total_rec_amt = sum(p.amount for p in payments_received) or 0.0
    
    payments_paid = Payment.query.filter_by(date=target_date, payment_type='paid').all()
    total_paid_amt = sum(p.amount for p in payments_paid) or 0.0

    expenses = Expense.query.filter_by(date=target_date).all()
    total_expense_amt = sum(exp.amount for exp in expenses) or 0.0

    # ─────────────────────────────────────────────────────────────
    # BUILD TELEGRAM HTML MESSAGE
    # ─────────────────────────────────────────────────────────────
    tg_lines = [
        f"📊 <b>DAILY WORK & OPERATIONS DIGEST</b> 🏭",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 <b>Date:</b> {date_str} ({day_name})",
        f"👤 <b>Manager/Owner:</b> {owner_name}",
        f"🌐 <a href='{app_url}/'>Open FlyAsh Manager</a>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]

    # Attendance
    tg_lines.append(f"👥 <b>STAFF ATTENDANCE ({total_staff} Enrolled)</b>")
    tg_lines.append(f"  • ✅ Present: <b>{present_cnt}</b>  |  ❌ Absent: <b>{absent_cnt}</b>  |  🌓 Half-day: <b>{half_day_cnt}</b>")
    if unmarked_cnt > 0:
        tg_lines.append(f"  • ⚠️ Unmarked: <b>{unmarked_cnt}</b>")
    tg_lines.append("")

    # Production
    if prod_by_product:
        tg_lines.append(f"🧱 <b>DAILY PRODUCTION SUMMARY</b>")
        for p_name, p_data in prod_by_product.items():
            tg_lines.append(
                f"  • <b>{p_name}:</b> {p_data['gross']:,.0f} produced ({p_data['trays']:,.0f} trays, {p_data['waste']:,.0f} waste cut) ➔ <b>{p_data['net']:,.0f} {p_data['unit']}</b> (Labor: ₹{p_data['wages']:,.2f})"
            )
        tg_lines.append(f"  ➔ <b>Total Output:</b> {total_gross_pcs:,.0f} Gross Pcs | <b>Wages:</b> ₹{total_prod_wages:,.2f}\n")
    else:
        tg_lines.append("🧱 <b>DAILY PRODUCTION:</b> <i>No production logged today</i>\n")

    # Outward Dispatches (with customer & specific units like Units for Dust)
    if outward_by_party:
        tg_lines.append(f"🚛 <b>MATERIAL OUTWARD / SALES DISPATCHES</b>")
        for p_name, items in outward_by_party.items():
            tg_lines.append(f"  🏢 <b>{p_name}:</b>")
            for item in items:
                qty_str = format_unit_qty(item['qty'], item['unit'])
                veh_str = f" [Veh: {item['vehicle']}]" if item['vehicle'] != '-' else ""
                tg_lines.append(f"     • {item['material']}: <b>{qty_str}</b> @ ₹{item['rate']:,.2f} = <b>₹{item['amount']:,.2f}</b>{veh_str}")
        tg_lines.append(f"  ➔ <b>Total Outward Sales: ₹{total_outward_amount:,.2f}</b> across {len(outward_entries)} dispatches\n")
    else:
        tg_lines.append("🚛 <b>MATERIAL OUTWARD:</b> <i>No dispatches logged today</i>\n")

    # Inward Receipts
    if inward_by_supplier:
        tg_lines.append(f"📥 <b>RAW MATERIAL INWARD / PURCHASES</b>")
        for s_name, items in inward_by_supplier.items():
            tg_lines.append(f"  🏭 <b>{s_name}:</b>")
            for item in items:
                qty_str = format_unit_qty(item['qty'], item['unit'])
                veh_str = f" [Veh: {item['vehicle']}]" if item['vehicle'] != '-' else ""
                tg_lines.append(f"     • {item['material']}: <b>{qty_str}</b> @ ₹{item['rate']:,.2f} = <b>₹{item['amount']:,.2f}</b>{veh_str}")
        tg_lines.append(f"  ➔ <b>Total Inward Purchases: ₹{total_inward_amount:,.2f}</b> across {len(inward_entries)} receipts\n")
    else:
        tg_lines.append("📥 <b>MATERIAL INWARD:</b> <i>No raw materials received today</i>\n")

    # Loading / Unloading
    if load_jobs_summary:
        tg_lines.append(f"👷 <b>VEHICLE LOADING & UNLOADING WAGES</b>")
        for lj in load_jobs_summary[:5]:
            tg_lines.append(f"  • {lj['product']} ({format_unit_qty(lj['qty'], lj['unit'])}) | {lj['party']} | Wage: ₹{lj['wage']:,.2f} [{lj['status']}]")
        if len(load_jobs_summary) > 5:
            tg_lines.append(f"  • ...and {len(load_jobs_summary) - 5} more loading jobs")
        tg_lines.append(f"  ➔ <b>Total Loading Wages: ₹{total_load_wages:,.2f}</b>\n")

    # Financials & Collections
    tg_lines.append(f"💰 <b>FINANCIAL & CASH SUMMARY</b>")
    tg_lines.append(f"  • 🟢 Collections / Money Received: <b>₹{total_rec_amt:,.2f}</b> ({len(payments_received)} payments)")
    tg_lines.append(f"  • 🔴 Supplier Payments Made: <b>₹{total_paid_amt:,.2f}</b> ({len(payments_paid)} payments)")
    tg_lines.append(f"  • ⛽ Operational Expenses: <b>₹{total_expense_amt:,.2f}</b> ({len(expenses)} bills)")
    tg_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    tg_lines.append(f"<i>Auto-generated daily operations digest • FlyAsh Manager ERP</i>")

    telegram_html = "\n".join(tg_lines)

    # ─────────────────────────────────────────────────────────────
    # BUILD EMAIL HTML TEMPLATE
    # ─────────────────────────────────────────────────────────────
    outward_rows_html = ""
    if outward_by_party:
        for p_name, items in outward_by_party.items():
            for it in items:
                outward_rows_html += f"""
                <tr>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #1e293b;">{p_name}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; color: #334155;">{it['material']}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #0284c7;">{format_unit_qty(it['qty'], it['unit'])}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #475569;">₹{it['rate']:,.2f}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #16a34a;">₹{it['amount']:,.2f}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-family: monospace; color: #64748b;">{it['vehicle']}</td>
                </tr>
                """
    else:
        outward_rows_html = "<tr><td colspan='6' style='padding: 12px; text-align: center; color: #94a3b8;'>No outward dispatches recorded today</td></tr>"

    inward_rows_html = ""
    if inward_by_supplier:
        for s_name, items in inward_by_supplier.items():
            for it in items:
                inward_rows_html += f"""
                <tr>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #1e293b;">{s_name}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; color: #334155;">{it['material']}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #16a34a;">{format_unit_qty(it['qty'], it['unit'])}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #475569;">₹{it['rate']:,.2f}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #dc2626;">₹{it['amount']:,.2f}</td>
                    <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-family: monospace; color: #64748b;">{it['vehicle']}</td>
                </tr>
                """
    else:
        inward_rows_html = "<tr><td colspan='6' style='padding: 12px; text-align: center; color: #94a3b8;'>No raw material receipts recorded today</td></tr>"

    prod_rows_html = ""
    if prod_by_product:
        for p_name, p_data in prod_by_product.items():
            prod_rows_html += f"""
            <tr>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; font-weight: 600; color: #1e293b;">{p_name}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #475569;">{p_data['trays']:,.0f}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #0284c7;">{p_data['gross']:,.0f}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; color: #ef4444;">{p_data['waste']:,.0f}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #16a34a;">{p_data['net']:,.0f} {p_data['unit']}</td>
                <td style="padding: 8px 12px; border-bottom: 1px solid #e2e8f0; text-align: right; font-weight: bold; color: #d97706;">₹{p_data['wages']:,.2f}</td>
            </tr>
            """
    else:
        prod_rows_html = "<tr><td colspan='6' style='padding: 12px; text-align: center; color: #94a3b8;'>No production recorded today</td></tr>"

    email_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Plant Work Digest - {date_str}</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; color: #1e293b; margin: 0; padding: 20px;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); border: 1px solid #e2e8f0;">
            
            <!-- Header -->
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); padding: 24px 28px; color: #ffffff;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h2 style="margin: 0; font-size: 22px; font-weight: 700; color: #38bdf8;">🏭 FlyAsh Plant Daily Digest</h2>
                        <p style="margin: 4px 0 0 0; font-size: 14px; color: #94a3b8;">{date_str} ({day_name}) &bull; Prepared for {owner_name}</p>
                    </div>
                </div>
            </div>

            <div style="padding: 24px 28px;">

                <!-- Key Metric Cards -->
                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 24px;">
                    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px;">
                        <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #166534;">Outward Sales Revenue</div>
                        <div style="font-size: 20px; font-weight: bold; color: #15803d; margin-top: 4px;">₹{total_outward_amount:,.2f}</div>
                        <div style="font-size: 12px; color: #4ade80;">{len(outward_entries)} dispatches</div>
                    </div>
                    <div style="background-color: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 14px;">
                        <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #1e40af;">Production Volume</div>
                        <div style="font-size: 20px; font-weight: bold; color: #1d4ed8; margin-top: 4px;">{total_gross_pcs:,.0f} Pcs</div>
                        <div style="font-size: 12px; color: #60a5fa;">{total_trays:,.0f} Trays (₹{total_prod_wages:,.2f} wages)</div>
                    </div>
                    <div style="background-color: #fefce8; border: 1px solid #fef08a; border-radius: 8px; padding: 14px;">
                        <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #854d0e;">Collections & Received</div>
                        <div style="font-size: 20px; font-weight: bold; color: #a16207; margin-top: 4px;">₹{total_rec_amt:,.2f}</div>
                        <div style="font-size: 12px; color: #eab308;">{len(payments_received)} payments</div>
                    </div>
                    <div style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 14px;">
                        <div style="font-size: 11px; text-transform: uppercase; font-weight: bold; color: #991b1b;">Expenses & Purchases</div>
                        <div style="font-size: 20px; font-weight: bold; color: #b91c1c; margin-top: 4px;">₹{(total_inward_amount + total_expense_amt):,.2f}</div>
                        <div style="font-size: 12px; color: #f87171;">Raw: ₹{total_inward_amount:,.2f} | Exp: ₹{total_expense_amt:,.2f}</div>
                    </div>
                </div>

                <!-- Staff Attendance -->
                <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px;">
                    <div style="font-size: 13px; font-weight: bold; color: #475569; text-transform: uppercase; margin-bottom: 8px;">
                        👥 Workforce Attendance ({total_staff} Active Staff)
                    </div>
                    <div style="font-size: 14px; color: #334155;">
                        <span style="display: inline-block; margin-right: 16px;">✅ Present: <strong>{present_cnt}</strong></span>
                        <span style="display: inline-block; margin-right: 16px;">❌ Absent: <strong>{absent_cnt}</strong></span>
                        <span style="display: inline-block; margin-right: 16px;">🌓 Half-Day: <strong>{half_day_cnt}</strong></span>
                        {"<span style='display: inline-block; color: #e11d48;'>⚠️ Unmarked: <strong>" + str(unmarked_cnt) + "</strong></span>" if unmarked_cnt > 0 else ""}
                    </div>
                </div>

                <!-- Production Table -->
                <div style="margin-bottom: 24px;">
                    <h3 style="font-size: 15px; font-weight: bold; color: #0f172a; margin: 0 0 10px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
                        🧱 Finished Goods Production
                    </h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #f1f5f9; color: #475569; text-align: left;">
                                <th style="padding: 8px 12px;">Product</th>
                                <th style="padding: 8px 12px; text-align: right;">Trays</th>
                                <th style="padding: 8px 12px; text-align: right;">Gross Pcs</th>
                                <th style="padding: 8px 12px; text-align: right;">Wastage</th>
                                <th style="padding: 8px 12px; text-align: right;">Net Payable</th>
                                <th style="padding: 8px 12px; text-align: right;">Labor Wages</th>
                            </tr>
                        </thead>
                        <tbody>
                            {prod_rows_html}
                        </tbody>
                    </table>
                </div>

                <!-- Outward Dispatches Table -->
                <div style="margin-bottom: 24px;">
                    <h3 style="font-size: 15px; font-weight: bold; color: #0f172a; margin: 0 0 10px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
                        🚛 Material Outward & Sales Dispatches
                    </h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #f1f5f9; color: #475569; text-align: left;">
                                <th style="padding: 8px 12px;">Customer</th>
                                <th style="padding: 8px 12px;">Material</th>
                                <th style="padding: 8px 12px; text-align: right;">Quantity & Unit</th>
                                <th style="padding: 8px 12px; text-align: right;">Rate</th>
                                <th style="padding: 8px 12px; text-align: right;">Amount</th>
                                <th style="padding: 8px 12px;">Vehicle</th>
                            </tr>
                        </thead>
                        <tbody>
                            {outward_rows_html}
                        </tbody>
                    </table>
                </div>

                <!-- Inward Receipts Table -->
                <div style="margin-bottom: 24px;">
                    <h3 style="font-size: 15px; font-weight: bold; color: #0f172a; margin: 0 0 10px 0; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">
                        📥 Raw Material Inward Receipts
                    </h3>
                    <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                        <thead>
                            <tr style="background-color: #f1f5f9; color: #475569; text-align: left;">
                                <th style="padding: 8px 12px;">Supplier</th>
                                <th style="padding: 8px 12px;">Material</th>
                                <th style="padding: 8px 12px; text-align: right;">Quantity & Unit</th>
                                <th style="padding: 8px 12px; text-align: right;">Rate</th>
                                <th style="padding: 8px 12px; text-align: right;">Amount</th>
                                <th style="padding: 8px 12px;">Vehicle</th>
                            </tr>
                        </thead>
                        <tbody>
                            {inward_rows_html}
                        </tbody>
                    </table>
                </div>

                <!-- Footer & Dashboard Link -->
                <div style="text-align: center; padding-top: 16px; border-top: 1px solid #e2e8f0;">
                    <a href="{app_url}/" style="display: inline-block; background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 10px 22px; border-radius: 6px; font-weight: 600; font-size: 14px;">
                        Open FlyAsh Manager Dashboard &rarr;
                    </a>
                    <p style="margin: 12px 0 0 0; font-size: 12px; color: #94a3b8;">
                        Automated Daily Digest &bull; FlyAsh Management System
                    </p>
                </div>

            </div>
        </div>
    </body>
    </html>
    """

    email_text = f"""FLYASH PLANT DAILY OPERATIONS DIGEST - {date_str}
Prepared for: {owner_name}

=== STAFF ATTENDANCE ===
Total Active: {total_staff} | Present: {present_cnt} | Absent: {absent_cnt} | Half-Day: {half_day_cnt}

=== PRODUCTION SUMMARY ===
Total Gross Output: {total_gross_pcs:,.0f} Pcs ({total_trays:,.0f} trays)
Wastage Cut: {total_waste_pcs:,.0f} Pcs | Net Pieces: {total_net_pcs:,.0f} Pcs
Total Production Labor Wages: INR {total_prod_wages:,.2f}

=== MATERIAL OUTWARD (SALES) ===
Total Outward Revenue: INR {total_outward_amount:,.2f} ({len(outward_entries)} dispatches)

=== MATERIAL INWARD (PURCHASES) ===
Total Inward Cost: INR {total_inward_amount:,.2f} ({len(inward_entries)} receipts)

=== FINANCIAL COLLECTIONS & PAYMENTS ===
Collections Received: INR {total_rec_amt:,.2f}
Supplier Payments: INR {total_paid_amt:,.2f}
Operational Expenses: INR {total_expense_amt:,.2f}

Dashboard URL: {app_url}/
"""

    summary_dict = {
        'date': date_str,
        'attendance': {'total': total_staff, 'present': present_cnt, 'absent': absent_cnt, 'half_day': half_day_cnt},
        'production': {'gross_pieces': total_gross_pcs, 'net_pieces': total_net_pcs, 'wages': total_prod_wages},
        'outward': {'amount': total_outward_amount, 'count': len(outward_entries)},
        'inward': {'amount': total_inward_amount, 'count': len(inward_entries)},
        'financials': {'received': total_rec_amt, 'paid': total_paid_amt, 'expenses': total_expense_amt}
    }

    return telegram_html, email_html, email_text, summary_dict


def send_daily_digest(target_date=None, channel=None, recipient_email=None, app_base_url="http://localhost:5000"):
    """
    Dispatches the daily work digest via Telegram, Email, or Both.
    Returns:
        dict: {'telegram': (success, msg), 'email': (success, msg)}
    """
    from models import AlertSettings, db
    from utils.telegram_service import send_telegram_message

    target_date = target_date or date.today()
    settings = AlertSettings.query.first()

    chosen_channel = channel or (settings.daily_digest_channel if settings else 'both')
    target_email = recipient_email or (settings.daily_digest_email if settings and settings.daily_digest_email else (settings.owner_email if settings else 'admin@flyash.local'))

    telegram_html, email_html, email_text, summary_dict = build_daily_work_digest(target_date, app_base_url)

    results = {
        'telegram': (False, 'Not requested'),
        'email': (False, 'Not requested')
    }

    # 1. Dispatch Telegram
    if chosen_channel in ('telegram', 'both'):
        try:
            tg_token = settings.get_telegram_token() if settings else None
            tg_chat = settings.get_telegram_chat_id() if settings else None
            ok, res = send_telegram_message(telegram_html, bot_token=tg_token, chat_id=tg_chat)
            results['telegram'] = (ok, res if isinstance(res, str) else "Telegram digest sent successfully!")
        except Exception as e:
            results['telegram'] = (False, f"Telegram error: {str(e)}")

    # 2. Dispatch Email
    if chosen_channel in ('email', 'both'):
        try:
            smtp_host = settings.smtp_host if settings and settings.smtp_host else 'smtp.gmail.com'
            smtp_port = settings.smtp_port if settings and settings.smtp_port else 587
            smtp_user = settings.smtp_user if settings and settings.smtp_user else ''
            smtp_password = settings.get_decrypted_smtp_password() if settings else ''

            if smtp_user and smtp_password:
                msg = MIMEMultipart('alternative')
                msg['Subject'] = f"📊 Daily Plant Work Digest - {target_date.strftime('%d %b %Y')} - FlyAsh Manager"
                msg['From'] = smtp_user
                msg['To'] = target_email

                part1 = MIMEText(email_text, 'plain')
                part2 = MIMEText(email_html, 'html')
                msg.attach(part1)
                msg.attach(part2)

                with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
                    server.starttls()
                    server.login(smtp_user, smtp_password)
                    server.sendmail(smtp_user, target_email, msg.as_string())

                results['email'] = (True, f"HTML Email digest sent successfully to {target_email}!")
            else:
                results['email'] = (True, f"Email notification queued for {target_email} (Configure SMTP credentials under Alert Settings to send live emails)")
        except Exception as e:
            results['email'] = (False, f"SMTP Email error: {str(e)}")

    # Update last_digest_sent_date
    if settings:
        try:
            settings.last_digest_sent_date = target_date
            db.session.commit()
        except Exception:
            db.session.rollback()

    return results
