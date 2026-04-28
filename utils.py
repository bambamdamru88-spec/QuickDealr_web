# -*- coding: utf-8 -*-
"""
utils.py - Shared utility functions
Used by both admin_app and user_app.
"""

import re
import secrets
from datetime import datetime
from functools import wraps
from io import BytesIO

from flask import session, redirect, url_for, request, flash, jsonify

ROLE_BUYER  = 'buyer'
ROLE_SELLER = 'seller'
ROLE_ADMIN  = 'admin'

#  Time 

def seconds_left(auction_end_str):
    if not auction_end_str:
        return 0
    try:
        end = datetime.strptime(str(auction_end_str)[:19], '%Y-%m-%d %H:%M:%S')
        return max(0, int((end - datetime.now()).total_seconds()))
    except Exception:
        return 0


def get_ip():
    return (request.headers.get('X-Forwarded-For') or
            request.remote_addr or 'unknown').split(',')[0].strip()


#  Validation 

def validate_email(email):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))


def validate_phone(phone):
    return bool(re.match(r'^[6-9]\d{9}$', phone.replace(' ', '').replace('-', '')))


def validate_pincode(pin):
    return bool(re.match(r'^\d{6}$', pin))


def validate_card_number(num):
    return bool(re.match(r'^\d{16}$', num.replace(' ', '')))


def validate_expiry(exp):
    return bool(re.match(r'^(0[1-9]|1[0-2])\/\d{2}$', exp.strip()))


def validate_cvv(cvv):
    return bool(re.match(r'^\d{3,4}$', cvv.strip()))


def validate_password_strength(password):
    """Returns (ok, reason). Minimum 8 chars, 1 uppercase, 1 digit."""
    if not password or len(password) < 8:
        return False, 'Password must be at least 8 characters.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must contain at least one uppercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    return True, 'OK'


#  CSRF 

def generate_csrf():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_hex(24)
    return session['_csrf']


def validate_csrf(token):
    return bool(token and token == session.get('_csrf'))


#  Auth decorators 

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please login to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def buyer_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        role = session.get('role', '')
        if role != ROLE_BUYER:
            flash('This page is for buyers only.', 'error')
            return redirect(_home_for_role(role))
        return f(*args, **kwargs)
    return decorated


def seller_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        role = session.get('role', '')
        if role != ROLE_SELLER:
            flash('This page is for sellers only.', 'error')
            return redirect(_home_for_role(role))
        return f(*args, **kwargs)
    return decorated


