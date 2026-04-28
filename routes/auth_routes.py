# -*- coding: utf-8 -*-
"""
routes/auth_routes.py
Auth blueprint: login, register, logout.
Registered in BOTH user_app and admin_app.
"""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash)
from werkzeug.security import generate_password_hash, check_password_hash
from utils import (redirect_if_logged_in, get_ip, generate_csrf, validate_csrf,
                   validate_email, validate_password_strength,
                   ROLE_BUYER, ROLE_SELLER, ROLE_ADMIN)
import models

auth_bp = Blueprint('auth', __name__, template_folder='../templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
@redirect_if_logged_in
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('auth/login.html')

        user = models.get_user_by_username(username)
        if not user or not check_password_hash(user['password'], password):
            models.log_security(None, get_ip(), 'login_fail', f'username={username}')
            flash('Invalid credentials.', 'error')
            return render_template('auth/login.html')

        token = models.create_session_token(user['id'], get_ip())
        session.clear()
        session.update({
            'user_id':       user['id'],
            'username':      user['username'],
            'role':          user['role'],
            'session_token': token,
        })
        flash(f"Welcome back, {username}!", 'success')

        role = user['role']
        if role == ROLE_ADMIN:
            return redirect(url_for('admin.dashboard'))
        elif role == ROLE_SELLER:
            return redirect(url_for('seller.dashboard'))
        else:
            return redirect(url_for('buyer.home'))

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@redirect_if_logged_in
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        email    = request.form.get('email', '').strip()
        role     = request.form.get('role', 'buyer')

        # Validate role
        if role not in (ROLE_BUYER, ROLE_SELLER):
            flash('Invalid role.', 'error')
            return render_template('auth/register.html')

        # Validate username
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters.', 'error')
            return render_template('auth/register.html')

        # Validate email
        if not email or not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('auth/register.html')

        # Validate password strength
        ok, reason = validate_password_strength(password)
        if not ok:
            flash(reason, 'error')
            return render_template('auth/register.html')

        # Confirm match
        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/register.html')

        db = models.get_db()
        if db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone():
            flash('Username already taken.', 'error')
            return render_template('auth/register.html')
        if db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone():
            flash('Email already registered.', 'error')
            return render_template('auth/register.html')

        models.create_user(username, generate_password_hash(password),
                           email, role, wallet=1000.0)
        flash('Account created! You have ₹1000 welcome bonus. Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
def logout():
    uid   = session.get('user_id')
    token = session.get('session_token')
    if uid and token:
        models.invalidate_session(uid, token)
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('auth.login'))
