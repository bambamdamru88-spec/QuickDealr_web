# -*- coding: utf-8 -*-
"""
user_app.py  --  QuickDealr User Application
Serves buyers and sellers on port 5000.
Shares the same database as admin_app (port 5001).
"""

import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, session, redirect, url_for, g
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from models import (init_db, close_db, valid_session, get_wallet,
                    get_qr_settings, save_chat_message, get_raw_conn,
                    unread_count, cart_item_count)
from utils import seconds_left, generate_csrf, ROLE_BUYER

from routes.auth_routes import auth_bp
from routes.user_routes  import buyer_bp, seller_bp, wallet_bp

#  Flask app 
user_app = Flask(__name__,
                 template_folder='templates',
                 static_folder='static')

user_app.secret_key = os.environ.get('USER_SECRET_KEY', 'user_qd_v6_secret_key_change_me')
user_app.config.update(
    SESSION_COOKIE_NAME    = 'qd_user_session',
    SESSION_COOKIE_HTTPONLY= True,
    SESSION_COOKIE_SAMESITE= 'Lax',
    SESSION_COOKIE_SECURE  = False,
    MAX_CONTENT_LENGTH     = 10 * 1024 * 1024,   # 10 MB
    UPLOAD_FOLDER          = 'static/uploads',
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8),
)

#  Extensions 
socketio = SocketIO(user_app, cors_allowed_origins='*', async_mode='threading')
limiter  = Limiter(key_func=get_remote_address, app=user_app,
                   default_limits=[], storage_uri='memory://')

#  Register blueprints 
user_app.register_blueprint(auth_bp)
user_app.register_blueprint(buyer_bp)
user_app.register_blueprint(seller_bp)
user_app.register_blueprint(wallet_bp)

#  Jinja globals 
from datetime import datetime as _dt
def _now_str():
    return _dt.utcnow().strftime('%Y-%m-%d %H:%M:%S')

user_app.jinja_env.globals.update(
    seconds_left = seconds_left,
    get_wallet   = get_wallet,
    csrf_token   = generate_csrf,
    int          = int,
    now_str      = _now_str,
)

#  DB lifecycle 
@user_app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)

#  Session enforcement 
@user_app.before_request
def enforce_session():
    from flask import request
    session.permanent = True
    uid   = session.get('user_id')
    token = session.get('session_token')
    if uid and token:
        if not valid_session(uid, token):
            session.clear()
            from flask import flash
            flash('Your session has expired. Please login again.', 'error')
            if not request.path.startswith('/static'):
                return redirect(url_for('auth.login'))
        last_active = session.get('_last_active')
        now = datetime.now(timezone.utc)
        if last_active:
            last_active_dt = datetime.fromisoformat(last_active)
            if last_active_dt.tzinfo is None:
                last_active_dt = last_active_dt.replace(tzinfo=timezone.utc)
            elapsed = (now - last_active_dt).total_seconds()
            if elapsed > 1800:
                session.clear()
                from flask import flash
                flash('You have been logged out due to inactivity.', 'error')
                if not request.path.startswith('/static'):
                    return redirect(url_for('auth.login'))
        session['_last_active'] = now.isoformat()

# ── AI Chat endpoint (user-facing) ──────────────────────────────────────────
@user_app.route('/ai_chat', methods=['POST'])
def ai_chat():
    """Floating AI chatbox for users — powered by Grok API."""
    from flask import jsonify, request as req
    data    = req.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'reply': 'Please type a message.'})

    grok_api_key = os.environ.get('GROK_API_KEY', '')
    if not grok_api_key:
        return jsonify({'reply': (
            'The AI assistant is not yet configured. '
            'Ask the site admin to set the GROK_API_KEY. '
            'Meanwhile, browse our auctions or check your wallet!'
        )})

    try:
        import urllib.request, json as _json
        payload = _json.dumps({
            "model": "grok-beta",
            "messages": [
                {"role": "system", "content":
                    "You are a helpful shopping assistant for QuickDealr, an Indian marketplace. "
                    "Help users with product searches, auction bidding, wallet top-ups, and orders. "
                    "Be friendly and concise. Use ₹ for prices."},
                {"role": "user", "content": message}
            ],
            "max_tokens": 250
        }).encode()
        req2 = urllib.request.Request(
            'https://api.x.ai/v1/chat/completions',
            data=payload,
            headers={
                'Authorization': f'Bearer {grok_api_key}',
                'Content-Type': 'application/json'
            }
        )
        with urllib.request.urlopen(req2, timeout=15) as resp:
            result = _json.loads(resp.read())
        reply = result['choices'][0]['message']['content']
    except Exception as e:
        reply = f'AI service temporarily unavailable. Please try again shortly.'

    return jsonify({'reply': reply})

#  Error handlers 
@user_app.errorhandler(403)
def forbidden(e):
    from routes.user_routes import _ctx
    return render_template('unauthorized.html', reason='Access denied.', **_ctx()), 403

@user_app.errorhandler(404)
def not_found(e):
    from routes.user_routes import _ctx
    return render_template('404.html', **_ctx()), 404

#  SocketIO handlers 
@socketio.on('join_auction')
def on_join(data):
    pid = data.get('product_id')
    if pid:
        join_room(f'auction_{pid}')

@socketio.on('leave_auction')
def on_leave(data):
    pid = data.get('product_id')
    if pid:
        leave_room(f'auction_{pid}')

@socketio.on('join_user_room')
def on_join_user(data):
    uid = data.get('user_id')
    if uid:
        join_room(f'user_{uid}')

@socketio.on('chat_message')
def on_chat(data):
    pid  = data.get('product_id')
    msg  = (data.get('message') or '').strip()[:200]
    user = data.get('username', 'Guest')
    uid  = data.get('user_id')
    if not pid or not msg:
        return
    save_chat_message(pid, uid, user, msg)
    emit('chat_message', {
        'username': user, 'message': msg, 'is_system': False,
        'created_at': datetime.now().strftime('%H:%M'),
    }, room=f'auction_{pid}')

@socketio.on('ping_auction')
def on_ping(data):
    pid = data.get('product_id')
    if not pid:
        return
    conn = get_raw_conn()
    p = conn.execute(
        "SELECT current_bid,bid_count,highest_bidder,auction_end,watcher_count "
        "FROM products WHERE id=?", (pid,)).fetchone()
    conn.close()
    if p:
        payload = {
            'product_id':     pid,
            'current_bid':    p['current_bid'],
            'bid_count':      p['bid_count'],
            'highest_bidder': p['highest_bidder'],
            'seconds_left':   seconds_left(p['auction_end']),
            'watcher_count':  p['watcher_count'],
        }
        # Send full state to the requester immediately
        emit('bid_update', payload)
        # Also broadcast watcher count to everyone in the room
        emit('auction_status', payload, room=f'auction_{pid}')

#  Run 
if __name__ == '__main__':
    init_db()
    print("\n  QuickDealr User App")
    print("  Running at:  http://localhost:5000")
    print("  Login at:    http://localhost:5000/login\n")
    socketio.run(user_app, debug=True, port=5000, allow_unsafe_werkzeug=True)
