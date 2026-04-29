# -*- coding: utf-8 -*-
"""
models.py - Shared database access layer
Both admin_app and user_app import from here.
Single source of truth for all DB operations.
Migrated to PostgreSQL (psycopg2).
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta
from flask import g
from werkzeug.utils import secure_filename

import psycopg2
import psycopg2.extras

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA   = os.path.join(BASE_DIR, 'database', 'schema.sql')

DATABASE_URL = os.environ.get('DATABASE_URL')


# ── Connection ─────────────────────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(DATABASE_URL)
        g.db.cursor_factory = psycopg2.extras.RealDictCursor
    return g.db


class _DBWrapper:
    """Makes psycopg2 connection behave like sqlite3 — supports db.execute() and ? placeholders."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        sql = sql.replace('?', '%s')
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def cursor(self):
        return self._conn.cursor()


def get_db():
    if 'db' not in g:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor_factory = psycopg2.extras.RealDictCursor
        g.db = _DBWrapper(conn)
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db:
        db.close()


def get_raw_conn():
    """Get a plain connection outside of request context (e.g., SocketIO handlers)."""
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    return conn


def _fetchone(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _fetchall(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _execute(conn, sql, params=()):
    with conn.cursor() as cur:
        cur.execute(sql, params)


def _execute_returning(conn, sql, params=()):
    """Execute an INSERT ... RETURNING id and return the id."""
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()['id']


def init_db():
    """Create all tables from schema and seed admin account."""
    from werkzeug.security import generate_password_hash
    conn = psycopg2.connect(DATABASE_URL)
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    with open(SCHEMA, encoding='utf-8') as f:
        schema_sql = f.read()
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username,password,role,email,wallet) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (username) DO NOTHING",
                ('admin', generate_password_hash('admin123'), 'admin', 'admin@quickdealr.com', 0.0))
        conn.commit()
    except Exception:
        conn.rollback()
    conn.close()
    print("[DB] Initialized (PostgreSQL)")


# ── Users ──────────────────────────────────────────────────────────────────────

def get_user_by_id(uid):
    return _fetchone(get_db(), "SELECT * FROM users WHERE id=%s", (uid,))


def get_user_by_username(username):
    return _fetchone(get_db(),
        "SELECT * FROM users WHERE username=%s AND is_active=1", (username,))


def get_all_users():
    return _fetchall(get_db(), "SELECT * FROM users ORDER BY created_at DESC")


def create_user(username, password_hash, email, role, wallet=0.0):
    db = get_db()
    _execute(db,
        "INSERT INTO users (username,password,email,role,wallet) VALUES (%s,%s,%s,%s,%s)",
        (username, password_hash, email, role, wallet))
    db.commit()


def toggle_user_active(uid):
    db = get_db()
    user = _fetchone(db, "SELECT is_active FROM users WHERE id=%s", (uid,))
    if user:
        new_state = 0 if user['is_active'] else 1
        _execute(db, "UPDATE users SET is_active=%s WHERE id=%s", (new_state, uid))
        db.commit()
        return new_state
    return None


def toggle_user_whitelist(uid):
    db = get_db()
    user = _fetchone(db, "SELECT is_whitelisted FROM users WHERE id=%s", (uid,))
    if user is None:
        return None
    new_state = 0 if user['is_whitelisted'] else 1
    _execute(db, "UPDATE users SET is_whitelisted=%s WHERE id=%s", (new_state, uid))
    db.commit()
    return new_state


def store_uploaded_file(user_id, original_name, file_path, size_bytes):
    db = get_db()
    try:
        _execute(db,
            "INSERT INTO uploaded_files (user_id, original_name, file_path, size_bytes) VALUES (%s,%s,%s,%s)",
            (user_id, original_name, file_path, size_bytes))
        db.commit()
    except Exception:
        db.rollback()


# ── Sessions ───────────────────────────────────────────────────────────────────

def create_session_token(user_id, ip_address):
    token   = secrets.token_hex(32)
    expires = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    _execute(db, "UPDATE sessions SET is_valid=0 WHERE user_id=%s", (user_id,))
    _execute(db,
        "INSERT INTO sessions (user_id,token,ip_address,expires_at) VALUES (%s,%s,%s,%s)",
        (user_id, token, ip_address, expires))
    _execute(db, "UPDATE users SET session_token=%s WHERE id=%s", (token, user_id))
    db.commit()
    return token


def invalidate_session(user_id, token):
    db = get_db()
    _execute(db, "UPDATE sessions SET is_valid=0 WHERE user_id=%s AND token=%s", (user_id, token))
    _execute(db, "UPDATE users SET session_token=NULL WHERE id=%s", (user_id,))
    db.commit()


def valid_session(user_id, token):
    if not token:
        return False
    row = _fetchone(get_db(),
        "SELECT id FROM sessions WHERE user_id=%s AND token=%s AND is_valid=1 "
        "AND expires_at > NOW()", (user_id, token))
    return row is not None


# ── Wallet ─────────────────────────────────────────────────────────────────────

