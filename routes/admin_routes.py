from datetime import datetime
# -*- coding: utf-8 -*-
"""
routes/admin_routes.py  — QuickDealr Enhanced
Admin blueprint: dashboard, products, orders, wallet (view-only),
whitelist toggle, AI chat (Grok), file upload, security logs.
Runs on port 5001. Admin-only access enforced on every route.
"""

import os
import uuid
import mimetypes
from pathlib import Path
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify)
from werkzeug.utils import secure_filename
from utils import (login_required, admin_only, generate_csrf,
                   validate_csrf, get_ip, api_ok, ROLE_ADMIN)
import models

admin_bp = Blueprint('admin', __name__, url_prefix='',
                     template_folder='../templates')

# ── Upload config ──────────────────────────────────────────────────────────
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'files')
MAX_FILE_SIZE_MB = 10  # 10 MB limit
BLOCKED_EXTENSIONS = {'.exe', '.php', '.py', '.sh', '.bat', '.cmd', '.js',
                      '.vbs', '.ps1', '.cgi', '.pl', '.rb', '.asp', '.aspx'}

# ── CSRF injection ─────────────────────────────────────────────────────────
@admin_bp.before_request
def inject_csrf():
    from flask import g
    g.csrf_token = generate_csrf()


# ══════════════════════════════════════════════════════════════════════════
#  Dashboard
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/')
@login_required
@admin_only
def dashboard():
    db       = models.get_db()
    stats    = models.get_admin_stats()
    users    = [dict(u) for u in models.get_all_users()]
    products = db.execute(
        """SELECT p.*,
               u.username as seller_name,
               (SELECT COUNT(*) FROM bids b WHERE b.product_id=p.id) as bid_count,
               p.highest_bidder, p.current_bid,
               CASE WHEN p.approved=1 AND p.status IS NULL THEN 'approved'
                    WHEN p.status IS NOT NULL THEN p.status
                    ELSE 'pending' END as status
           FROM products p
           LEFT JOIN users u ON p.seller_id=u.id
           ORDER BY p.approved ASC, p.created_at DESC"""
    ).fetchall()
    orders = db.execute(
        """SELECT o.*, u.username as buyer_name, p.name as product_name
           FROM orders o
           LEFT JOIN users u ON o.buyer_id=u.id
           LEFT JOIN products p ON o.product_id=p.id
           ORDER BY o.created_at DESC LIMIT 100"""
    ).fetchall()
    sec_logs    = models.get_security_logs(limit=30)
    blocked     = models.get_blocked_ips()
    qr          = models.get_qr_settings()
    wallet_txns = models.get_all_wallet_transactions(limit=50)
    nc          = models.unread_count(session['user_id'])
    return render_template('admin/panel.html',
        stats=stats, users=users, products=products, orders=orders,
        sec_logs=sec_logs, blocked=blocked, qr=qr,
        wallet_txns=wallet_txns, nc=nc)


