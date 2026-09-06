# 🏭 FlyAsh Manager - Brick & Block Plant Management System

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2F14-Nishanth%2Fflyash-manager)
[![Vercel Deployment](https://img.shields.io/badge/Vercel-Live_App-black?style=for-the-badge&logo=vercel)](https://flyash-manager.vercel.app)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/14-Nishanth/flyash-manager)

A comprehensive, production-ready Cloud ERP and Plant Management web application built with **Flask**, **SQLAlchemy**, and **Bootstrap 5**, tailored specifically for **Fly Ash Bricks & Concrete Hollow/Solid Block manufacturing plants**.

---

## 🌐 Live Cloud Demo on Vercel

Access the live application directly from any mobile phone, tablet, or desktop:

🔗 **Live Vercel Link:** [https://flyash-manager.vercel.app](https://flyash-manager.vercel.app)

> **Default Login Credentials:**
> - **Username:** `admin` *(or `admin@flyash.com`)*
> - **Password:** `admin123`
> *(Credentials can be updated immediately after login from My Profile or Security settings)*

---

## 🚀 Key Features

### 1. 🔨 Piece-Rate Job Wages & Labor Gangs / Groups
- **Customizable Piece Rates:** Set independent rates per piece/brick for:
  - Fly Ash Bricks (Production, Loading, Unloading)
  - Solid Concrete Blocks (4", 6", 8" Production, Loading, Unloading)
  - Hollow Concrete Blocks (4", 6", 8", 10", 12")
- **Labor Groups / Teams:** Create work gangs and assign employees to groups.
- **Auto Wage Splitting:** When recording daily production or loading/unloading, the total earnings are automatically divided equally among the active workers present that day.

### 2. 🚛 Material Inward & Outward Register
- Full tracking of raw materials and finished goods:
  - **Cement** (OPC / PPC bags & bulkers)
  - **Jelly / Aggregates** (Blue Metal 20mm, 12mm, Baby Jelly, Stone Dust)
  - **Fly Ash** (Class F / Class C MT)
  - **M-Sand / River Sand / Crusher Sand**
  - **Chemicals, Quarry Dust & Slag**
- Auto-calculation of quantities, rates per MT, vehicle numbers, and supplier billing.

### 3. 👥 Role-Based Staff Accounts
Create dedicated logins with customizable roles from **Staff & Users**:
- **Operator:** Quick piece-rate work recording, loading/unloading, and material entry.
- **Supervisor:** Daily attendance tracking, group management, and wage calculations.
- **Accountant:** Customer/Supplier ledgers, payments received/paid, and billing.
- **Owner / Admin:** Full system control, analytics, and security alert configurations.

### 4. 📱 Real-Time Owner Security Alerts
Instant multi-channel notifications sent directly to the owner on:
- Staff logins (account name, time, IP address, device)
- Failed / Incorrect password attempts
- Password & Profile updates
- **Supported Channels:** Telegram Bot, WhatsApp API, Fast2SMS, and direct SMTP Email.

### 5. 📱 Fully Responsive Mobile Layout
- Native-like mobile experience with touch-friendly navigation, slide-out sidebar, 2x2 responsive KPI dashboard cards, and mobile-optimized table views.

### 6. 📊 Accounting Ledgers & Reports
- Running balance ledgers for all Customers & Suppliers.
- Daily production reports, stock balance summaries, and CSV data export.

---

## 🛠️ Deploying to Vercel

You can deploy this repository to Vercel in 1 click:

1. Click the **Deploy with Vercel** button above or import `14-Nishanth/flyash-manager` in your [Vercel Dashboard](https://vercel.com/new).
2. Set the framework preset to **Other**.
3. Deploy! The project automatically uses `vercel.json` and `api/index.py` serverless functions.

---

## 💻 Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/14-Nishanth/flyash-manager.git
   cd flyash-manager
   ```

2. **Create a virtual environment & install dependencies:**
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate

   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```
   Open [http://localhost:5000](http://localhost:5000) in your web browser.

---

## 📄 License & Ownership
Developed for Fly Ash Brick & Block Manufacturing Operations.  
Owner: **Nishanth** ([@14-Nishanth](https://github.com/14-Nishanth))
