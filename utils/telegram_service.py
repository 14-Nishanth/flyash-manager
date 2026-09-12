import threading
import time
from datetime import datetime, date
import requests
from flask import current_app


def send_telegram_message(text, bot_token=None, chat_id=None, parse_mode='HTML'):
    """
    Sends a message to Telegram channel / user / group via Telegram Bot API.
    Returns (success: bool, response_dict_or_error: dict|str).
    """
    if not bot_token or not chat_id:
        from models import AlertSettings
        settings = AlertSettings.query.first()
        if settings:
            bot_token = bot_token or settings.get_telegram_token()
            chat_id = chat_id or settings.get_telegram_chat_id()

    if not bot_token or not chat_id:
        return False, "Telegram Bot Token or Chat ID is not configured. Please enter Bot Token and Chat ID."

    url = f"https://api.telegram.org/bot{bot_token.strip()}/sendMessage"
    payload = {
        'chat_id': str(chat_id).strip(),
        'text': text,
        'parse_mode': parse_mode,
        'disable_web_page_preview': False
    }

    try:
        res = requests.post(url, json=payload, timeout=8)
        data = res.json()
        if res.status_code == 200 and data.get('ok'):
            return True, data
        else:
            err_desc = data.get('description', f"HTTP {res.status_code}")
            return False, f"Telegram API error: {err_desc}"
    except Exception as e:
        return False, f"Network/Connection error sending Telegram message: {str(e)}"


def build_morning_reminder(app_base_url="http://localhost:5000"):
    """
    Builds the morning start-of-day attendance & work start reminder message.
    """
    from models import Employee, EmployeeGroup
    today = date.today()
    date_str = today.strftime('%d %b %Y')
    day_name = today.strftime('%A')

    active_emps = Employee.query.filter_by(is_active=True).count()
    active_groups = EmployeeGroup.query.count()

    attendance_link = f"{app_base_url.rstrip('/')}/employees/attendance"
    production_link = f"{app_base_url.rstrip('/')}/stock/production"

    msg = (
        f"☀️ <b>GOOD MORNING! PLANT WORK & ATTENDANCE REMINDER</b> ☀️\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {date_str} ({day_name})\n"
        f"🏭 <b>Plant:</b> FlyAsh Brick & Block Manufacturing Unit\n\n"
        f"👥 <b>Active Workforce:</b> {active_emps} Workers across {active_groups} Work Gangs\n\n"
        f"📋 <b>Morning Action Checklist:</b>\n"
        f" 1️⃣ Mark today's morning worker attendance (Drivers, Loaders, Operators)\n"
        f" 2️⃣ Verify raw material silos & press machine readiness\n"
        f" 3️⃣ Start recording production batches & tray counts\n\n"
        f"👉 <b>Open Attendance Register:</b>\n"
        f"<a href=\"{attendance_link}\">👉 Click Here to Mark Attendance</a>\n\n"
        f"👉 <b>Open Production Sheet:</b>\n"
        f"<a href=\"{production_link}\">👉 Click Here for Production Sheet</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡ FlyAsh ERP Automatic Daily Notification</i>"
    )
    return msg