# ══════════════════════════════════════════════════════════════════════════
#  Products
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/approve/<int:pid>', methods=['POST'])
@login_required
@admin_only
def approve_product(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    p = models.approve_product(pid)
    if p:
        models.add_notification(p['seller_id'],
            f"Your product '{p['name']}' has been approved and is now live!", ntype='info')
        flash(f"Product '{p['name']}' approved.", 'success')
    else:
        flash('Product not found.', 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/reject/<int:pid>', methods=['POST'])
@login_required
@admin_only
def reject_product(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    reason = request.form.get('reason', 'Does not meet quality standards.').strip()
    p = models.reject_product(pid)
    if p:
        models.add_notification(p['seller_id'],
            f"Your product '{p['name']}' was rejected. Reason: {reason}", ntype='info')
        flash(f"Product '{p['name']}' rejected.", 'success')
    else:
        flash('Product not found.', 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/deactivate/<int:pid>', methods=['POST'])
@login_required
@admin_only
def deactivate_product(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    p = models.deactivate_product(pid)
    if p:
        models.add_notification(p['seller_id'],
            f"Your product '{p['name']}' has been deactivated by admin.", ntype='info')
        flash(f"Product '{p['name']}' deactivated.", 'success')
    else:
        flash('Product not found.', 'error')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/delete/<int:pid>', methods=['POST'])
@login_required
@admin_only
def delete_product(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    p = models.delete_product_admin(pid)
    if p:
        models.add_notification(p['seller_id'],
            f"Your product '{p['name']}' has been permanently removed by admin.", ntype='info')
        flash(f"Product '{p['name']}' deleted.", 'success')
    else:
        flash('Product not found.', 'error')
    return redirect(url_for('admin.dashboard'))


# ══════════════════════════════════════════════════════════════════════════
#  Orders
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/order_status/<int:oid>', methods=['POST'])
@login_required
@admin_only
def update_order_status(oid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    valid_statuses = ('Placed', 'Confirmed', 'Shipped', 'Delivered', 'Cancelled')
    status = request.form.get('status', 'Placed')
    if status not in valid_statuses:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin.dashboard'))
    o = models.update_order_status(oid, status)
    if o:
        models.add_notification(o['buyer_id'], f"Order #{oid} is now: {status}", ntype='order')
    flash(f'Order #{oid} updated to {status}.', 'success')
    return redirect(url_for('admin.dashboard'))


# ══════════════════════════════════════════════════════════════════════════
#  Users
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/toggle_user/<int:uid>', methods=['POST'])
@login_required
@admin_only
def toggle_user(uid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    if uid == session['user_id']:
        flash('Cannot deactivate your own account.', 'error')
        return redirect(url_for('admin.dashboard'))
    new_state = models.toggle_user_active(uid)
    flash(f"User {'activated' if new_state else 'deactivated'}.", 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/toggle_whitelist/<int:uid>', methods=['POST'])
@login_required
@admin_only
def toggle_whitelist(uid):
    """AJAX endpoint — returns JSON. Toggles is_whitelisted for a user."""
    # Read CSRF from form body (sent as application/x-www-form-urlencoded)
    csrf = request.form.get('_csrf', '')
    if not validate_csrf(csrf):
        return jsonify({'success': False, 'error': 'Security error: invalid CSRF token.'})
    result = models.toggle_user_whitelist(uid)
    if result is None:
        return jsonify({'success': False, 'error': 'User not found.'})
    return jsonify({'success': True, 'whitelisted': bool(result)})


# ══════════════════════════════════════════════════════════════════════════
#  Security
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/unblock_ip', methods=['POST'])
@login_required
@admin_only
def unblock_ip():
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    ip = request.form.get('ip', '').strip()
    if ip:
        models.unblock_ip(ip)
        flash(f'IP {ip} unblocked.', 'success')
    return redirect(url_for('admin.dashboard'))


# ══════════════════════════════════════════════════════════════════════════
#  QR Settings
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/qr_settings', methods=['POST'])
@login_required
@admin_only
def update_qr_settings():
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    qr_image = request.form.get('qr_image', '').strip()
    upi_id   = request.form.get('upi_id', '').strip()
    models.update_qr_settings(qr_image, upi_id)
    flash('QR settings updated!', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/admin/qr_upload', methods=['POST'])
@login_required
@admin_only
def qr_file_upload():
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.dashboard'))
    file   = request.files.get('qr_file')
    upi_id = request.form.get('upi_id', '').strip()
    img_path = ''
    if file and file.filename:
        img_path = models.save_uploaded_image(file, 'qr')
        if not img_path:
            flash('Invalid file type. Use PNG/JPG.', 'error')
            return redirect(url_for('admin.dashboard'))
    else:
        img_path = request.form.get('qr_image', '').strip()
    models.update_qr_settings(img_path, upi_id)
    flash('QR settings updated!', 'success')
    return redirect(url_for('admin.dashboard'))


# ══════════════════════════════════════════════════════════════════════════
#  Wallet — VIEW ONLY (no approve/reject/credit/debit)
# ══════════════════════════════════════════════════════════════════════════
# Admin can only VIEW balances and transaction history.
# All wallet transactions are automatic (no approval required).

@admin_bp.route('/admin/wallet-requests')
@login_required
@admin_only
def wallet_requests():
    db = models.get_db()
    requests_list = models.get_wallet_requests(status=None, limit=100)
    stats = models.get_admin_stats()
    nc = models.unread_count(session['user_id'])
    return render_template('admin/wallet_requests.html',
                           requests=requests_list, stats=stats, nc=nc)

# Wallet request approval/rejection routes

@admin_bp.route('/admin/approve_wallet_request/<int:req_id>', methods=['POST'])
@login_required
@admin_only
def approve_wallet_request(req_id):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    db = models.get_db()
    req_row = db.execute("SELECT * FROM wallet_requests WHERE id=?", (req_id,)).fetchone()
    if not req_row:
        flash('Request not found.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    if req_row['status'] != 'pending':
        flash('Request already processed.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    amount = float(req_row['amount'])
    models.credit_wallet(req_row['user_id'], amount,
                         f'Wallet top-up approved (Ref: {req_row["reference"] or req_id})',
                         'topup')
    db.execute("UPDATE wallet_requests SET status='approved', updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (req_id,))
    db.commit()
    models.add_notification(req_row['user_id'],
                            f'Your wallet top-up of ₹{amount:,.2f} has been approved.', ntype='success')
    flash(f'Wallet request #{req_id} approved — ₹{amount:,.2f} credited.', 'success')
    return redirect(url_for('admin.wallet_requests'))


@admin_bp.route('/admin/reject_wallet_request/<int:req_id>', methods=['POST'])
@login_required
@admin_only
def reject_wallet_request(req_id):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    db = models.get_db()
    req_row = db.execute("SELECT * FROM wallet_requests WHERE id=?", (req_id,)).fetchone()
    if not req_row:
        flash('Request not found.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    if req_row['status'] != 'pending':
        flash('Request already processed.', 'error')
        return redirect(url_for('admin.wallet_requests'))
    reason = request.form.get('reason', 'Rejected by admin').strip() or 'Rejected by admin'
    db.execute("UPDATE wallet_requests SET status='rejected', updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (req_id,))
    db.commit()
    models.add_notification(req_row['user_id'],
                            f'Your wallet top-up of ₹{float(req_row["amount"]):,.2f} was rejected. Reason: {reason}',
                            ntype='error')
    flash(f'Wallet request #{req_id} rejected.', 'success')
    return redirect(url_for('admin.wallet_requests'))



@admin_bp.route('/admin/wallet')
@login_required
@admin_only
def wallet_overview():
    db    = models.get_db()
    users = db.execute(
        "SELECT id, username, wallet FROM users ORDER BY wallet DESC"
    ).fetchall()
    txns  = models.get_all_wallet_transactions(limit=100)
    nc    = models.unread_count(session['user_id'])
    return render_template('admin/wallet_overview.html',
                           users=users, txns=txns, nc=nc)


# ══════════════════════════════════════════════════════════════════════════
#  Notifications
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/notifications')
@login_required
@admin_only
def notifications():
    notifs = models.get_notifications(session['user_id'], limit=30)
    models.mark_notifications_read(session['user_id'])
    return render_template('admin/notifications.html', notifs=notifs, nc=0)


# ══════════════════════════════════════════════════════════════════════════
#  Promo Codes
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/promos')
@login_required
@admin_only
def promo_codes():
    promos = models.get_all_promo_codes()
    nc     = models.unread_count(session['user_id'])
    return render_template('admin/promos.html', promos=promos, nc=nc)


@admin_bp.route('/admin/promos/create', methods=['POST'])
@login_required
@admin_only
def create_promo():
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.promo_codes'))
    code  = request.form.get('code', '').strip().upper()
    dtype = request.form.get('discount_type', 'percentage')
    try:
        value     = float(request.form.get('value', 0))
        min_order = float(request.form.get('min_order', 0))
        max_uses  = request.form.get('max_uses', '').strip()
        max_uses  = int(max_uses) if max_uses else None
    except (ValueError, TypeError):
        flash('Invalid promo code values.', 'error')
        return redirect(url_for('admin.promo_codes'))
    if not code or value <= 0:
        flash('Code and value are required.', 'error')
        return redirect(url_for('admin.promo_codes'))
    if dtype == 'percentage' and value > 100:
        flash('Percentage discount cannot exceed 100%.', 'error')
        return redirect(url_for('admin.promo_codes'))
    models.create_promo_code(code, dtype, value, min_order, max_uses)
    flash(f'Promo code {code} created!', 'success')
    return redirect(url_for('admin.promo_codes'))


@admin_bp.route('/admin/promos/toggle/<int:pid>', methods=['POST'])
@login_required
@admin_only
def toggle_promo(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.promo_codes'))
    models.toggle_promo_code(pid)
    flash('Promo code status updated.', 'success')
    return redirect(url_for('admin.promo_codes'))


@admin_bp.route('/admin/promos/delete/<int:pid>', methods=['POST'])
@login_required
@admin_only
def delete_promo(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.promo_codes'))
    models.delete_promo_code(pid)
    flash('Promo code deleted.', 'success')
    return redirect(url_for('admin.promo_codes'))


# ══════════════════════════════════════════════════════════════════════════
#  Contact Messages
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/messages')
@login_required
@admin_only
def contact_messages():
    msgs = models.get_contact_messages(limit=100)
    nc   = models.unread_count(session['user_id'])
    return render_template('admin/contact_messages.html', msgs=msgs, nc=nc)


@admin_bp.route('/admin/messages/resolve/<int:mid>', methods=['POST'])
@login_required
@admin_only
def resolve_message(mid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('admin.contact_messages'))
    models.resolve_contact_message(mid)
    flash('Message marked as resolved.', 'success')
    return redirect(url_for('admin.contact_messages'))


# ══════════════════════════════════════════════════════════════════════════
#  File Upload (any extension, secured)
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/upload_file', methods=['POST'])
@login_required
@admin_only
def upload_file():
    if not validate_csrf(request.form.get('_csrf')):
        return jsonify({'success': False, 'error': 'Security error.'})
    f = request.files.get('file')
    if not f or not f.filename:
        return jsonify({'success': False, 'error': 'No file provided.'})

    original_name = secure_filename(f.filename)
    ext = Path(original_name).suffix.lower()

    # Block dangerous executable extensions
    if ext in BLOCKED_EXTENSIONS:
        return jsonify({'success': False, 'error': f'File type {ext} is not allowed.'})

    # Check content-length if available
    f.seek(0, 2)
    size_bytes = f.tell()
    f.seek(0)
    if size_bytes > MAX_FILE_SIZE_MB * 1024 * 1024:
        return jsonify({'success': False, 'error': f'File exceeds {MAX_FILE_SIZE_MB}MB limit.'})

    # Unique filename to prevent overwrites / path traversal
    unique_name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    save_path = os.path.join(UPLOAD_FOLDER, unique_name)
    f.save(save_path)

    # Store record in DB
    rel_path = f"/static/uploads/files/{unique_name}"
    models.store_uploaded_file(session['user_id'], original_name, rel_path, size_bytes)

    return jsonify({'success': True, 'path': rel_path, 'name': original_name})


# ══════════════════════════════════════════════════════════════════════════
#  AI Chat (Grok API)
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/ai_chat', methods=['POST'])
@login_required
@admin_only
def ai_chat():
    data    = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'reply': 'Please enter a message.'})

    grok_api_key = os.environ.get('GROK_API_KEY', '')
    if not grok_api_key:
        # Graceful fallback when no API key is configured
        return jsonify({'reply': (
            'The AI assistant is not configured yet. '
            'Set the GROK_API_KEY environment variable to enable it. '
            'For now: How can I assist you with your admin tasks?'
        )})

    try:
        import urllib.request, json as _json
        payload = _json.dumps({
            "model": "grok-beta",
            "messages": [
                {"role": "system", "content":
                    "You are a helpful AI assistant for QuickDealr, an Indian marketplace platform. "
                    "You help admins manage products, users, orders, auctions, and wallets. "
                    "Keep responses concise and practical. Use Indian Rupee (₹) for amounts."},
                {"role": "user", "content": message}
            ],
            "max_tokens": 300
        }).encode()
        req = urllib.request.Request(
            'https://api.x.ai/v1/chat/completions',
            data=payload,
            headers={
                'Authorization': f'Bearer {grok_api_key}',
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = _json.loads(resp.read())
        reply = result['choices'][0]['message']['content']
    except Exception as e:
        reply = f'AI service error: {str(e)[:120]}. Please try again.'

    return jsonify({'reply': reply})


# ══════════════════════════════════════════════════════════════════════════
#  API: live auction status
# ══════════════════════════════════════════════════════════════════════════



# ══════════════════════════════════════════════════════════════════════════
#  Separate Admin Pages
# ══════════════════════════════════════════════════════════════════════════

@admin_bp.route('/admin/users')
@login_required
@admin_only
def users_page():
    users = [dict(u) for u in models.get_all_users()]
    nc = models.unread_count(session['user_id'])
    return render_template('admin/users.html', users=users, nc=nc)


@admin_bp.route('/admin/auctions')
@login_required
@admin_only
def auctions_page():
    db = models.get_db()
    products = db.execute(
        """SELECT p.*, u.username as seller_name,
               (SELECT COUNT(*) FROM bids b WHERE b.product_id=p.id) as bid_count
           FROM products p LEFT JOIN users u ON p.seller_id=u.id
           WHERE p.is_auction=1 ORDER BY p.created_at DESC"""
    ).fetchall()
    nc = models.unread_count(session['user_id'])
    now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    return render_template('admin/auctions.html', products=products, nc=nc, now_str=now_str)


@admin_bp.route('/admin/transactions')
@login_required
@admin_only
def transactions_page():
    db = models.get_db()
    orders = db.execute(
        """SELECT o.*, u.username as buyer_name, p.name as product_name
           FROM orders o LEFT JOIN users u ON o.buyer_id=u.id
           LEFT JOIN products p ON o.product_id=p.id
           ORDER BY o.created_at DESC LIMIT 200"""
    ).fetchall()
    wallet_txns = models.get_all_wallet_transactions(limit=100)
    nc = models.unread_count(session['user_id'])
    return render_template('admin/transactions.html', orders=orders,
                           wallet_txns=wallet_txns, nc=nc)


@admin_bp.route('/admin/analytics')
@login_required
@admin_only
def analytics_page():
    db = models.get_db()
    # Revenue by day (last 30 days)
    revenue_data = db.execute(
        """SELECT DATE(created_at) as day, SUM(total_amount) as revenue
           FROM orders WHERE status != 'Cancelled'
           AND created_at >= DATE('now', '-30 days')
           GROUP BY day ORDER BY day"""
    ).fetchall()
    # User growth (last 30 days)
    user_data = db.execute(
        """SELECT DATE(created_at) as day, COUNT(*) as count
           FROM users WHERE created_at >= DATE('now', '-30 days')
           GROUP BY day ORDER BY day"""
    ).fetchall()
    # Auction count by day
    auction_data = db.execute(
        """SELECT DATE(created_at) as day, COUNT(*) as count
           FROM products WHERE is_auction=1
           AND created_at >= DATE('now', '-30 days')
           GROUP BY day ORDER BY day"""
    ).fetchall()
    stats = models.get_admin_stats()
    nc = models.unread_count(session['user_id'])
    return render_template('admin/analytics.html',
        revenue_data=[dict(r) for r in revenue_data],
        user_data=[dict(r) for r in user_data],
        auction_data=[dict(r) for r in auction_data],
        stats=stats, nc=nc)


@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@login_required
@admin_only
def settings_page():
    db = models.get_db()
    nc = models.unread_count(session['user_id'])
    qr = models.get_qr_settings()
    if request.method == 'POST':
        if not validate_csrf(request.form.get('_csrf')):
            flash('Security error.', 'error')
            return redirect(url_for('admin.settings_page'))
        action = request.form.get('action')
        if action == 'upi':
            upi_id = request.form.get('upi_id', '').strip()
            db.execute("UPDATE settings SET value=? WHERE key='upi_id'", (upi_id,))
            if db.execute("SELECT key FROM settings WHERE key='upi_id'").fetchone() is None:
                db.execute("INSERT INTO settings (key,value) VALUES ('upi_id',?)", (upi_id,))
            db.commit()
            flash('UPI ID updated.', 'success')
        elif action == 'password':
            import hashlib
            old_pw = request.form.get('old_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')
            if new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
                return redirect(url_for('admin.settings_page'))
            if len(new_pw) < 6:
                flash('Password must be at least 6 characters.', 'error')
                return redirect(url_for('admin.settings_page'))
            uid = session['user_id']
            user = db.execute("SELECT password FROM users WHERE id=?", (uid,)).fetchone()
            import werkzeug.security as ws
            if not ws.check_password_hash(user['password'], old_pw):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('admin.settings_page'))
            new_hash = ws.generate_password_hash(new_pw)
            db.execute("UPDATE users SET password=? WHERE id=?", (new_hash, uid))
            db.commit()
            flash('Password changed successfully.', 'success')
        return redirect(url_for('admin.settings_page'))
    return render_template('admin/settings.html', qr=qr, nc=nc)

@admin_bp.route('/api/auction_status/<int:pid>')
@login_required
@admin_only
def auction_status(pid):
    from utils import seconds_left
    p = models.get_db().execute(
        "SELECT current_bid,bid_count,highest_bidder,auction_end,watcher_count "
        "FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return api_ok({'error': 'not found'})
    return api_ok({
        'current_bid':    p['current_bid'],
        'bid_count':      p['bid_count'],
        'highest_bidder': p['highest_bidder'],
        'seconds_left':   seconds_left(p['auction_end']),
        'watcher_count':  p['watcher_count'],
    })