def admin_only(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        role = session.get('role', '')
        if role != ROLE_ADMIN:
            flash('Admin access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def buyer_or_seller(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        role = session.get('role', '')
        if role not in (ROLE_BUYER, ROLE_SELLER):
            flash('Please login to continue.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def redirect_if_logged_in(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('user_id'):
            return redirect(_home_for_role(session.get('role', '')))
        return f(*args, **kwargs)
    return decorated


def _home_for_role(role):
    if role == ROLE_ADMIN:
        return url_for('admin.dashboard')
    elif role == ROLE_SELLER:
        return url_for('seller.dashboard')
    return url_for('buyer.home')


#  API helpers 

def api_ok(data=None, message='OK'):
    return jsonify({'status': 'success', 'message': message, 'data': data})


def api_err(message='Error', code=400):
    return jsonify({'status': 'error', 'message': message}), code


#  Invoice PDF 

def generate_invoice_pdf(order, addr):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    except ImportError:
        return None

    buf    = BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4,
                               leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle('T', parent=styles['Heading1'],
                                 fontSize=22, textColor=colors.HexColor('#0f172a'), spaceAfter=6)
    sub_style   = ParagraphStyle('S', parent=styles['Normal'],
                                 fontSize=10, textColor=colors.grey)

    story.append(Paragraph("QuickDealr", title_style))
    story.append(Paragraph("Tax Invoice / Order Receipt", sub_style))
    story.append(Spacer(1, 0.4*cm))

    info_data = [
        ['Order ID:', f'#QD{order["id"]:06d}',    'Date:',           str(order['created_at'])[:10]],
        ['Payment:',  order['payment_method'].upper(), 'Status:',    order['status']],
        ['Buyer:',    order['buyer_name'],          'Pay Status:',   order['payment_status'].upper()],
    ]
    if order['transaction_id']:
        info_data.append(['Transaction ID:', order['transaction_id'], '', ''])

    info_t = Table(info_data, colWidths=[3*cm, 6*cm, 3*cm, 5*cm])
    info_t.setStyle(TableStyle([
        ('FONTSIZE',  (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), colors.grey),
        ('TEXTCOLOR', (2,0), (2,-1), colors.grey),
        ('FONTNAME',  (1,0), (1,-1), 'Helvetica-Bold'),
        ('FONTNAME',  (3,0), (3,-1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Delivery Address",
                            ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceAfter=4)))
    if addr:
        addr_text = (f"{addr['full_name'] if 'full_name' in addr.keys() else ''} | {addr['phone'] if 'phone' in addr.keys() else ''}<br/>"
                     f"{addr['full_address'] if 'full_address' in addr.keys() else ''}")
        if 'landmark' in addr.keys() and addr['landmark']:
            addr_text += f", Near {addr['landmark']}"
        addr_text += f"<br/>{addr['city'] if 'city' in addr.keys() else ''}, {addr['state'] if 'state' in addr.keys() else ''} - {addr['pincode'] if 'pincode' in addr.keys() else ''}"
        story.append(Paragraph(addr_text, styles['Normal']))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Order Items",
                            ParagraphStyle('H2', parent=styles['Heading2'], fontSize=12, spaceAfter=4)))
    item_data = [['Product', 'Qty', 'Unit Price', 'Amount']]
    item_data.append([
        order['product_name'],
        str(order['quantity']),
        f"Rs.{order['amount']/order['quantity']:.2f}",
        f"Rs.{order['amount']:.2f}",
    ])
    item_t = Table(item_data, colWidths=[9*cm, 2*cm, 4*cm, 4*cm])
    item_t.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,0), colors.HexColor('#0f172a')),
        ('TEXTCOLOR',   (0,0), (-1,0), colors.white),
        ('FONTNAME',    (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE',    (0,0), (-1,-1), 10),
        ('ALIGN',       (1,0), (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#dee2e6')),
        ('TOPPADDING',  (0,0), (-1,-1), 6),
        ('BOTTOMPADDING',(0,0), (-1,-1), 6),
    ]))
    story.append(item_t)
    story.append(Spacer(1, 0.3*cm))

    summary_data = [
        ['Subtotal:',     f"Rs.{order['amount']:.2f}"],
        ['Delivery Fee:', f"Rs.{order['delivery_fee']:.2f}"],
        ['Discount:',     f"-Rs.{order['discount']:.2f}"],
        ['TOTAL:',        f"Rs.{order['total_amount']:.2f}"],
    ]
    sum_t = Table(summary_data, colWidths=[13*cm, 6*cm])
    sum_t.setStyle(TableStyle([
        ('ALIGN',        (1,0), (1,-1), 'RIGHT'),
        ('FONTSIZE',     (0,0), (-1,-1), 10),
        ('FONTNAME',     (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE',     (0,-1), (-1,-1), 12),
        ('LINEABOVE',    (0,-1), (-1,-1), 1.5, colors.HexColor('#0f172a')),
        ('BOTTOMPADDING',(0,0), (-1,-1), 5),
    ]))
    story.append(sum_t)
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Thank you for shopping with QuickDealr!",
                            ParagraphStyle('Footer', parent=styles['Normal'],
                                           fontSize=10, textColor=colors.grey, alignment=1)))
    doc.build(story)
    buf.seek(0)
    return buf
