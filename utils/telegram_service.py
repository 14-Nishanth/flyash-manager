import threading
import requests
import json
import logging
from datetime import datetime, date, timedelta
from flask import current_app

logger = logging.getLogger(__name__)


def send_telegram_message(message_text, bot_token=None, chat_id=None):
    """
    Sends a formatted HTML message to Telegram via Bot API.
    Returns (True, response_data) on success or (False, error_message) on failure.
    """
    from models import AlertSettings

    if not bot_token or not chat_id:
        settings = AlertSettings.query.first()
        if settings:
            bot_token = bot_token or settings.get_telegram_token()
            chat_id = chat_id or settings.get_telegram_chat_id()

    if not bot_token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is not configured."

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=12)
        res_json = response.json()
        if response.status_code == 200 and res_json.get("ok"):
            return True, res_json
        else:
            err = res_json.get("description", f"HTTP {response.status_code}")
            return False, err
    except Exception as e:
        return False, str(e)


def build_morning_reminder(app_base_url="http://localhost:5000"):
    """
    Builds the morning 7:00 AM attendance & work start reminder message.
    """
    from models import Employee, EmployeeGroup
    today = date.today()
    date_str = today.strftime('%d %b %Y')
    day_name = today.strftime('%A')

    active_emps = Employee.query.filter_by(is_active=True).all()
    active_groups = EmployeeGroup.query.count()

    attendance_link = f"{app_base_url.rstrip('/')}/employees/attendance"
    production_link = f"{app_base_url.rstrip('/')}/stock/production"

    worker_list_preview = ""
    for idx, e in enumerate(active_emps[:8], 1):
        worker_list_preview += f"  • {e.name} ({e.role or 'Worker'})\n"
    if len(active_emps) > 8:
        worker_list_preview += f"  • ...and {len(active_emps) - 8} more workers\n"

    if not worker_list_preview:
        worker_list_preview = "  (No active employees enrolled)\n"

    msg = (
        f"☀️ <b>GOOD MORNING! PLANT WORK & ATTENDANCE REMINDER</b> ☀️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {date_str} ({day_name})\n"
        f"⏰ <b>Time:</b> 7:00 AM Shift Start\n"
        f"🏭 <b>Plant:</b> FlyAsh Brick & Block Manufacturing Unit\n\n"
        f"👥 <b>Active Workforce ({len(active_emps)} Staff, {active_groups} Gangs):</b>\n"
        f"{worker_list_preview}\n"
        f"📋 <b>Shift Action Checklist:</b>\n"
        f" 1️⃣ Mark Worker Attendance: <a href='{attendance_link}'>Click to Mark Attendance</a>\n"
        f" 2️⃣ Or reply <code>/present_all</code> to this bot to mark all present!\n"
        f" 3️⃣ Check Raw Material Silos (Fly Ash, Cement, Sand, Aggregate)\n"
        f" 4️⃣ Start Batching Plant & Log Production: <a href='{production_link}'>Production Entry</a>\n\n"
        f"💬 <b>Quick Bot Commands:</b>\n"
        f"• <code>/present_all</code> - Mark all active staff present\n"
        f"• <code>/attendance</code> - View live attendance status\n"
        f"• <code>/status</code> - Today's complete plant overview\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Have a safe and productive manufacturing day! 🧱</i>"
    )
    return msg


