# -*- coding: utf-8 -*-
"""
admin_app.py  --  QuickDealr Admin Application
Serves admin panel on port 5001.
Shares the same database as user_app (port 5000).
"""

import os
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template, session, redirect, url_for

from models import init_db, close_db, valid_session, get_wallet
from utils import seconds_left, generate_csrf, ROLE_ADMIN

from routes.auth_routes  import auth_bp
from routes.admin_routes import admin_bp

#  Flask app 
admin_app = Flask(__name__,
                  template_folder='templates',
                  static_folder='static')

admin_app.secret_key = os.environ.get('ADMIN_SECRET_KEY', 'admin_qd_v6_secret_key_change_me')
admin_app.config.update(
    SESSION_COOKIE_NAME    = 'qd_admin_session',
    SESSION_COOKIE_HTTPONLY= True,
    SESSION_COOKIE_SAMESITE= 'Lax',
    SESSION_COOKIE_SECURE  = False,
    PERMANENT_SESSION_LIFETIME = timedelta(hours=4),  # Stricter timeout for admin
)

#  Register blueprints 
admin_app.register_blueprint(auth_bp)   # /login  /register  /logout
admin_app.register_blueprint(admin_bp)  # /  /admin/...

#  Jinja globals 
from datetime import datetime as _dt
def _now_str():
    return _dt.utcnow().strftime('%Y-%m-%d %H:%M:%S')

admin_app.jinja_env.globals.update(
    seconds_left = seconds_left,
    get_wallet   = get_wallet,
    csrf_token   = generate_csrf,
    int          = int,
    now_str      = _now_str,
)

# Jinja filter: convert sqlite3.Row to dict so .get() works in templates
@admin_app.template_filter('as_dict')
def as_dict_filter(row):
    if isinstance(row, dict):
        return row
    try:
        return dict(row)
    except Exception:
        return row

#  DB lifecycle 
@admin_app.teardown_appcontext
def teardown_db(e=None):
    close_db(e)

#  Session enforcement 
@admin_app.before_request
def enforce_admin_session():
    from flask import request
    session.permanent = True  # Honour PERMANENT_SESSION_LIFETIME
    uid   = session.get('user_id')
    token = session.get('session_token')
    if uid and token:
        if not valid_session(uid, token):
            session.clear()
            from flask import flash
            flash('Session expired. Please login.', 'error')
            if not request.path.startswith('/static'):
                return redirect(url_for('auth.login'))
        # Admin inactivity timeout — 20 minutes
        last_active = session.get('_last_active')
        now = datetime.now(timezone.utc)
        if last_active:
            last_active_dt = datetime.fromisoformat(last_active)
            if last_active_dt.tzinfo is None:
                last_active_dt = last_active_dt.replace(tzinfo=timezone.utc)
            elapsed = (now - last_active_dt).total_seconds()
            if elapsed > 1200:  # 20 minutes
                session.clear()
                from flask import flash
                flash('Admin session timed out due to inactivity.', 'error')
                if not request.path.startswith('/static'):
                    return redirect(url_for('auth.login'))
        session['_last_active'] = now.isoformat()

#  Admin access guard 
@admin_app.before_request
def block_non_admin():
    """Block any non-admin who somehow gets a session on this port."""
    from flask import request
    # Skip login/register/static
    if request.endpoint in ('auth.login', 'auth.register', 'auth.logout', 'static', None):
        return
    role = session.get('role', '')
    if session.get('user_id') and role != ROLE_ADMIN:
        session.clear()
        from flask import flash
        flash('Admin access only. Your session has been cleared.', 'error')
        return redirect(url_for('auth.login'))

#  Error handlers 
@admin_app.errorhandler(403)
def forbidden(e):
    return render_template('unauthorized.html', reason='Admin access required.'), 403

@admin_app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

#  Run 
if __name__ == '__main__':
    init_db()
    print("\n  QuickDealr Admin App")
    print("  Running at:  http://localhost:5001")
    print("  Login:       admin / admin123\n")
    admin_app.run(debug=True, port=5001)
