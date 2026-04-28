# QuickDealr v7 — Enhancement Notes

## What Was Changed

### 1. LOGIN PAGE (Animated + Right-Side Card)
- **File:** `templates/auth/login.html`
- Animated gradient background: blue/white tones for user login (CSS @keyframes `gradientShift`)
- Three floating animated blobs for depth
- Login card moved to the **right side** of screen
- Left side shows branding panel with features list
- Fully responsive: on mobile, left panel hides and card takes full width
- Original form structure (inputs, labels, buttons) is unchanged

### 2. ADMIN DASHBOARD REDESIGN
- **Files:** `templates/base_admin.html`, `templates/admin/panel.html`
- Fixed left sidebar (240px wide) with dark background
- Top navbar with breadcrumb and notification bell
- Logo updated: gradient icon (QD) + styled wordmark
- Sidebar navigation: Dashboard, Users, Products, Auctions, Orders, Wallet, Security, Settings
- Wallet link now points to read-only `/admin/wallet` page

### 3. SELLER DASHBOARD REDESIGN
- **File:** `templates/seller/dashboard.html`
- Earnings breakdown card: Total Revenue, Estimated Profit (2%), Wallet Balance
- Stats row: Total Listed, Live, Pending, Auctions, Views, Orders
- Products table with image, category, price, stock, status, actions
- Orders Received table with buyer, amount, estimated profit per order, status

### 4. WALLET SYSTEM (Strict Rules)
- **Files:** `routes/user_routes.py`, `routes/admin_routes.py`, `templates/buyer/wallet_topup.html`
- ✅ All wallet top-ups are **automatically approved** — no admin review needed
- ✅ Transaction ID is optional (no longer required for QR payments)
- ✅ Admin wallet page (`/admin/wallet`) is **read-only** — view balances and history only
- ✅ Admin CANNOT credit/debit any user wallet
- ❌ Old `wallet_requests` approval/reject routes removed from admin sidebar
- ❌ Old pending request table removed from buyer wallet topup page

### 5. WHITELIST BUTTON FIX
- **Files:** `routes/admin_routes.py` (new `toggle_whitelist` route), `models.py`, `templates/admin/panel.html`
- New `is_whitelisted` column added to users table (auto-migrated on first call)
- **AJAX toggle**: clicking button sends POST to `/admin/toggle_whitelist/<uid>`, returns JSON
- Button updates instantly without page reload
- Green "Whitelisted" badge when active, grey "Not Whitelisted" when inactive
- CSRF-protected via form body token (read from `<meta name="csrf-token">`)

### 6. LOGO REPLACEMENT
- **Files:** `templates/base.html` (navbar + footer), `templates/base_admin.html` (sidebar), `templates/auth/login.html`
- Logo: gradient rounded-square icon (QD) + bold wordmark "Quick**Dealr**"
- Consistent across all surfaces — user navbar, admin sidebar, login pages, footer
- Responsive sizing, works on both light and dark backgrounds

### 7. FLOATING AI CHAT BOX (Grok API)
- **Files:** `templates/base.html` (user side), `templates/base_admin.html` (admin side)
- **User endpoint:** `GET/POST /ai_chat` in `user_app.py`
- **Admin endpoint:** `POST /admin/ai_chat` in `routes/admin_routes.py`
- Floating FAB button (bottom-right, purple gradient)
- Popup with typing indicator, scrollable history
- Real-time responses via Grok API (`grok-beta` model)
- **Setup:** Set environment variable `GROK_API_KEY=your_key_here`
- Graceful fallback message when API key is not configured
- No page reload — pure fetch/AJAX

### 8. FILE UPLOAD SYSTEM (Any Extension)
- **Files:** `routes/user_routes.py` (`/seller/upload`), `routes/admin_routes.py` (`/admin/upload_file`), `templates/seller/upload.html`, `models.py`
- Accepts ALL file extensions except executable types (.exe, .php, .py, .sh, .bat, .cmd, .vbs, .ps1, .cgi, .pl, .rb, .asp, .aspx)
- Files saved to `/static/uploads/files/` with UUID-based unique names
- Original filename and metadata stored in `uploaded_files` DB table
- Drag-and-drop UI with file size display
- 10 MB per-file limit
- Secure: `werkzeug.utils.secure_filename` used for sanitization

### 9. AUCTION TIMER FORMAT (HH:MM:SS)
- **Files:** `templates/buyer/auctions.html` (already correct), `templates/admin/panel.html`
- Admin panel auctions table now shows live `HH:MM:SS` countdown
- JavaScript `updateTimers()` runs every 1 second
- Leading zeros always shown (e.g., `02:05:09`)
- Shows "Ended" in red when auction expires

### 10. CURRENCY FORMAT (Indian ₹)
- All `Rs.` replaced with HTML entity `&#8377;` (₹) across:
  - All buyer templates (home, cart, checkout, orders, auction, wallet)
  - All seller templates (dashboard, orders, add/edit product)
  - All admin templates (panel, wallet overview)
  - Auth templates (register page welcome bonus text)
  - Python notification strings in routes

### 11. PROFIT CALCULATION (2% Estimated)
- **Admin Dashboard:** New stat card "Est. Profit (2%)" = 2% of total revenue
- **Admin Orders table:** Per-order estimated profit column (&#8377;X.XX)
- **Seller Dashboard:** Earnings breakdown shows Total Revenue + Estimated Profit
- **Seller Orders table:** Per-order profit column
- Clearly labelled as "Estimated Profit" throughout

### 12. SECURITY & ROUTING
- All existing `@login_required` and `@admin_only` decorators retained
- New `/admin/toggle_whitelist/<uid>` CSRF-protected AJAX route
- New `/admin/wallet` read-only route (replaces wallet_requests)
- File uploads blocked for dangerous extensions server-side
- Session timeout: admin 20 min inactivity, user 30 min inactivity (unchanged)

## Database Migrations Required

If upgrading an **existing** database, run:

```bash
cd QuickDealr_v7
python3 migrate.py
```

Or manually execute:

```sql
ALTER TABLE users ADD COLUMN is_whitelisted INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS uploaded_files (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  original_name TEXT NOT NULL,
  file_path TEXT NOT NULL,
  size_bytes INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Environment Variables

```bash
# Required for AI chatbox
export GROK_API_KEY="your_grok_api_key_here"

# Optional (already have defaults)
export USER_SECRET_KEY="your_secret"
export ADMIN_SECRET_KEY="your_admin_secret"
```

## Running the App

```bash
pip install -r requirements.txt

# Terminal 1 — User app (port 5000)
python run_user.py

# Terminal 2 — Admin app (port 5001)  
python run_admin.py
```

## What Was NOT Changed (as requested)
- Login form structure (inputs, labels, buttons) — unchanged
- No wallet approval/reject system added
- Admin cannot modify wallet balance
- Existing features (auctions, bids, cart, checkout, SocketIO) — all intact
- Admin and user UIs remain completely separate