def build_evening_reminder(app_base_url="http://localhost:5000", target_date=None):
    """
    Builds the evening 7:00 PM work completion, production tally & attendance summary message.
    """
    from models import Employee, Attendance, MaterialInward, MaterialOutward, JobWageEntry, db

    target_date = target_date or date.today()
    date_str = target_date.strftime('%d %b %Y')
    day_name = target_date.strftime('%A')

    # Attendance stats
    all_emps = Employee.query.filter_by(is_active=True).all()
    total_workers = len(all_emps)
    attendances = Attendance.query.filter_by(date=target_date).all()
    
    present_cnt = sum(1 for a in attendances if a.status == 'present')
    absent_cnt = sum(1 for a in attendances if a.status == 'absent')
    half_day_cnt = sum(1 for a in attendances if a.status == 'half-day')
    unmarked_cnt = max(0, total_workers - len(attendances))

    # Production & outward jobs
    prod_jobs = JobWageEntry.query.filter_by(date=target_date).filter(
        JobWageEntry.job_type.like('%Production%')
    ).all()
    outward_jobs = JobWageEntry.query.filter_by(date=target_date).filter(
        ~JobWageEntry.job_type.like('%Production%')
    ).all()

    total_trays = sum(j.tray_count or 0.0 for j in prod_jobs)
    total_bricks = sum((j.gross_quantity or j.quantity or 0.0) for j in prod_jobs)
    prod_wages = sum(j.total_amount or 0.0 for j in prod_jobs)
    outward_wages = sum(j.total_amount or 0.0 for j in outward_jobs)
    total_wages = prod_wages + outward_wages

    # Material movements
    inward_entries = MaterialInward.query.filter_by(date=target_date).all()
    inward_qty = sum(e.quantity_mt for e in inward_entries)
    inward_amt = sum(e.amount for e in inward_entries)

    outward_entries = MaterialOutward.query.filter_by(date=target_date).all()
    outward_qty = sum(e.quantity_mt for e in outward_entries)
    outward_amt = sum(e.amount for e in outward_entries)

    attendance_link = f"{app_base_url.rstrip('/')}/employees/attendance?date={target_date.strftime('%Y-%m-%d')}"
    wages_link = f"{app_base_url.rstrip('/')}/employees/wages?from_date={target_date.strftime('%Y-%m-%d')}&to_date={target_date.strftime('%Y-%m-%d')}"
    dashboard_link = f"{app_base_url.rstrip('/')}/"

    msg = (
        f"🌙 <b>EVENING PLANT WORK COMPLETE & ATTENDANCE SUMMARY</b> 🌙\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {date_str} ({day_name})\n"
        f"⏰ <b>Time:</b> 7:00 PM Shift Close\n"
        f"🏭 <b>Plant:</b> FlyAsh Brick & Block Manufacturing Unit\n\n"
        f"👷 <b>Worker Attendance Summary:</b>\n"
        f"  • Total Active Staff: <b>{total_workers}</b>\n"
        f"  • ✅ Present: <b>{present_cnt}</b>\n"
        f"  • ❌ Absent: <b>{absent_cnt}</b>\n"
        f"  • 🌓 Half-Day: <b>{half_day_cnt}</b>\n"
        f"  • ⚠️ Unmarked: <b>{unmarked_cnt}</b>\n\n"
        f"🧱 <b>Today's Production & Wage Output:</b>\n"
        f"  • Total Trays Pressed: <b>{total_trays:,.0f} Trays</b>\n"
        f"  • Bricks / Blocks Produced: <b>{total_bricks:,.0f} Pieces</b>\n"
        f"  • 🔨 Production Wages: <b>₹{prod_wages:,.2f}</b>\n"
        f"  • 🚚 Loading / Dispatch Wages: <b>₹{outward_wages:,.2f}</b>\n"
        f"  • 💰 Total Daily Wages: <b>₹{total_wages:,.2f}</b>\n\n"
        f"🚛 <b>Material Logistics:</b>\n"
        f"  • Inward Purchases: <b>{inward_qty:,.2f} MT</b> (₹{inward_amt:,.2f} across {len(inward_entries)} trips)\n"
        f"  • Outward Sales: <b>{outward_qty:,.2f} MT</b> (₹{outward_amt:,.2f} across {len(outward_entries)} dispatches)\n\n"
        f"🔗 <b>Quick ERP Links:</b>\n"
        f"• <a href='{attendance_link}'>Review Attendance Register</a>\n"
        f"• <a href='{wages_link}'>View Daily Wages & Salary Sheet</a>\n"
        f"• <a href='{dashboard_link}'>Open Live Plant Dashboard</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Daily shift logs successfully closed and recorded. 🏭✨</i>"
    )
    return msg


