# 🏭 FlyAsh Manager - Enterprise Brick & Block Plant ERP

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2F14-Nishanth%2Fflyash-manager)
[![Vercel Deployment](https://img.shields.io/badge/Vercel-Live_App-black?style=for-the-badge&logo=vercel)](https://flyash-manager.vercel.app)
[![GitHub Repository](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/14-Nishanth/flyash-manager)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)](https://python.org)
[![Bootstrap 5](https://img.shields.io/badge/Bootstrap-5.3-purple?style=for-the-badge&logo=bootstrap)](https://getbootstrap.com)

A comprehensive, production-ready Cloud ERP and Plant Management web application built with **Flask**, **SQLAlchemy**, and **Bootstrap 5**, tailored specifically for **Fly Ash Bricks & Concrete Hollow/Solid Block manufacturing plants**.

---

## 🌐 Live Cloud Demo on Vercel

Access the live application directly from any mobile phone, tablet, or desktop:

🔗 **Live Vercel Link:** [https://flyash-manager.vercel.app](https://flyash-manager.vercel.app)

> ### 🔑 Verified Staff Login Accounts
> | Role | Username | Password | Access Level |
> |---|---|---|---|
> | **Owner / Admin** | `admin` *(or `admin@flyash.com`)* | `admin123` | Full System Control, Analytics & Settings |
> | **Plant Operator** | `ramesh_op` | `ramesh123` | Production, Loading/Unloading & Stock |
> | **Machine Operator** | `operator_2275` | `operator123` | Daily Piece-Rate Work Entry |
> | **Stock Admin** | `testadmin_stock` | `admin123` | Inventory, Inward & Outward Dispatch |
>
> *(Credentials can be updated at any time from Profile / Staff Accounts)*

---

## 🚀 Key Features & Modules

### 1. 🔨 Dynamic Piece-Rate Wages & Labor Gangs
- **Tray/Stack Production Calculator:** Configurable stack capacity (e.g., 105 pcs) and daily wastage deductions (e.g., 5 pcs) for precise physical stock vs. wage accounting.
- **Customizable Piece Rates:** Configure independent rates per piece/brick for:
  - Standard Fly Ash Bricks (9"x4"x3")
  - Solid Concrete Blocks (4", 6", 8")
  - Hollow Concrete Blocks (4", 6", 8", 10", 12")
  - Paver Blocks & Custom Moulds
- **Labor Gangs / Teams:** Form work gangs with auto-wage division among active workers present on each shift.
- **Loading & Unloading Wages:** Track labor piece-rates for dispatches with party linkage and payment status (`Paid` / `Pending`).

### 2. 🚛 Material Inward & Outward Register
- **Dynamic Multi-Units:** Record materials in their actual units (**Ton / MT**, **Unit / Pcs**, **Bags**, **Load / Trip**, **Kg**, **CFT**), preventing rigid single-unit mismatches.
- **Raw Material Inward Tracking:** Cement (OPC / PPC), Fly Ash (Class F / C), Jelly / Aggregates (Blue Metal 20mm, 12mm, Baby Jelly, Stone Dust), M-Sand, River Sand, Quarry Dust, and Chemicals.
- **Finished Goods Outward:** Customer sales dispatches with auto-computed total amounts, agreed customer rates, vehicle numbers, and automatic ledger updates.

### 3. 👥 1-Click Employee Access & Safe Account Management
- **1-Click Login Creation:** Create staff logins directly from the Employee Directory with automatic role assignment.
- **Instant Revocation & Toggle:** Activate or deactivate staff access in one click.
- **Safe Cascading Deletion:** Delete former employees and staff accounts cleanly without orphaned foreign keys, preserving historical ledger integrity.

### 4. 📊 Customizable Executive Dashboard
- **Personalized KPI Cards:** Select which metrics appear on your dashboard (Today's Inward, Outward, Expenses, Outstanding Receivables/Payables, Production Output, Quick Actions).
- **Tabular Statements & Graph-Free Views:** Clean, fast-loading responsive view optimized for low-bandwidth plant environments.

### 5. 📢 Daily Work Digest & Anti-Spam Security Alerts
- **Automated Daily Digest:** Scheduled multi-channel delivery (Email & Telegram) summarizing daily inward, outward dispatches, piece-rate production, loading volume, labor wages, and collections.
- **Duplicate Payment & Entry Warnings:** Built-in heuristics notify users if identical payments (same party, amount, and date) or duplicate production batches are entered.
- **Owner Security Alerts:** Real-time notifications for staff logins, failed password attempts, and credential updates with anti-spam cooldown throttles.

### 6. 💼 Financial Statements & Dues Adjustments
- **Running Ledger Balances:** Detailed party statements for all Customers & Suppliers.
- **1-Click Full Settlement:** Record complete payments and settlements in a single click.
- **Past Unpaid Dues Tracking:** Adjust and record historical balances prior to software implementation with full audit notes.

---

## 🛠️ Deploying to Vercel

Deploy this repository to Vercel in 1 click:

1. Click the **Deploy with Vercel** button above or import `14-Nishanth/flyash-manager` into your [Vercel Dashboard](https://vercel.com/new).
2. Set the framework preset to **Other**.
3. Deploy! The project automatically uses `vercel.json` and `api/index.py` serverless WSGI functions.

---

## 🗄️ Connecting a Persistent Cloud Database (Neon / Supabase / PostgreSQL)

Local environments run seamlessly on SQLite (`flyash.db`). For persistent storage on Vercel:

1. Create a free PostgreSQL database on [Neon.tech](https://neon.tech), [Supabase.com](https://supabase.com), or [Vercel Postgres](https://vercel.com/docs/storage/vercel-postgres).
2. Copy your connection URI (e.g., `postgresql://user:pass@ep-xyz.neon.tech/flyash?sslmode=require`).
3. Add it as an environment variable in Vercel:
   - Go to your Project on **Vercel Dashboard** → **Settings** → **Environment Variables**.
   - Key: `DATABASE_URL` *(or `POSTGRES_URL`)*
   - Value: `postgresql://...`
4. Redeploy your project. The application will automatically execute migrations, bootstrap admin credentials, and keep all data permanently synced across all devices!

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
   Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## 📱 Progressive Web App (PWA) & Mobile Installation
- Open the application URL in Google Chrome, Safari, or Microsoft Edge on your Android / iOS phone.
- Tap **"Add to Home Screen"** or the **"Install App"** prompt in the navigation bar to install it as a standalone, fullscreen mobile application.

---

## 📄 License & Ownership
Developed for Fly Ash Brick & Concrete Block Manufacturing Operations.  
Owner: **Nishanth** ([@14-Nishanth](https://github.com/14-Nishanth))