def build_evening_reminder(app_base_url="http://localhost:5000", target_date=None):
    """
    Builds the evening work-completed attendance & daily summary reminder message.
    """
    from models import Employee, Attendance, JobWageEntry, MaterialOutward

    target_date = target_date or date.today()
    date_str = target_date.strftime('%d %b %Y')
    day_name = target_date.strftime('%A')

    total_active = Employee.query.filter_by(is_active=True).count()
    attendances = Attendance.query.filter_by(date=target_date).all()
    present_cnt = sum(1 for a in attendances if a.status == 'present')
    absent_cnt = sum(1 for a in attendances if a.status == 'absent')
    half_cnt = sum(1 for a in attendances if a.status == 'half-day')
    unmarked_cnt = max(0, total_active - len(attendances))

    prod_jobs = JobWageEntry.query.filter(
        JobWageEntry.date == target_date,
        JobWageEntry.job_type.ilike('%Production%')
    ).all()
    total_trays = sum(j.tray_count or 0.0 for j in prod_jobs)
    total_gross_qty = sum(j.gross_quantity or j.quantity or 0.0 for j in prod_jobs)
    total_wages = sum(j.total_wage or 0.0 for j in prod_jobs)

    outwards = MaterialOutward.query.filter_by(date=target_date).all()
    total_dispatch_qty = sum(o.quantity_mt for o in outwards)

    attendance_link = f"{app_base_url.rstrip('/')}/employees/attendance"
    wages_link = f"{app_base_url.rstrip('/')}/employees/job-wages"
    stock_link = f"{app_base_url.rstrip('/')}/stock"

    msg = (
        f"🌙 <b>EVENING WORK COMPLETED & DAILY RECAP</b> 🌙\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 <b>Date:</b> {date_str} ({day_name})\n"
        f"🏭 <b>Plant:</b> FlyAsh Brick & Block Manufacturing Unit\n\n"
        f"📊 <b>Worker Attendance Summary:</b>\n"
        f" • ✅ Present: <b>{present_cnt}</b>\n"
        f" • ❌ Absent: <b>{absent_cnt}</b>\n"
        f" • 🌓 Half-Day: <b>{half_cnt}</b>\n"
        f" • ⚠️ Unmarked: <b>{unmarked_cnt}</b> / {total_active} Total\n\n"
        f"🏗️ <b>Today's Production & Job Output:</b>\n"
        f" • 📦 Trays Produced: <b>{total_trays:,.0f} Trays</b>\n"
        f" • 🧱 Total Bricks / Blocks: <b>{total_gross_qty:,.0f} Pcs</b>\n"
        f" • 💰 Daily Piece Wages: <b>₹{total_wages:,.2f}</b>\n"
        f" • 🚚 Material Dispatched: <b>{total_dispatch_qty:,.2f} MT</b>\n\n"
        f"🔔 <b>Evening Action Checklist:</b>\n"
        f" 1️⃣ Verify all worker attendance is locked\n"
        f" 2️⃣ Confirm all gang job sheets and vehicle dispatches are recorded\n"
        f" 3️⃣ Check closing yard stock balance\n\n"
        f"👉 <b>Quick Links:</b>\n"
        f"• <a href=\"{attendance_link}\">Mark/Review Attendance</a>\n"
        f"• <a href=\"{wages_link}\">Job Wage Register</a>\n"
        f"• <a href=\"{stock_link}\">Stock & Yard Inventory</a>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<i>⚡ FlyAsh ERP Automatic Daily Notification</i>"
    )
    return msg


def check_and_send_scheduled_reminders(app):
    """
    Background worker loop that checks current time against configured
    morning (default 07:00) and evening (default 19:00) reminder times.
    """
    while True:
        try:
            with app.app_context():
                from models import db, AlertSettings
                settings = AlertSettings.query.first()
                if settings and settings.get_telegram_token() and settings.get_telegram_chat_id():
                    now = datetime.now()
                    current_hm = now.strftime('%H:%M')
                    today_date = now.date()

                    morning_time = (settings.telegram_morning_reminder_time or '07:00').strip()
                    morning_enabled = settings.telegram_morning_reminder_enabled if settings.telegram_morning_reminder_enabled is not None else True
                    if morning_enabled and current_hm == morning_time and settings.last_morning_sent_date != today_date:
                        msg = build_morning_reminder()
                        success, res = send_telegram_message(msg, settings.get_telegram_token(), settings.get_telegram_chat_id())
                        if success:
                            settings.last_morning_sent_date = today_date
                            db.session.commit()
                            print(f"[OK] Scheduled morning Telegram reminder sent successfully for {today_date} at {current_hm}")
                        else:
                            print(f"[WARN] Failed to send scheduled morning Telegram reminder: {res}")

                    evening_time = (settings.telegram_evening_reminder_time or '19:00').strip()
                    evening_enabled = settings.telegram_evening_reminder_enabled if settings.telegram_evening_reminder_enabled is not None else True
                    if evening_enabled and current_hm == evening_time and settings.last_evening_sent_date != today_date:
                        msg = build_evening_reminder(target_date=today_date)
                        success, res = send_telegram_message(msg, settings.get_telegram_token(), settings.get_telegram_chat_id())
                        if success:
                            settings.last_evening_sent_date = today_date
                            db.session.commit()
                            print(f"[OK] Scheduled evening Telegram reminder sent successfully for {today_date} at {current_hm}")
                        else:
                            print(f"[WARN] Failed to send scheduled evening Telegram reminder: {res}")

        except Exception as e:
            pass

        time.sleep(30)


_scheduler_started = False
def start_telegram_scheduler(app):
    """Starts the background scheduler thread if not already active."""
    global _scheduler_started
    if not _scheduler_started:
        _scheduler_started = True
        thread = threading.Thread(target=check_and_send_scheduled_reminders, args=(app,), daemon=True)
        thread.start()
        return thread
    return None