def handle_telegram_command(text, chat_id, host_url="http://localhost:5000"):
    """
    Handles interactive commands received from Telegram webhook.
    Supported commands:
      /start, /help - Show available commands
      /present_all or 'all present' - Mark all active employees present today
      /attendance - Show live attendance count
      /wages - Show today's production & loading wages
      /status or /today - Daily overview
      /morning - Morning reminder
      /evening - Evening reminder
    """
    cmd = (text or "").strip().lower()
    from models import db, Employee, Attendance, JobWageEntry, MaterialInward, MaterialOutward
    today = date.today()

    if cmd in ['/start', '/help', 'help']:
        reply = (
            "🤖 <b>FlyAsh ERP Bot Assistant</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "Available Commands:\n"
            "• <code>/present_all</code> - Mark all active workers Present today\n"
            "• <code>/attendance</code> - View today's attendance summary\n"
            "• <code>/wages</code> - Today's production & loading wages\n"
            "• <code>/status</code> - Today's full plant activity status\n"
            "• <code>/morning</code> - Send 7:00 AM Morning Shift Start reminder\n"
            "• <code>/evening</code> - Send 7:00 PM Evening Shift Recap summary\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_message(reply, chat_id=chat_id)
        return True, reply

    elif cmd in ['/present_all', 'all present', 'present all']:
        active_emps = Employee.query.filter_by(is_active=True).all()
        count = 0
        try:
            for emp in active_emps:
                att = Attendance.query.filter_by(employee_id=emp.id, date=today).first()
                if att:
                    att.status = 'present'
                else:
                    att = Attendance(
                        employee_id=emp.id,
                        date=today,
                        status='present',
                        notes='Marked present via Telegram Bot'
                    )
                    db.session.add(att)
                count += 1
            db.session.commit()
            reply = f"✅ <b>Attendance Marked!</b> All <b>{count} active workers</b> marked PRESENT for today ({today.strftime('%d %b %Y')})."
        except Exception as e:
            db.session.rollback()
            reply = f"❌ Error marking attendance: {str(e)}"
        
        send_telegram_message(reply, chat_id=chat_id)
        return True, reply

    elif cmd in ['/attendance', 'attendance']:
        all_emps = Employee.query.filter_by(is_active=True).all()
        total_workers = len(all_emps)
        attendances = Attendance.query.filter_by(date=today).all()
        
        present_cnt = sum(1 for a in attendances if a.status == 'present')
        absent_cnt = sum(1 for a in attendances if a.status == 'absent')
        half_day_cnt = sum(1 for a in attendances if a.status == 'half-day')
        unmarked_cnt = max(0, total_workers - len(attendances))

        reply = (
            f"📋 <b>Attendance Status for {today.strftime('%d %b %Y')}:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 Total Active Workers: <b>{total_workers}</b>\n"
            f"✅ Present: <b>{present_cnt}</b>\n"
            f"❌ Absent: <b>{absent_cnt}</b>\n"
            f"🌓 Half-Day: <b>{half_day_cnt}</b>\n"
            f"⚠️ Unmarked: <b>{unmarked_cnt}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Tip: Send <code>/present_all</code> to mark all as present."
        )
        send_telegram_message(reply, chat_id=chat_id)
        return True, reply

    elif cmd in ['/wages', 'wages', 'wage']:
        prod_jobs = JobWageEntry.query.filter_by(date=today).filter(JobWageEntry.job_type.like('%Production%')).all()
        outward_jobs = JobWageEntry.query.filter_by(date=today).filter(~JobWageEntry.job_type.like('%Production%')).all()

        total_trays = sum(j.tray_count or 0.0 for j in prod_jobs)
        total_bricks = sum((j.gross_quantity or j.quantity or 0.0) for j in prod_jobs)
        prod_wages = sum(j.total_amount or 0.0 for j in prod_jobs)
        outward_wages = sum(j.total_amount or 0.0 for j in outward_jobs)
        total_wages = prod_wages + outward_wages

        reply = (
            f"💰 <b>Today's Wage & Production Breakdown ({today.strftime('%d %b %Y')}):</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🧱 Production Volume: <b>{total_trays:,.0f} Trays</b> ({total_bricks:,.0f} Pcs)\n"
            f"🔨 Production Wages: <b>₹{prod_wages:,.2f}</b>\n"
            f"🚚 Loading / Dispatch Wages: <b>₹{outward_wages:,.2f}</b>\n"
            f"💵 <b>Total Wages Today: ₹{total_wages:,.2f}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        send_telegram_message(reply, chat_id=chat_id)
        return True, reply

    elif cmd in ['/status', '/today', 'status', 'today']:
        msg = build_evening_reminder(app_base_url=host_url, target_date=today)
        send_telegram_message(msg, chat_id=chat_id)
        return True, msg

    elif cmd in ['/morning', 'morning']:
        msg = build_morning_reminder(app_base_url=host_url)
        send_telegram_message(msg, chat_id=chat_id)
        return True, msg

    elif cmd in ['/evening', 'evening']:
        msg = build_evening_reminder(app_base_url=host_url, target_date=today)
        send_telegram_message(msg, chat_id=chat_id)
        return True, msg

    else:
        reply = (
            f"❓ Unknown command: <code>{text}</code>\n"
            f"Send <code>/help</code> to see all available commands (such as <code>/present_all</code>, <code>/attendance</code>, <code>/wages</code>, <code>/status</code>)."
        )
        send_telegram_message(reply, chat_id=chat_id)
        return True, reply


def check_and_send_scheduled_reminders(app):
    """
    Background worker loop called periodically to check if current time matches
    the 7:00 AM (Morning) or 7:00 PM (Evening) scheduled reminder times.
    """
    import time
    with app.app_context():
        from models import AlertSettings
        
        last_morning_sent_date = None
        last_evening_sent_date = None

        while True:
            try:
                now = datetime.now()
                current_time_str = now.strftime('%H:%M')
                today_date = now.date()

                settings = AlertSettings.query.first()
                if settings:
                    bot_token = settings.get_telegram_token()
                    chat_id = settings.get_telegram_chat_id()

                    if bot_token and chat_id:
                        # 1. Morning Reminder (Default 07:00)
                        morning_time = (settings.telegram_morning_reminder_time or '07:00').strip()
                        if settings.telegram_morning_reminder_enabled and current_time_str == morning_time:
                            if last_morning_sent_date != today_date:
                                logger.info(f"Triggering scheduled 7 AM Morning Reminder to Telegram at {current_time_str}")
                                msg = build_morning_reminder()
                                success, _ = send_telegram_message(msg, bot_token=bot_token, chat_id=chat_id)
                                if success:
                                    last_morning_sent_date = today_date

                        # 2. Evening Reminder (Default 19:00)
                        evening_time = (settings.telegram_evening_reminder_time or '19:00').strip()
                        if settings.telegram_evening_reminder_enabled and current_time_str == evening_time:
                            if last_evening_sent_date != today_date:
                                logger.info(f"Triggering scheduled 7 PM Evening Reminder to Telegram at {current_time_str}")
                                msg = build_evening_reminder(target_date=today_date)
                                success, _ = send_telegram_message(msg, bot_token=bot_token, chat_id=chat_id)
                                if success:
                                    last_evening_sent_date = today_date

            except Exception as e:
                logger.error(f"Error in Telegram reminder background scheduler: {e}")

            time.sleep(30)


def start_telegram_scheduler(app):
    """Starts the Telegram reminder background loop daemon thread."""
    t = threading.Thread(target=check_and_send_scheduled_reminders, args=(app,), daemon=True)
    t.start()
    return t