def get_wallet(user_id):
    row = _fetchone(get_db(), "SELECT wallet FROM users WHERE id=%s", (user_id,))
    return float(row['wallet']) if row else 0.0


def credit_wallet(user_id, amount, description='', method='system'):
    db = get_db()
    _execute(db, "UPDATE users SET wallet=wallet+%s WHERE id=%s", (amount, user_id))
    _execute(db,
        "INSERT INTO wallet_transactions (user_id,amount,type,method,status,description) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (user_id, amount, 'credit', method, 'success', description))
    db.commit()


def deduct_wallet(user_id, amount, description='', method='system'):
    db = get_db()
    _execute(db, "UPDATE users SET wallet=wallet-%s WHERE id=%s", (amount, user_id))
    _execute(db,
        "INSERT INTO wallet_transactions (user_id,amount,type,method,status,description) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (user_id, amount, 'debit', method, 'success', description))
    db.commit()


def get_wallet_transactions(user_id, limit=30):
    return _fetchall(get_db(),
        "SELECT * FROM wallet_transactions WHERE user_id=%s ORDER BY created_at DESC LIMIT %s",
        (user_id, limit))


def get_all_wallet_transactions(limit=100):
    return _fetchall(get_db(),
        "SELECT wt.*, u.username FROM wallet_transactions wt "
        "JOIN users u ON wt.user_id=u.id ORDER BY wt.created_at DESC LIMIT %s",
        (limit,))


# ── Products ───────────────────────────────────────────────────────────────────

def get_products(approved_only=True, is_auction=None, seller_id=None, category=None,
                 search=None, sort='latest', min_price=None, max_price=None):
    sql    = "SELECT * FROM products WHERE 1=1"
    params = []
    if approved_only:
        sql += " AND approved=1"
    if is_auction is not None:
        sql += " AND is_auction=%s"; params.append(is_auction)
    if seller_id:
        sql += " AND seller_id=%s"; params.append(seller_id)
    if category:
        sql += " AND category=%s"; params.append(category)
    if search:
        sql += " AND (name ILIKE %s OR description ILIKE %s)"; params += [f'%{search}%', f'%{search}%']
    if min_price is not None:
        sql += " AND price>=%s"; params.append(min_price)
    if max_price is not None:
        sql += " AND price<=%s"; params.append(max_price)
    order_map = {'latest': 'created_at DESC', 'price_asc': 'price ASC',
                 'price_desc': 'price DESC', 'popular': 'views DESC',
                 'highest_bid': 'current_bid DESC'}
    sql += f" ORDER BY {order_map.get(sort, 'created_at DESC')}"
    return _fetchall(get_db(), sql, params)


def get_product(pid, approved_only=True):
    sql = "SELECT * FROM products WHERE id=%s"
    if approved_only:
        sql += " AND approved=1"
    return _fetchone(get_db(), sql, (pid,))


def create_product(name, desc, price, category, image, seller_id, seller_name,
                   stock, is_auction=0, auction_hours=24, start_price=0):
    auction_end = None
    if is_auction:
        auction_end = (datetime.now() + timedelta(hours=auction_hours)).strftime('%Y-%m-%d %H:%M:%S')
    db = get_db()
    _execute(db,
        "INSERT INTO products (name,description,price,category,image,seller_id,seller_name,"
        "approved,stock,is_auction,auction_end,start_price,current_bid) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s,%s)",
        (name, desc, price, category, image, seller_id, seller_name,
         stock, is_auction, auction_end, start_price, start_price))
    db.commit()


def approve_product(pid, seller_id=None):
    db = get_db()
    p  = _fetchone(db, "SELECT seller_id, name FROM products WHERE id=%s", (pid,))
    if p:
        _execute(db, "UPDATE products SET approved=1, status='approved' WHERE id=%s", (pid,))
        db.commit()
    return p


def reject_product(pid):
    db = get_db()
    p  = _fetchone(db, "SELECT seller_id, name FROM products WHERE id=%s", (pid,))
    if p:
        _execute(db, "UPDATE products SET approved=0, status='rejected' WHERE id=%s", (pid,))
        db.commit()
    return p


def deactivate_product(pid):
    db = get_db()
    p  = _fetchone(db, "SELECT seller_id, name, approved FROM products WHERE id=%s", (pid,))
    if p:
        _execute(db, "UPDATE products SET approved=0, status='inactive' WHERE id=%s", (pid,))
        db.commit()
    return p


def delete_product_admin(pid):
    db = get_db()
    p  = _fetchone(db, "SELECT seller_id, name FROM products WHERE id=%s", (pid,))
    if p:
        _execute(db, "DELETE FROM products WHERE id=%s", (pid,))
        db.commit()
    return p


def get_categories():
    return _fetchall(get_db(), "SELECT * FROM categories ORDER BY name")


def get_active_categories(is_auction=0):
    return _fetchall(get_db(),
        "SELECT DISTINCT category FROM products WHERE approved=1 AND is_auction=%s ORDER BY category",
        (is_auction,))


# ── Orders ─────────────────────────────────────────────────────────────────────

def get_orders(buyer_id=None, limit=None):
    sql = "SELECT * FROM orders WHERE 1=1"
    params = []
    if buyer_id:
        sql += " AND buyer_id=%s"; params.append(buyer_id)
    sql += " ORDER BY created_at DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return _fetchall(get_db(), sql, params)


def get_order(oid, buyer_id=None):
    sql = "SELECT * FROM orders WHERE id=%s"
    params = [oid]
    if buyer_id:
        sql += " AND buyer_id=%s"; params.append(buyer_id)
    return _fetchone(get_db(), sql, params)


def create_order(buyer_id, buyer_name, pid, pname, pimage, amount, quantity,
                 delivery_fee, discount, total_amount, payment_method,
                 payment_status, transaction_id, address_id, address_snapshot):
    db = get_db()
    oid = _execute_returning(db,
        "INSERT INTO orders (buyer_id,buyer_name,product_id,product_name,product_image,"
        "amount,quantity,delivery_fee,discount,total_amount,payment_method,"
        "payment_status,transaction_id,address_id,address_snapshot) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
        (buyer_id, buyer_name, pid, pname, pimage, amount, quantity,
         delivery_fee, discount, total_amount, payment_method,
         payment_status, transaction_id, address_id, address_snapshot))
    db.commit()
    return oid


def update_order_status(oid, status):
    db = get_db()
    o  = _fetchone(db, "SELECT * FROM orders WHERE id=%s", (oid,))
    if o:
        _execute(db, "UPDATE orders SET status=%s,updated_at=NOW() WHERE id=%s", (status, oid))
        db.commit()
    return o


def cancel_order(oid, buyer_id):
    db = get_db()
    o  = _fetchone(db, "SELECT * FROM orders WHERE id=%s AND buyer_id=%s", (oid, buyer_id))
    if not o or o['status'] not in ('Placed', 'Confirmed'):
        return False, o
    _execute(db, "UPDATE orders SET status='Cancelled', updated_at=NOW() WHERE id=%s", (oid,))
    db.commit()
    if o['payment_status'] == 'paid' and o['payment_method'] in ('wallet', 'card', 'upi', 'qr'):
        refund_amt = float(o['total_amount'] or o['amount'] or 0)
        if refund_amt > 0:
            credit_wallet(buyer_id, refund_amt, f'Refund for cancelled order #QD{oid:06d}', 'refund')
    return True, o


def get_seller_orders(seller_id):
    return _fetchall(get_db(),
        "SELECT o.*, p.name as pname FROM orders o "
        "JOIN products p ON o.product_id=p.id "
        "WHERE p.seller_id=%s ORDER BY o.created_at DESC",
        (seller_id,))


# ── Returns ────────────────────────────────────────────────────────────────────

def get_return_for_order(order_id):
    return _fetchone(get_db(),
        "SELECT * FROM returns WHERE order_id=%s", (order_id,))


def create_return(order_id, user_id, reason, description, image_path=''):
    db = get_db()
    _execute(db,
        "INSERT INTO returns (order_id, user_id, reason, description, image_path, created_at) "
        "VALUES (%s,%s,%s,%s,%s,%s)",
        (order_id, user_id, reason, description, image_path,
         datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')))
    db.commit()


def get_all_returns():
    return _fetchall(get_db(),
        "SELECT r.*, o.product_name, o.product_image, u.username "
        "FROM returns r "
        "JOIN orders o ON r.order_id = o.id "
        "JOIN users u ON r.user_id = u.id "
        "ORDER BY r.created_at DESC")


# ── Cart ───────────────────────────────────────────────────────────────────────

def get_cart(buyer_id):
    return _fetchall(get_db(),
        "SELECT c.id as cid, c.quantity, p.id as pid, p.name, p.price, p.image, p.category "
        "FROM cart c JOIN products p ON c.product_id=p.id WHERE c.buyer_id=%s",
        (buyer_id,))


def cart_item_count(buyer_id):
    r = _fetchone(get_db(),
        "SELECT SUM(quantity) as t FROM cart WHERE buyer_id=%s", (buyer_id,))
    return r['t'] or 0


def add_to_cart(buyer_id, pid):
    db = get_db()
    ex = _fetchone(db, "SELECT id FROM cart WHERE buyer_id=%s AND product_id=%s", (buyer_id, pid))
    if ex:
        _execute(db, "UPDATE cart SET quantity=quantity+1 WHERE id=%s", (ex['id'],))
    else:
        _execute(db, "INSERT INTO cart (buyer_id,product_id) VALUES (%s,%s)", (buyer_id, pid))
    db.commit()


def remove_from_cart(cid, buyer_id):
    db = get_db()
    _execute(db, "DELETE FROM cart WHERE id=%s AND buyer_id=%s", (cid, buyer_id))
    db.commit()


def clear_cart(buyer_id):
    db = get_db()
    _execute(db, "DELETE FROM cart WHERE buyer_id=%s", (buyer_id,))
    db.commit()


# ── Addresses ──────────────────────────────────────────────────────────────────

def get_addresses(user_id):
    return _fetchall(get_db(),
        "SELECT * FROM addresses WHERE user_id=%s ORDER BY is_default DESC, id DESC",
        (user_id,))


def get_address(aid, user_id):
    return _fetchone(get_db(),
        "SELECT * FROM addresses WHERE id=%s AND user_id=%s", (aid, user_id))


def create_address(user_id, full_name, phone, city, state, pincode, landmark, full_address):
    db = get_db()
    is_default = 1 if not _fetchone(db, "SELECT id FROM addresses WHERE user_id=%s", (user_id,)) else 0
    _execute(db,
        "INSERT INTO addresses (user_id,full_name,phone,city,state,pincode,landmark,full_address,is_default) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (user_id, full_name, phone, city, state, pincode, landmark, full_address, is_default))
    db.commit()


def delete_address(aid, user_id):
    db = get_db()
    _execute(db, "DELETE FROM addresses WHERE id=%s AND user_id=%s", (aid, user_id))
    db.commit()


def set_default_address(aid, user_id):
    db = get_db()
    _execute(db, "UPDATE addresses SET is_default=0 WHERE user_id=%s", (user_id,))
    _execute(db, "UPDATE addresses SET is_default=1 WHERE id=%s AND user_id=%s", (aid, user_id))
    db.commit()


# ── Wishlist ───────────────────────────────────────────────────────────────────

def get_wishlist_ids(buyer_id):
    rows = _fetchall(get_db(),
        "SELECT product_id FROM wishlist WHERE buyer_id=%s", (buyer_id,))
    return [r['product_id'] for r in rows]


def toggle_wishlist(buyer_id, pid):
    db = get_db()
    ex = _fetchone(db, "SELECT id FROM wishlist WHERE buyer_id=%s AND product_id=%s", (buyer_id, pid))
    if ex:
        _execute(db, "DELETE FROM wishlist WHERE buyer_id=%s AND product_id=%s", (buyer_id, pid))
        db.commit()
        return False
    try:
        _execute(db, "INSERT INTO wishlist (buyer_id,product_id) VALUES (%s,%s)", (buyer_id, pid))
        db.commit()
    except Exception:
        db.rollback()
    return True


def get_wishlist_products(buyer_id):
    return _fetchall(get_db(),
        "SELECT p.* FROM wishlist w JOIN products p ON w.product_id=p.id WHERE w.buyer_id=%s",
        (buyer_id,))


# ── Bids ───────────────────────────────────────────────────────────────────────

def get_bids(product_id, limit=20):
    return _fetchall(get_db(),
        "SELECT * FROM bids WHERE product_id=%s ORDER BY amount DESC LIMIT %s",
        (product_id, limit))


def get_user_bids(user_id, limit=10):
    return _fetchall(get_db(),
        "SELECT b.*, p.name as product_name, p.image as product_image, "
        "p.current_bid, p.auction_end, p.is_auction, "
        "(p.highest_bid_uid = b.user_id) as is_leading "
        "FROM bids b JOIN products p ON b.product_id = p.id "
        "WHERE b.user_id = %s ORDER BY b.created_at DESC LIMIT %s",
        (user_id, limit))


def get_user_won_auctions(user_id, limit=6):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return _fetchall(get_db(),
        "SELECT * FROM products WHERE highest_bid_uid=%s AND is_auction=1 "
        "AND auction_end < %s AND approved=1 ORDER BY auction_end DESC LIMIT %s",
        (user_id, now, limit))


def get_user_active_auctions(user_id, limit=6):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return _fetchall(get_db(),
        "SELECT DISTINCT p.*, (p.highest_bid_uid = %s) as is_leading "
        "FROM products p JOIN bids b ON b.product_id = p.id "
        "WHERE b.user_id = %s AND p.is_auction = 1 AND p.auction_end > %s AND p.approved = 1 "
        "ORDER BY p.auction_end ASC LIMIT %s",
        (user_id, user_id, now, limit))


def get_leaderboard(product_id, limit=5):
    return _fetchall(get_db(),
        "SELECT username, MAX(amount) as top FROM bids WHERE product_id=%s "
        "GROUP BY username ORDER BY top DESC LIMIT %s",
        (product_id, limit))


def place_bid(product_id, user_id, username, amount, ip_address):
    db = get_db()
    prev = _fetchone(db,
        "SELECT highest_bidder, highest_bid_uid, bid_count FROM products WHERE id=%s",
        (product_id,))
    _execute(db,
        "INSERT INTO bids (product_id,user_id,username,amount,ip_address) VALUES (%s,%s,%s,%s,%s)",
        (product_id, user_id, username, amount, ip_address))
    _execute(db,
        "UPDATE products SET current_bid=%s,bid_count=bid_count+1,highest_bidder=%s,highest_bid_uid=%s WHERE id=%s",
        (amount, username, user_id, product_id))
    db.commit()
    return prev


# ── Notifications ──────────────────────────────────────────────────────────────

def add_notification(user_id, message, ntype='info'):
    db = get_db()
    _execute(db, "INSERT INTO notifications (user_id,message,ntype) VALUES (%s,%s,%s)",
             (user_id, message, ntype))
    db.commit()


def get_notifications(user_id, unread_only=False, limit=30):
    sql = "SELECT * FROM notifications WHERE user_id=%s"
    params = [user_id]
    if unread_only:
        sql += " AND read=0"
    sql += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    return _fetchall(get_db(), sql, params)


def mark_notifications_read(user_id):
    db = get_db()
    _execute(db, "UPDATE notifications SET read=1 WHERE user_id=%s", (user_id,))
    db.commit()


def unread_count(user_id):
    r = _fetchone(get_db(),
        "SELECT COUNT(*) as n FROM notifications WHERE user_id=%s AND read=0",
        (user_id,))
    return r['n'] or 0


# ── Messages ───────────────────────────────────────────────────────────────────

def get_conversations(user_id):
    return _fetchall(get_db(),
        "SELECT DISTINCT m.auction_id, p.name as product_name, "
        "CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END as other_id, "
        "u.username as other_name, m.created_at "
        "FROM messages m "
        "JOIN products p ON m.auction_id=p.id "
        "JOIN users u ON u.id=(CASE WHEN m.sender_id=%s THEN m.receiver_id ELSE m.sender_id END) "
        "WHERE m.sender_id=%s OR m.receiver_id=%s "
        "ORDER BY m.created_at DESC",
        (user_id, user_id, user_id, user_id))


def get_message_thread(auction_id, user_id, other_id):
    return _fetchall(get_db(),
        "SELECT m.*, u.username FROM messages m JOIN users u ON m.sender_id=u.id "
        "WHERE m.auction_id=%s AND "
        "(m.sender_id=%s AND m.receiver_id=%s OR m.sender_id=%s AND m.receiver_id=%s) "
        "ORDER BY m.created_at ASC",
        (auction_id, user_id, other_id, other_id, user_id))


def send_message(auction_id, sender_id, receiver_id, message):
    db = get_db()
    _execute(db,
        "INSERT INTO messages (auction_id,sender_id,receiver_id,message) VALUES (%s,%s,%s,%s)",
        (auction_id, sender_id, receiver_id, message))
    db.commit()


def mark_messages_read(auction_id, receiver_id):
    db = get_db()
    _execute(db, "UPDATE messages SET read=1 WHERE auction_id=%s AND receiver_id=%s",
             (auction_id, receiver_id))
    db.commit()


# ── Auction tokens / anti-bot ──────────────────────────────────────────────────

def issue_auction_token(user_id, product_id):
    token = secrets.token_hex(16)
    db = get_db()
    _execute(db,
        "INSERT INTO auction_tokens (user_id,product_id,token) VALUES (%s,%s,%s) "
        "ON CONFLICT (user_id,product_id) "
        "DO UPDATE SET token=EXCLUDED.token, issued_at=NOW(), interacted=0",
        (user_id, product_id, token))
    db.commit()
    return token


def mark_interaction(user_id, product_id):
    db = get_db()
    _execute(db, "UPDATE auction_tokens SET interacted=1 WHERE user_id=%s AND product_id=%s",
             (user_id, product_id))
    db.commit()


def validate_auction_token(user_id, product_id, token, page_dwell=3):
    db  = get_db()
    row = _fetchone(db,
        "SELECT * FROM auction_tokens WHERE user_id=%s AND product_id=%s",
        (user_id, product_id))
    if not row or row['token'] != token:
        return False, 'Invalid session token. Reload the page.'
    issued = row['issued_at']
    if isinstance(issued, str):
        issued = datetime.strptime(str(issued)[:19], '%Y-%m-%d %H:%M:%S')
    if (datetime.now() - issued).total_seconds() < page_dwell:
        return False, f'Please wait {page_dwell}s before bidding.'
    if not row['interacted']:
        return False, 'Please scroll or click on the page first.'
    return True, 'OK'


def log_bid_rate(user_id, product_id, ip):
    db = get_db()
    _execute(db,
        "INSERT INTO bid_rate_log (user_id,product_id,ip_address) VALUES (%s,%s,%s)",
        (user_id, product_id, ip))
    db.commit()


def check_bid_rate(user_id, product_id, ip, cooldown=5, window=10, max_bids=3, block_min=15):
    db = get_db()
    if _fetchone(db,
        "SELECT id FROM blocked_ips WHERE ip_address=%s AND "
        "(expires_at IS NULL OR expires_at > NOW())", (ip,)):
        return False, 'Your IP is temporarily blocked.'
    now          = datetime.now()
    cooldown_cut = (now - timedelta(seconds=cooldown)).strftime('%Y-%m-%d %H:%M:%S')
    window_cut   = (now - timedelta(seconds=window)).strftime('%Y-%m-%d %H:%M:%S')
    if _fetchone(db,
        "SELECT id FROM bid_rate_log WHERE user_id=%s AND product_id=%s AND created_at>%s LIMIT 1",
        (user_id, product_id, cooldown_cut)):
        return False, f'Wait {cooldown}s between bids.'
    n = _fetchone(db,
        "SELECT COUNT(*) as n FROM bid_rate_log WHERE user_id=%s AND created_at>%s",
        (user_id, window_cut))['n']
    if n >= max_bids:
        exp = (now + timedelta(minutes=block_min)).strftime('%Y-%m-%d %H:%M:%S')
        try:
            _execute(db,
                "INSERT INTO blocked_ips (ip_address,reason,expires_at) VALUES (%s,%s,%s) "
                "ON CONFLICT (ip_address) DO UPDATE SET reason=EXCLUDED.reason, expires_at=EXCLUDED.expires_at",
                (ip, 'Automated bidding detected', exp))
            db.commit()
        except Exception:
            db.rollback()
        return False, 'Suspicious activity. Temporarily blocked.'
    return True, 'OK'


# ── Security ───────────────────────────────────────────────────────────────────

def log_security(user_id, ip, action, detail=''):
    db = get_db()
    _execute(db,
        "INSERT INTO security_log (user_id,ip_address,action,detail) VALUES (%s,%s,%s,%s)",
        (user_id, ip, action, detail))
    db.commit()


def get_security_logs(limit=20):
    return _fetchall(get_db(),
        "SELECT * FROM security_log ORDER BY created_at DESC LIMIT %s", (limit,))


def get_blocked_ips():
    return _fetchall(get_db(),
        "SELECT * FROM blocked_ips WHERE expires_at>NOW() OR expires_at IS NULL")


def unblock_ip(ip):
    db = get_db()
    _execute(db, "DELETE FROM blocked_ips WHERE ip_address=%s", (ip,))
    db.commit()


# ── QR Settings ────────────────────────────────────────────────────────────────

def get_qr_settings():
    return _fetchone(get_db(), "SELECT * FROM qr_settings WHERE id=1")


def update_qr_settings(qr_image, upi_id):
    db = get_db()
    _execute(db,
        "UPDATE qr_settings SET qr_image=%s,upi_id=%s,updated_at=NOW() WHERE id=1",
        (qr_image, upi_id))
    db.commit()


# ── Chat ───────────────────────────────────────────────────────────────────────

def get_chat_messages(product_id, limit=30):
    return _fetchall(get_db(),
        "SELECT * FROM chat_messages WHERE product_id=%s ORDER BY created_at DESC LIMIT %s",
        (product_id, limit))


def save_chat_message(product_id, user_id, username, message):
    conn = get_raw_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO chat_messages (product_id,user_id,username,message) VALUES (%s,%s,%s,%s)",
            (product_id, user_id, username, message))
    conn.commit()
    conn.close()


# ── Watchers ───────────────────────────────────────────────────────────────────

def toggle_watcher(user_id, product_id):
    db = get_db()
    ex = _fetchone(db, "SELECT id FROM watchers WHERE user_id=%s AND product_id=%s",
                   (user_id, product_id))
    if ex:
        _execute(db, "DELETE FROM watchers WHERE user_id=%s AND product_id=%s", (user_id, product_id))
        _execute(db, "UPDATE products SET watcher_count=GREATEST(0,watcher_count-1) WHERE id=%s", (product_id,))
        db.commit()
        return False
    try:
        _execute(db, "INSERT INTO watchers (user_id,product_id) VALUES (%s,%s)", (user_id, product_id))
        _execute(db, "UPDATE products SET watcher_count=watcher_count+1 WHERE id=%s", (product_id,))
        db.commit()
    except Exception:
        db.rollback()
    return True


# ── Promo Codes ────────────────────────────────────────────────────────────────

def get_promo_code(code):
    return _fetchone(get_db(),
        "SELECT * FROM promo_codes WHERE code=%s AND is_active=1", (code,))


def apply_promo(code, subtotal):
    promo = get_promo_code(code.strip().upper())
    if not promo:
        return 0.0, None, "Invalid or inactive promo code."
    if subtotal < promo['min_order']:
        return 0.0, None, f"Minimum order Rs.{promo['min_order']:.0f} required for this code."
    if promo['max_uses'] and promo['used_count'] >= promo['max_uses']:
        return 0.0, None, "This promo code has reached its usage limit."
    if promo['discount_type'] == 'percentage':
        discount = round(subtotal * promo['value'] / 100, 2)
    else:
        discount = min(promo['value'], subtotal)
    return discount, promo, None


def use_promo_code(code):
    db = get_db()
    _execute(db, "UPDATE promo_codes SET used_count=used_count+1 WHERE code=%s", (code,))
    db.commit()


def get_all_promo_codes():
    return _fetchall(get_db(), "SELECT * FROM promo_codes ORDER BY created_at DESC")


def create_promo_code(code, discount_type, value, min_order, max_uses=None):
    db = get_db()
    _execute(db,
        "INSERT INTO promo_codes (code,discount_type,value,min_order,max_uses,is_active) "
        "VALUES (%s,%s,%s,%s,%s,1)",
        (code.strip().upper(), discount_type, value, min_order, max_uses))
    db.commit()


def toggle_promo_code(pid):
    db = get_db()
    _execute(db, "UPDATE promo_codes SET is_active=NOT is_active WHERE id=%s", (pid,))
    db.commit()


def delete_promo_code(pid):
    db = get_db()
    _execute(db, "DELETE FROM promo_codes WHERE id=%s", (pid,))
    db.commit()


# ── Wallet Requests ────────────────────────────────────────────────────────────

def create_wallet_request(user_id, amount, method, transaction_id='', card_last4=''):
    db = get_db()
    _execute(db,
        "INSERT INTO wallet_requests (user_id,amount,method,transaction_id,card_last4,status) "
        "VALUES (%s,%s,%s,%s,%s,'pending')",
        (user_id, amount, method, transaction_id, card_last4))
    db.commit()


def get_wallet_requests(user_id=None, status=None, limit=50):
    sql = ("SELECT wr.*, u.username FROM wallet_requests wr "
           "JOIN users u ON wr.user_id=u.id WHERE 1=1")
    params = []
    if user_id:
        sql += " AND wr.user_id=%s"; params.append(user_id)
    if status:
        sql += " AND wr.status=%s"; params.append(status)
    sql += f" ORDER BY wr.created_at DESC LIMIT {int(limit)}"
    return _fetchall(get_db(), sql, params)


def approve_wallet_request(req_id, admin_id, note=''):
    db  = get_db()
    req = _fetchone(db, "SELECT * FROM wallet_requests WHERE id=%s AND status='pending'", (req_id,))
    if not req:
        return False, "Request not found or already reviewed."
    credit_wallet(req['user_id'], req['amount'],
                  f"Wallet top-up approved (Req #{req_id})", method=req['method'])
    _execute(db,
        "UPDATE wallet_requests SET status='approved',admin_note=%s,reviewed_by=%s,"
        "reviewed_at=NOW() WHERE id=%s",
        (note, admin_id, req_id))
    db.commit()
    add_notification(req['user_id'],
                     f"Rs.{req['amount']:.2f} wallet top-up approved and added to your wallet!",
                     ntype='info')
    return True, "Approved."


def reject_wallet_request(req_id, admin_id, note=''):
    db  = get_db()
    req = _fetchone(db, "SELECT * FROM wallet_requests WHERE id=%s AND status='pending'", (req_id,))
    if not req:
        return False, "Request not found or already reviewed."
    _execute(db,
        "UPDATE wallet_requests SET status='rejected',admin_note=%s,reviewed_by=%s,"
        "reviewed_at=NOW() WHERE id=%s",
        (note, admin_id, req_id))
    db.commit()
    add_notification(req['user_id'],
                     f"Your wallet top-up request of Rs.{req['amount']:.2f} was rejected."
                     + (f" Reason: {note}" if note else ""),
                     ntype='info')
    return True, "Rejected."


# ── Contact Messages ───────────────────────────────────────────────────────────

def create_contact_message(name, email, subject, message):
    db = get_db()
    _execute(db,
        "INSERT INTO contact_messages (name,email,subject,message) VALUES (%s,%s,%s,%s)",
        (name, email, subject, message))
    db.commit()


def get_contact_messages(resolved=None, limit=100):
    sql = "SELECT * FROM contact_messages WHERE 1=1"
    params = []
    if resolved is not None:
        sql += " AND is_resolved=%s"; params.append(1 if resolved else 0)
    sql += f" ORDER BY created_at DESC LIMIT {int(limit)}"
    return _fetchall(get_db(), sql, params)


def resolve_contact_message(mid):
    db = get_db()
    _execute(db, "UPDATE contact_messages SET is_resolved=1 WHERE id=%s", (mid,))
    db.commit()


# ── Image upload helper ────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_image(filename):
    return ('.' in filename and
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS)


def save_uploaded_image(file_obj, subfolder='products'):
    if not file_obj or not file_obj.filename:
        return ''
    if not allowed_image(file_obj.filename):
        return ''
    ext      = secure_filename(file_obj.filename).rsplit('.', 1)[-1].lower()
    fname    = f"{uuid.uuid4().hex}.{ext}"
    dest_dir = os.path.join(BASE_DIR, 'static', 'uploads', subfolder)
    os.makedirs(dest_dir, exist_ok=True)
    file_obj.save(os.path.join(dest_dir, fname))
    return f"/static/uploads/{subfolder}/{fname}"


# ── Auction Winners & Failover Logic ───────────────────────────────────────────

AUCTION_PAYMENT_HOURS = 24


def get_ranked_bidders(product_id):
    return _fetchall(get_db(),
        "SELECT user_id, username, MAX(amount) as top_bid "
        "FROM bids WHERE product_id=%s "
        "GROUP BY user_id, username ORDER BY top_bid DESC",
        (product_id,))


def settle_auction(product_id):
    db = get_db()
    existing = _fetchone(db,
        "SELECT id FROM auction_winners WHERE product_id=%s AND rank=1", (product_id,))
    if existing:
        return

    ranked = get_ranked_bidders(product_id)
    if not ranked:
        return

    deadline = (datetime.now() + timedelta(hours=AUCTION_PAYMENT_HOURS)).strftime('%Y-%m-%d %H:%M:%S')

    for i, row in enumerate(ranked, start=1):
        status = 'pending_payment' if i == 1 else 'skipped'
        pay_dl = deadline if i == 1 else None
        _execute(db,
            "INSERT INTO auction_winners "
            "(product_id, winner_user_id, winner_username, bid_amount, rank, status, payment_deadline) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (product_id, row['user_id'], row['username'], row['top_bid'], i, status, pay_dl))

    db.commit()

    top = ranked[0]
    add_notification(
        top['user_id'],
        f"Congratulations! You won the auction. Please pay Rs.{top['top_bid']:.2f} within {AUCTION_PAYMENT_HOURS} hours.",
        ntype='info')


def get_current_winner(product_id):
    return _fetchone(get_db(),
        "SELECT aw.*, u.email FROM auction_winners aw "
        "JOIN users u ON aw.winner_user_id=u.id "
        "WHERE aw.product_id=%s AND aw.status IN ('pending_payment','paid') "
        "ORDER BY aw.rank ASC LIMIT 1",
        (product_id,))


def get_auction_leaderboard(product_id):
    return _fetchall(get_db(),
        "SELECT aw.rank, aw.winner_username, aw.bid_amount, aw.status, aw.payment_deadline "
        "FROM auction_winners aw WHERE aw.product_id=%s ORDER BY aw.rank ASC",
        (product_id,))


def process_auction_payment(product_id, user_id):
    db  = get_db()
    win = _fetchone(db,
        "SELECT * FROM auction_winners WHERE product_id=%s AND winner_user_id=%s AND status='pending_payment'",
        (product_id, user_id))
    if not win:
        return False, "No pending payment found for you on this auction."

    balance = get_wallet(user_id)
    if balance < win['bid_amount']:
        return False, f"Insufficient wallet balance (Rs.{balance:.2f}). Please top up first."

    deduct_wallet(user_id, win['bid_amount'],
                  f"Auction payment for product #{product_id}",
                  method='auction')

    _execute(db,
        "UPDATE auction_winners SET status='paid', paid_at=NOW() WHERE id=%s",
        (win['id'],))
    db.commit()

    add_notification(user_id,
                     f"Payment of Rs.{win['bid_amount']:.2f} confirmed. Auction item will be delivered soon.",
                     ntype='info')
    return True, "Payment successful!"


def trigger_failover(product_id):
    db  = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    expired = _fetchone(db,
        "SELECT * FROM auction_winners WHERE product_id=%s AND status='pending_payment' "
        "AND payment_deadline < %s",
        (product_id, now))
    if not expired:
        return None

    _execute(db, "UPDATE auction_winners SET status='failed' WHERE id=%s", (expired['id'],))

    next_w = _fetchone(db,
        "SELECT * FROM auction_winners WHERE product_id=%s AND status='skipped' "
        "ORDER BY rank ASC LIMIT 1",
        (product_id,))

    if not next_w:
        db.commit()
        return None

    new_deadline = (datetime.now() + timedelta(hours=AUCTION_PAYMENT_HOURS)).strftime('%Y-%m-%d %H:%M:%S')
    _execute(db,
        "UPDATE auction_winners SET status='pending_payment', payment_deadline=%s WHERE id=%s",
        (new_deadline, next_w['id']))
    db.commit()

    add_notification(
        next_w['winner_user_id'],
        f"You are now the winner of the auction! Please pay Rs.{next_w['bid_amount']:.2f} within {AUCTION_PAYMENT_HOURS} hours.",
        ntype='info')

    return next_w


def get_user_auction_win(product_id, user_id):
    return _fetchone(get_db(),
        "SELECT * FROM auction_winners WHERE product_id=%s AND winner_user_id=%s AND status='pending_payment'",
        (product_id, user_id))


# ── Admin Stats ────────────────────────────────────────────────────────────────

def get_admin_stats():
    db  = get_db()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    return {
        'total_users':      _fetchone(db, "SELECT COUNT(*) as n FROM users")['n'],
        'total_products':   _fetchone(db, "SELECT COUNT(*) as n FROM products")['n'],
        'total_orders':     _fetchone(db, "SELECT COUNT(*) as n FROM orders")['n'],
        'total_bids':       _fetchone(db, "SELECT COUNT(*) as n FROM bids")['n'],
        'active_auctions':  _fetchone(db,
            "SELECT COUNT(*) as n FROM products WHERE is_auction=1 AND approved=1 AND auction_end>%s",
            (now,))['n'],
        'total_rev':        _fetchone(db, "SELECT SUM(total_amount) as s FROM orders")['s'] or 0,
        'pending_products': _fetchone(db,
            "SELECT COUNT(*) as n FROM products WHERE approved=0 AND status='pending'")['n'],
        'total_wallet':     _fetchone(db, "SELECT SUM(wallet) as s FROM users")['s'] or 0,
    }
