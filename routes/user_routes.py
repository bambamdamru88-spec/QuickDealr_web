# -*- coding: utf-8 -*-
"""
routes/user_routes.py
Buyer, Seller, and Wallet blueprints.
All run on port 5000 (user_app).
"""

import json
import os
import re
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, session, flash, jsonify, send_file, abort)
from flask_socketio import emit, join_room, leave_room
# socketio instance imported lazily to avoid circular import
def _sio():
    from user_app import socketio
    return socketio

from utils import (login_required, buyer_only, seller_only, buyer_or_seller,
                   generate_csrf, validate_csrf, get_ip, api_ok, api_err,
                   validate_email, validate_phone, validate_pincode,
                   validate_card_number, validate_expiry, validate_cvv,
                   seconds_left, generate_invoice_pdf,
                   ROLE_BUYER, ROLE_SELLER)
import models

#  BUYER BLUEPRINT 
buyer_bp = Blueprint('buyer', __name__, template_folder='../templates')

#  SELLER BLUEPRINT 
seller_bp = Blueprint('seller', __name__, url_prefix='/seller',
                      template_folder='../templates')

#  WALLET BLUEPRINT 
wallet_bp = Blueprint('wallet', __name__, url_prefix='/wallet',
                      template_folder='../templates')


#  Context helpers 

def _ctx(uid=None, role=None):
    """Inject cc, nc, wl, now_utc into all buyer templates."""
    uid  = uid  or session.get('user_id')
    role = role or session.get('role', '')
    ctx  = {
        'nc': models.unread_count(uid) if uid else 0,
        'now_utc': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
    }
    if role == ROLE_BUYER and uid:
        ctx['cc'] = models.cart_item_count(uid)
        ctx['wl'] = models.get_wishlist_ids(uid)
    else:
        ctx['cc'] = 0
        ctx['wl'] = []
    return ctx


# 
#  BUYER ROUTES
# 

@buyer_bp.route('/')
@login_required
@buyer_only
def home():
    uid  = session['user_id']
    q    = request.args.get('q', '').strip()
    cat  = request.args.get('category', '').strip()
    sort = request.args.get('sort', 'latest')
    minp = request.args.get('min_price', '')
    maxp = request.args.get('max_price', '')

    products = models.get_products(
        approved_only=True, is_auction=0,
        category=cat or None, search=q or None, sort=sort,
        min_price=float(minp) if minp else None,
        max_price=float(maxp) if maxp else None)
    active_cats = models.get_active_categories(is_auction=0)
    recent      = models.get_products(approved_only=True, is_auction=0, sort='latest')[:8]

    # Dashboard data
    user_orders        = models.get_orders(buyer_id=uid, limit=5)
    user_bids          = models.get_user_bids(uid, limit=8)
    won_auctions       = models.get_user_won_auctions(uid, limit=4)
    active_auctions    = models.get_user_active_auctions(uid, limit=4)
    total_orders       = len(models.get_orders(buyer_id=uid) or [])
    total_wins         = len(models.get_user_won_auctions(uid, limit=999) or [])

    return render_template('buyer/home.html',
        all_products=products, recent=recent, active_cats=active_cats,
        search_q=q, active_cat=cat, sort=sort, min_p=minp, max_p=maxp,
        wallet=models.get_wallet(uid),
        user_orders=user_orders, user_bids=user_bids,
        won_auctions=won_auctions, active_auctions=active_auctions,
        total_orders=total_orders, total_wins=total_wins,
        **_ctx(uid))


@buyer_bp.route('/product/<int:pid>')
@login_required
@buyer_only
def product_detail(pid):
    uid = session['user_id']
    p   = models.get_product(pid)
    if not p:
        flash('Product not found.', 'error')
        return redirect(url_for('buyer.home'))
    models.get_db().execute("UPDATE products SET views=views+1 WHERE id=?", (pid,))
    models.get_db().commit()
    in_wl = pid in models.get_wishlist_ids(uid)
    return render_template('buyer/product_detail.html', p=p, in_wishlist=in_wl, **_ctx(uid))


#  Auctions 

@buyer_bp.route('/auctions')
@login_required
@buyer_only
def auctions_list():
    uid      = session['user_id']
    auctions = models.get_products(approved_only=True, is_auction=1, sort='latest')
    wallet   = models.get_wallet(uid)
    return render_template('buyer/auctions.html', auctions=auctions,
                           wallet=wallet, **_ctx(uid))


@buyer_bp.route('/auction/<int:pid>')
@login_required
@buyer_only
def auction_detail(pid):
    uid  = session['user_id']
    # Support viewing ended auctions (no longer filters active-only)
    p    = models.get_db().execute(
        "SELECT * FROM products WHERE id=? AND is_auction=1", (pid,)).fetchone()
    if not p or not p['approved']:
        flash('Auction not found.', 'error')
        return redirect(url_for('buyer.auctions_list'))
    secs  = seconds_left(p['auction_end'])
    ended = secs <= 0
    bids  = models.get_bids(pid, limit=20)
    leaders = models.get_leaderboard(pid, limit=5)
    chat  = list(reversed(models.get_chat_messages(pid, limit=30)))
    is_watch = bool(models.get_db().execute(
        "SELECT id FROM watchers WHERE user_id=? AND product_id=?", (uid, pid)).fetchone())
    atoken = models.issue_auction_token(uid, pid)
    wallet = models.get_wallet(uid)
    min_bid = float(p['current_bid'] or p['start_price']) + 1.0
    # Post-auction settlement
    if ended:
        models.settle_auction(pid)
    winner           = models.get_current_winner(pid) if ended else None
    my_win           = models.get_user_auction_win(pid, uid) if ended else None
    full_leaderboard = models.get_auction_leaderboard(pid) if ended else []
    return render_template('buyer/auction.html',
        p=p, bids=bids, leaders=leaders, chat=chat,
        is_watching=is_watch, secs=secs, ended=ended,
        atoken=atoken, dwell=3, wallet=wallet, min_bid=min_bid,
        winner=winner, my_win=my_win, full_leaderboard=full_leaderboard, **_ctx(uid))


@buyer_bp.route('/auction/<int:pid>/pay', methods=['POST'])
@login_required
@buyer_only
def auction_pay(pid):
    """Winner pays their auction amount from wallet."""
    uid = session['user_id']
    ok, msg = models.process_auction_payment(pid, uid)
    flash(msg, 'success' if ok else 'error')
    return redirect(url_for('buyer.auction_detail', pid=pid))


@buyer_bp.route('/bid/<int:pid>', methods=['POST'])
@login_required
@buyer_only
def place_bid(pid):
    uid = session['user_id']
    ip  = get_ip()

    p = models.get_db().execute(
        "SELECT * FROM products WHERE id=? AND is_auction=1 AND approved=1", (pid,)).fetchone()
    if not p:
        flash('Invalid auction.', 'error')
        return redirect(url_for('buyer.auctions_list'))
    if seconds_left(p['auction_end']) <= 0:
        flash('This auction has ended.', 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    ok, reason = models.validate_auction_token(uid, pid, request.form.get('atoken', ''))
    if not ok:
        models.log_security(uid, ip, 'bid_token_fail', reason)
        flash(reason, 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    allowed, reason = models.check_bid_rate(uid, pid, ip)
    if not allowed:
        flash(reason, 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    try:
        amount = float(request.form.get('amount', 0))
    except (TypeError, ValueError):
        flash('Invalid amount.', 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    min_bid = float(p['current_bid'] or p['start_price']) + 1.0
    if amount < min_bid:
        flash(f'Bid must be at least ₹{min_bid:.2f}.', 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    # No wallet balance check - bidding is free, payment required only if you win.

    if models.get_db().execute(
        "SELECT id FROM bids WHERE product_id=? AND user_id=? AND amount=?",
            (pid, uid, amount)).fetchone():
        flash('You already placed a bid for this amount.', 'error')
        return redirect(url_for('buyer.auction_detail', pid=pid))

    prev = models.place_bid(pid, uid, session['username'], amount, ip)
    models.log_bid_rate(uid, pid, ip)

    # Notify outbid user
    if prev and prev['highest_bidder'] and prev['highest_bidder'] != session['username']:
        row = models.get_db().execute(
            "SELECT id FROM users WHERE username=?", (prev['highest_bidder'],)).fetchone()
        if row:
            models.add_notification(
                row['id'],
                f"You were outbid on '{p['name']}'. New bid: ₹{amount:.2f}", ntype='outbid')

    # Broadcast real-time update to all auction watchers
    try:
        updated = models.get_db().execute(
            "SELECT current_bid, bid_count, highest_bidder, auction_end, watcher_count "
            "FROM products WHERE id=?", (pid,)).fetchone()
        if updated:
            _sio().emit('bid_update', {
                'product_id':     pid,
                'current_bid':    updated['current_bid'],
                'bid_count':      updated['bid_count'],
                'highest_bidder': updated['highest_bidder'],
                'seconds_left':   seconds_left(updated['auction_end']),
                'watcher_count':  updated['watcher_count'],
            }, room=f'auction_{pid}', namespace='/')
    except Exception:
        pass  # non-fatal — page will still redirect correctly

    flash(f'Bid of ₹{amount:.2f} placed successfully!', 'success')
    return redirect(url_for('buyer.auction_detail', pid=pid))


@buyer_bp.route('/api/interact/<int:pid>', methods=['POST'])
@login_required
@buyer_only
def record_interaction(pid):
    models.mark_interaction(session['user_id'], pid)
    return api_ok()


@buyer_bp.route('/watch/<int:pid>', methods=['POST'])
@login_required
@buyer_only
def watch_auction(pid):
    watching = models.toggle_watcher(session['user_id'], pid)
    return jsonify({'ok': True, 'watching': watching})


#  Cart 

@buyer_bp.route('/cart')
@login_required
@buyer_only
def cart():
    uid   = session['user_id']
    items = models.get_cart(uid)
    total = sum(i['price'] * i['quantity'] for i in items)
    return render_template('buyer/cart.html', items=items, total=total, **_ctx(uid))


@buyer_bp.route('/cart/add/<int:pid>', methods=['POST'])
@login_required
@buyer_only
def add_cart(pid):
    models.add_to_cart(session['user_id'], pid)
    flash('Added to cart!', 'success')
    return redirect(request.referrer or url_for('buyer.home'))




@buyer_bp.route('/cart/update/<int:cid>', methods=['POST'])
@login_required
@buyer_only
def update_cart_qty(cid):
    uid = session['user_id']
    qty = int(request.form.get('qty', 1))
    if qty < 1:
        qty = 1
    if qty > 20:
        qty = 20
    db = models.get_db()
    db.execute("UPDATE cart SET quantity=? WHERE id=? AND buyer_id=?", (qty, cid, uid))
    db.commit()
    return redirect(url_for('buyer.cart'))

@buyer_bp.route('/cart/remove/<int:cid>', methods=['POST'])
@login_required
@buyer_only
def remove_cart(cid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('buyer.cart'))
    models.remove_from_cart(cid, session['user_id'])
    return redirect(url_for('buyer.cart'))


#  Checkout 

@buyer_bp.route('/checkout', methods=['GET', 'POST'])
@login_required
@buyer_only
def checkout():
    uid  = session['user_id']
    mode = request.args.get('mode', 'cart')
    pid  = request.args.get('pid')
    qty  = int(request.args.get('qty', 1))

    if mode == 'buy_now' and pid:
        p = models.get_product(int(pid))
        if not p:
            flash('Product not found.', 'error')
            return redirect(url_for('buyer.home'))
        items = [{'pid': p['id'], 'name': p['name'], 'price': p['price'],
                  'image': p['image'], 'quantity': qty}]
    else:
        raw = models.get_cart(uid)
        if not raw:
            flash('Your cart is empty.', 'error')
            return redirect(url_for('buyer.cart'))
        items = [dict(i) for i in raw]

    subtotal     = sum(i['price'] * i['quantity'] for i in items)
    delivery_fee = 49.0 if subtotal < 500 else 0.0
    addresses    = models.get_addresses(uid)
    qr           = models.get_qr_settings()
    wallet_bal   = models.get_wallet(uid)
    promo_code   = ''
    promo_discount = 0.0
    promo_message  = ''

    if request.method == 'POST':
        #  CSRF check 
        if not validate_csrf(request.form.get('_csrf')):
            flash('Security error. Please try again.', 'error')
            return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))

        payment_method = request.form.get('payment_method', 'cod')
        if payment_method == 'upi': payment_method = 'qr'  # upi-compat
        address_id     = request.form.get('address_id', '').strip()
        transaction_id = request.form.get('transaction_id', '').strip()
        promo_code     = request.form.get('promo_code', '').strip().upper()

        #  Promo code 
        if promo_code:
            disc, promo_row, err = models.apply_promo(promo_code, subtotal)
            if err:
                promo_discount = 0.0
                promo_message  = err
            else:
                promo_discount = disc

        total = round(subtotal + delivery_fee - promo_discount, 2)

        #  Address validation 
        if not address_id:
            flash('Please select a delivery address.', 'error')
            return render_template('buyer/checkout.html',
                items=items, subtotal=subtotal, delivery_fee=delivery_fee,
                promo_discount=promo_discount, promo_message=promo_message,
                promo_code=promo_code, total=total, addresses=addresses,
                mode=mode, pid=pid, qty=qty, qr=qr, wallet_bal=wallet_bal, **_ctx(uid))

        addr = models.get_address(int(address_id), uid)
        if not addr:
            flash('Invalid address.', 'error')
            return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))

        #  Payment validation 
        if payment_method == 'card':
            if not validate_card_number(request.form.get('card_number', '')):
                flash('Enter a valid 16-digit card number.', 'error')
                return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))
            if not request.form.get('card_name', '').strip():
                flash('Enter cardholder name.', 'error')
                return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))
            if not validate_expiry(request.form.get('expiry', '')):
                flash('Enter valid expiry MM/YY.', 'error')
                return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))
            if not validate_cvv(request.form.get('cvv', '')):
                flash('Enter valid CVV.', 'error')
                return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))
        elif payment_method in ('upi', 'qr'):
            pass  # Auto-confirmed: no TXN ID required
        elif payment_method == 'wallet':
            if wallet_bal < total:
                flash(f'Insufficient wallet balance (₹{wallet_bal:.2f}). Need ₹{total:.2f}.', 'error')
                return redirect(url_for('buyer.checkout', mode=mode, pid=pid, qty=qty))

        #  Build order 
        addr_snap      = json.dumps({
            'full_name': addr['full_name'], 'phone': addr['phone'],
            'full_address': addr['full_address'], 'landmark': addr['landmark'],
            'city': addr['city'], 'state': addr['state'], 'pincode': addr['pincode'],
        })
        payment_status = 'paid' if payment_method in ('card', 'upi', 'qr', 'wallet') else 'pending'
        order_status_val = 'confirmed' if payment_method in ('card', 'upi', 'qr', 'wallet') else 'placed'

        if payment_method == 'wallet':
            models.deduct_wallet(uid, total, 'Order payment', method='wallet')

        if promo_code and promo_discount > 0:
            models.use_promo_code(promo_code)

        order_ids = []
        for item in items:
            item_total    = item['price'] * item['quantity']
            item_disc     = round(item_total * (promo_discount / subtotal), 2) if subtotal > 0 else 0
            item_delivery = round(delivery_fee / len(items), 2)
            item_grand    = round(item_total + item_delivery - item_disc, 2)
            oid = models.create_order(
                uid, session['username'],
                item['pid'], item['name'], item['image'] if 'image' in item.keys() else '',
                item_total, item['quantity'],
                item_delivery, item_disc, item_grand,
                payment_method, payment_status, transaction_id,
                int(address_id), addr_snap)
            order_ids.append(oid)

        if mode != 'buy_now':
            models.clear_cart(uid)

        if payment_method in ('upi', 'qr'):
            models.add_notification(uid, "Payment successful. Order confirmed.", ntype='order')
            flash('Payment successful. Order confirmed.', 'success')
        else:
            models.add_notification(uid, f"Order placed successfully! Payment: {payment_method.upper()}", ntype='order')
        # Store order_id in session so success page can show the popup
        session['last_order_id'] = order_ids[0]
        return redirect(url_for('buyer.order_success', oid=order_ids[0]))

    # GET
    total = round(subtotal + delivery_fee, 2)
    return render_template('buyer/checkout.html',
        items=items, subtotal=subtotal, delivery_fee=delivery_fee,
        promo_discount=0.0, promo_message='', promo_code='',
        total=total, addresses=addresses,
        mode=mode, pid=pid, qty=qty, qr=qr, wallet_bal=wallet_bal,
        **_ctx(uid))


@buyer_bp.route('/checkout/apply_promo', methods=['POST'])
@login_required
@buyer_only
def apply_promo_ajax():
    """AJAX endpoint: validate promo code and return discount info."""
    if not validate_csrf(request.form.get('_csrf')):
        return api_err('Security error', 403)
    code     = request.form.get('code', '').strip().upper()
    subtotal = float(request.form.get('subtotal', 0))
    disc, promo, err = models.apply_promo(code, subtotal)
    if err:
        return api_err(err)
    return api_ok({
        'discount':      disc,
        'code':          promo['code'],
        'discount_type': promo['discount_type'],
        'value':         promo['value'],
        'message':       f"Promo applied: -{('%.0f%%' % promo['value']) if promo['discount_type']=='percentage' else ('₹%.0f' % disc)} off!",
    })


@buyer_bp.route('/buy/<int:pid>')
@login_required
@buyer_only
def buy_now(pid):
    return redirect(url_for('buyer.checkout', mode='buy_now', pid=pid, qty=1))


#  Orders 

@buyer_bp.route('/order/success/<int:oid>')
@login_required
@buyer_only
def order_success(oid):
    uid   = session['user_id']
    order = models.get_order(oid, buyer_id=uid)
    if not order:
        flash('Order not found.', 'error')
        return redirect(url_for('buyer.orders'))
    addr = {}
    try:
        if order['address_snapshot']:
            addr = json.loads(order['address_snapshot'])
    except Exception:
        pass
    return render_template('buyer/order_success.html', order=order, addr=addr, **_ctx(uid))


@buyer_bp.route('/orders')
@login_required
@buyer_only
def orders():
    uid    = session['user_id']
    orders = models.get_orders(buyer_id=uid)
    return render_template('buyer/orders.html', orders=orders, **_ctx(uid))


@buyer_bp.route('/order/cancel/<int:oid>', methods=['POST'])
@login_required
@buyer_only
def cancel_order(oid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('buyer.orders'))
    ok, order = models.cancel_order(oid, session['user_id'])
    if not ok:
        flash('Order cannot be cancelled.', 'error')
    else:
        models.add_notification(session['user_id'], f"Order #{oid} cancelled.")
        flash(f'Order #{oid} cancelled.', 'success')
    return redirect(url_for('buyer.orders'))


@buyer_bp.route('/order/invoice/<int:oid>')
@login_required
@buyer_only
def download_invoice(oid):
    uid   = session['user_id']
    order = models.get_order(oid, buyer_id=uid)
    if not order:
        abort(404)
    addr = {}
    try:
        if order['address_snapshot']:
            addr = json.loads(order['address_snapshot'])
    except Exception:
        pass
    buf = generate_invoice_pdf(order, addr)
    if not buf:
        flash('PDF generation unavailable. Install reportlab.', 'error')
        return redirect(url_for('buyer.orders'))
    return send_file(buf, mimetype='application/pdf',
                     download_name=f'QuickDealr_Invoice_QD{oid:06d}.pdf',
                     as_attachment=True)


#  Addresses 

@buyer_bp.route('/addresses')
@login_required
@buyer_only
def addresses():
    uid  = session['user_id']
    addr = models.get_addresses(uid)
    return render_template('buyer/addresses.html', addresses=addr, **_ctx(uid))


@buyer_bp.route('/addresses/add', methods=['POST'])
@login_required
@buyer_only
def add_address():
    uid = session['user_id']
    fn  = request.form.get('full_name', '').strip()
    ph  = request.form.get('phone', '').strip()
    ci  = request.form.get('city', '').strip()
    st  = request.form.get('state', '').strip()
    pin = request.form.get('pincode', '').strip()
    lm  = request.form.get('landmark', '').strip()
    fa  = request.form.get('full_address', '').strip()

    if not all([fn, ph, ci, st, pin, fa]):
        flash('All required address fields must be filled.', 'error')
        return redirect(request.referrer or url_for('buyer.addresses'))
    if not validate_phone(ph):
        flash('Enter a valid 10-digit phone number.', 'error')
        return redirect(request.referrer or url_for('buyer.addresses'))
    if not validate_pincode(pin):
        flash('Enter a valid 6-digit pincode.', 'error')
        return redirect(request.referrer or url_for('buyer.addresses'))

    models.create_address(uid, fn, ph, ci, st, pin, lm, fa)
    flash('Address saved!', 'success')
    return redirect(request.referrer or url_for('buyer.addresses'))


@buyer_bp.route('/addresses/delete/<int:aid>', methods=['POST'])
@login_required
@buyer_only
def delete_address(aid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('buyer.addresses'))
    models.delete_address(aid, session['user_id'])
    flash('Address deleted.', 'success')
    return redirect(url_for('buyer.addresses'))


@buyer_bp.route('/addresses/default/<int:aid>', methods=['POST'])
@login_required
@buyer_only
def set_default_address(aid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('buyer.addresses'))
    models.set_default_address(aid, session['user_id'])
    flash('Default address updated.', 'success')
    return redirect(url_for('buyer.addresses'))


#  Wishlist 

@buyer_bp.route('/wishlist')
@login_required
@buyer_only
def wishlist():
    uid   = session['user_id']
    items = models.get_wishlist_products(uid)
    return render_template('buyer/wishlist.html', items=items, **_ctx(uid))


@buyer_bp.route('/wishlist/toggle/<int:pid>', methods=['POST'])
@login_required
@buyer_only
def toggle_wishlist(pid):
    liked = models.toggle_wishlist(session['user_id'], pid)
    return jsonify({'ok': True, 'liked': liked})


#  Messages 

@buyer_bp.route('/messages')
@login_required
@buyer_only
def messages():
    uid   = session['user_id']
    convs = models.get_conversations(uid)
    return render_template('buyer/messages.html', conversations=convs, **_ctx(uid))


@buyer_bp.route('/messages/<int:auction_id>/<int:other_id>', methods=['GET', 'POST'])
@login_required
@buyer_only
def message_thread(auction_id, other_id):
    uid = session['user_id']
    db  = models.get_db()
    auction = db.execute("SELECT * FROM products WHERE id=?", (auction_id,)).fetchone()
    other   = db.execute("SELECT id, username FROM users WHERE id=?", (other_id,)).fetchone()
    if not auction or not other:
        flash('Conversation not found.', 'error')
        return redirect(url_for('buyer.messages'))
    if request.method == 'POST':
        msg = request.form.get('message', '').strip()[:500]
        if msg:
            models.send_message(auction_id, uid, other_id, msg)
        return redirect(url_for('buyer.message_thread', auction_id=auction_id, other_id=other_id))
    msgs = models.get_message_thread(auction_id, uid, other_id)
    models.mark_messages_read(auction_id, uid)
    return render_template('buyer/message_thread.html',
                           msgs=msgs, auction=auction, other=other, **_ctx(uid))


#  Notifications 

@buyer_bp.route('/notifications')
@login_required
@buyer_or_seller
def notifications():
    uid    = session['user_id']
    notifs = models.get_notifications(uid, limit=30)
    models.mark_notifications_read(uid)
    role = session.get('role', '')
    tmpl = 'seller/notifications.html' if role == ROLE_SELLER else 'buyer/notifications.html'
    return render_template(tmpl, notifs=notifs, **_ctx(uid))


#  Search API 

@buyer_bp.route('/api/search')
@login_required
@buyer_only
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return api_ok([])
    rows = models.get_db().execute(
        "SELECT id,name,price,category,image,is_auction FROM products "
        "WHERE approved=1 AND name LIKE ? LIMIT 6", (f'%{q}%',)).fetchall()
    return api_ok([dict(r) for r in rows])


@buyer_bp.route('/api/auction_status/<int:pid>')
def auction_status_api(pid):
    p = models.get_db().execute(
        "SELECT current_bid,bid_count,highest_bidder,auction_end,watcher_count "
        "FROM products WHERE id=?", (pid,)).fetchone()
    if not p:
        return api_err('Not found', 404)
    return api_ok({
        'current_bid':    p['current_bid'],
        'bid_count':      p['bid_count'],
        'highest_bidder': p['highest_bidder'],
        'seconds_left':   seconds_left(p['auction_end']),
        'watcher_count':  p['watcher_count'],
    })


@buyer_bp.route('/api/notifications')
@login_required
def api_notifs():
    rows = models.get_notifications(session['user_id'], unread_only=True, limit=5)
    return api_ok([dict(r) for r in rows])


@buyer_bp.route('/api/live_auctions')
@login_required
@buyer_only
def api_live_auctions():
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    count = models.get_db().execute(
        "SELECT COUNT(*) FROM products WHERE is_auction=1 AND approved=1 AND auction_end > ?",
        (now,)).fetchone()[0]
    return api_ok(count)


# 
#  WALLET ROUTES  (prefix: /wallet)
# 

@wallet_bp.route('/')
@login_required
@buyer_or_seller
def wallet_home():
    uid    = session['user_id']
    bal    = models.get_wallet(uid)
    txns   = models.get_wallet_transactions(uid, limit=30)
    qr     = models.get_qr_settings()
    return render_template('buyer/wallet.html', wallet=bal, txns=txns, qr=qr, **_ctx(uid))


@wallet_bp.route('/topup', methods=['GET', 'POST'])
@login_required
@buyer_or_seller
def topup():
    uid = session['user_id']
    qr  = models.get_qr_settings()
    bal = models.get_wallet(uid)
    my_requests = []  # Approval system removed — all top-ups are instant

    if request.method == 'POST':
        if not validate_csrf(request.form.get('_csrf')):
            flash('Security error.', 'error')
            return redirect(url_for('wallet.topup'))

        try:
            amount = float(request.form.get('amount', 0))
        except (ValueError, TypeError):
            flash('Invalid amount.', 'error')
            return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                   my_requests=my_requests, **_ctx(uid))

        if amount < 10:
            flash('Minimum top-up amount is ₹10.', 'error')
            return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                   my_requests=my_requests, **_ctx(uid))
        if amount > 100000:
            flash('Maximum top-up is ₹1,00,000.', 'error')
            return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                   my_requests=my_requests, **_ctx(uid))

        payment_method = request.form.get('payment_method', 'card')
        transaction_id = request.form.get('transaction_id', '').strip()
        card_last4 = ''

        if payment_method == 'card':
            if not validate_card_number(request.form.get('card_number', '')):
                flash('Enter a valid 16-digit card number.', 'error')
                return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                       my_requests=my_requests, **_ctx(uid))
            if not request.form.get('card_name', '').strip():
                flash('Enter cardholder name.', 'error')
                return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                       my_requests=my_requests, **_ctx(uid))
            if not validate_expiry(request.form.get('expiry', '')):
                flash('Enter valid expiry MM/YY.', 'error')
                return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                       my_requests=my_requests, **_ctx(uid))
            if not validate_cvv(request.form.get('cvv', '')):
                flash('Enter valid CVV.', 'error')
                return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                                       my_requests=my_requests, **_ctx(uid))
            raw_num = request.form.get('card_number', '').replace(' ', '')
            card_last4 = raw_num[-4:] if len(raw_num) >= 4 else ''

        # (Transaction ID verification removed — all top-ups are auto-approved)

        # AUTO-APPROVE: Credit wallet immediately, no admin approval needed
        models.credit_wallet(uid, amount,
                             f'Wallet top-up via {payment_method.upper()}', payment_method)
        models.add_notification(uid,
            f"Wallet credited with \u20b9{amount:.2f}. Transaction successful!",
            ntype='info')
        flash(f'Wallet topped up with \u20b9{amount:.2f} successfully!', 'success')
        return redirect(url_for('wallet.wallet_home'))

    return render_template('buyer/wallet_topup.html', wallet=bal, qr=qr,
                           my_requests=my_requests, **_ctx(uid))


# 
#  SELLER ROUTES  (prefix: /seller)
# 

@seller_bp.route('/')
@login_required
@seller_only
def dashboard():
    uid      = session['user_id']
    products = models.get_products(approved_only=False, seller_id=uid)
    nc       = models.unread_count(uid)
    # Earnings: sum of all delivered orders for this seller's products
    db = models.get_db()
    seller_orders = db.execute(
        """SELECT o.* FROM orders o
           JOIN products p ON o.product_id = p.id
           WHERE p.seller_id = ? ORDER BY o.created_at DESC""",
        (uid,)
    ).fetchall()
    total_earned  = sum(o['total_amount'] or o['amount'] for o in seller_orders)
    return render_template('seller/dashboard.html',
        products=products,
        pending=[p for p in products if not p['approved']],
        live=[p for p in products if p['approved']],
        total_views=sum(p['views'] for p in products),
        seller_orders=seller_orders,
        total_earned=total_earned,
        nc=nc)


@seller_bp.route('/add', methods=['GET', 'POST'])
@login_required
@seller_only
def add_product():
    uid = session['user_id']
    db  = models.get_db()
    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        price_str  = request.form.get('price', '')
        cat        = request.form.get('category', '').strip()
        desc       = request.form.get('description', '').strip()
        stock      = int(request.form.get('stock', 1))
        is_auction = 1 if request.form.get('is_auction') else 0
        if not name or not price_str or not cat:
            flash('Name, price, and category are required.', 'error')
        else:
            try:
                price = round(float(price_str), 2)
            except ValueError:
                flash('Invalid price.', 'error')
                return render_template('seller/add_product.html',
                                       categories=models.get_categories(), nc=models.unread_count(uid))
            # Handle image: file upload takes priority over URL
            img = ''
            file = request.files.get('image_file')
            if file and file.filename:
                img = models.save_uploaded_image(file, 'products')
                if not img:
                    flash('Invalid image file type. Use PNG/JPG/GIF/WEBP.', 'error')
                    return render_template('seller/add_product.html',
                                           categories=models.get_categories(), nc=models.unread_count(uid))
            else:
                img = request.form.get('image_url', '').strip()
            auction_time_str = request.form.get('auction_duration', '').strip()
            auction_hours = None
            if is_auction:
                if auction_time_str:
                    try:
                        parts = auction_time_str.split(':')
                        if len(parts) == 3:
                            dd, hh, mm = int(parts[0]), int(parts[1]), int(parts[2])
                            total_mins = dd * 24 * 60 + hh * 60 + mm
                            auction_hours = max(1, total_mins / 60) if total_mins > 0 else None
                        elif len(parts) == 2:
                            hh, mm = int(parts[0]), int(parts[1])
                            auction_hours = max(1, hh + mm / 60)
                        else:
                            auction_hours = max(1, int(auction_time_str))
                    except Exception:
                        auction_hours = None
                if not auction_hours:
                    flash('Please select a valid auction duration for your auction listing.', 'error')
                    return render_template('seller/add_product.html',
                                           categories=models.get_categories(), nc=models.unread_count(uid))
            models.create_product(name, desc, price, cat, img,
                                  uid, session['username'], stock,
                                  is_auction, auction_hours, price if is_auction else 0)
            flash('Product submitted for approval!', 'success')
            return redirect(url_for('seller.dashboard'))
    return render_template('seller/add_product.html',
                           categories=models.get_categories(), nc=models.unread_count(uid))


@seller_bp.route('/edit/<int:pid>', methods=['GET', 'POST'])
@login_required
@seller_only
def edit_product(pid):
    uid = session['user_id']
    p   = models.get_db().execute(
        "SELECT * FROM products WHERE id=? AND seller_id=?", (pid, uid)).fetchone()
    if not p:
        flash('Product not found.', 'error')
        return redirect(url_for('seller.dashboard'))
    if request.method == 'POST':
        name  = request.form.get('name', '').strip()
        desc  = request.form.get('description', '').strip()
        price = float(request.form.get('price', p['price']))
        img   = request.form.get('image', p['image']).strip()
        stock = int(request.form.get('stock', p['stock']))
        db    = models.get_db()
        db.execute("UPDATE products SET name=?,description=?,price=?,image=?,stock=?,approved=0 WHERE id=?",
                   (name, desc, price, img, stock, pid))
        db.commit()
        flash('Product updated and re-submitted for approval.', 'success')
        return redirect(url_for('seller.dashboard'))
    return render_template('seller/edit_product.html', p=p,
                           categories=models.get_categories(), nc=models.unread_count(uid))


@seller_bp.route('/delete/<int:pid>', methods=['POST'])
@login_required
@seller_only
def delete_product(pid):
    if not validate_csrf(request.form.get('_csrf')):
        flash('Security error.', 'error')
        return redirect(url_for('seller.dashboard'))
    db = models.get_db()
    db.execute("DELETE FROM products WHERE id=? AND seller_id=?", (pid, session['user_id']))
    db.commit()
    flash('Product deleted.', 'success')
    return redirect(url_for('seller.dashboard'))




@seller_bp.route('/withdraw', methods=['GET', 'POST'])
@login_required
@seller_only
def withdraw():
    uid = session['user_id']
    nc  = models.unread_count(uid)
    bal = models.get_wallet(uid)
    db  = models.get_db()

    if request.method == 'POST':
        if not validate_csrf(request.form.get('_csrf')):
            flash('Security error.', 'error')
            return redirect(url_for('seller.withdraw'))
        method = request.form.get('method', 'bank')
        amount_str = request.form.get('amount', '')
        try:
            amount = round(float(amount_str), 2)
        except (ValueError, TypeError):
            flash('Invalid amount.', 'error')
            return redirect(url_for('seller.withdraw'))
        if amount < 100:
            flash('Minimum withdrawal is ₹100.', 'error')
            return redirect(url_for('seller.withdraw'))
        if amount > bal:
            flash('Insufficient wallet balance.', 'error')
            return redirect(url_for('seller.withdraw'))

        details = {}
        if method == 'bank':
            details['account'] = request.form.get('account_number', '').strip()
            details['ifsc']    = request.form.get('ifsc_code', '').strip().upper()
            details['name']    = request.form.get('account_name', '').strip()
            if not all(details.values()):
                flash('All bank details are required.', 'error')
                return redirect(url_for('seller.withdraw'))
        else:
            details['upi_id'] = request.form.get('upi_id', '').strip()
            if not details['upi_id']:
                flash('UPI ID is required.', 'error')
                return redirect(url_for('seller.withdraw'))

        import json
        models.deduct_wallet(uid, amount, f'Withdrawal via {method.upper()} - {json.dumps(details)}', 'withdrawal')
        models.add_notification(uid, f'Withdrawal of ₹{amount:,.2f} requested successfully.', ntype='info')
        flash(f'Withdrawal of ₹{amount:,.2f} requested. It will be processed within 2-3 business days.', 'success')
        return redirect(url_for('seller.withdraw'))

    return render_template('seller/withdraw.html', bal=bal, nc=nc)

@seller_bp.route('/upload', methods=['GET', 'POST'])
@login_required
@seller_only
def upload_file():
    """Secure file upload for sellers — any extension, sanitized."""
    import uuid as _uuid
    from pathlib import Path as _Path
    from werkzeug.utils import secure_filename as _sf

    UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads', 'files')
    BLOCKED_EXT = {'.exe','.php','.py','.sh','.bat','.cmd','.vbs','.ps1','.cgi','.pl','.rb','.asp','.aspx'}
    MAX_MB = 10

    uploaded = None
    error = None

    if request.method == 'POST':
        if not validate_csrf(request.form.get('_csrf')):
            flash('Security error.', 'error')
            return redirect(url_for('seller.upload_file'))
        f = request.files.get('file')
        if not f or not f.filename:
            error = 'Please choose a file to upload.'
        else:
            original = _sf(f.filename)
            ext = _Path(original).suffix.lower()
            if ext in BLOCKED_EXT:
                error = f'File type "{ext}" is not permitted for security reasons.'
            else:
                f.seek(0, 2); size = f.tell(); f.seek(0)
                if size > MAX_MB * 1024 * 1024:
                    error = f'File exceeds the {MAX_MB} MB size limit.'
                else:
                    unique = f'{_uuid.uuid4().hex}{ext}'
                    os.makedirs(UPLOAD_DIR, exist_ok=True)
                    f.save(os.path.join(UPLOAD_DIR, unique))
                    rel_path = f'/static/uploads/files/{unique}'
                    models.store_uploaded_file(session['user_id'], original, rel_path, size)
                    uploaded = {'name': original, 'path': rel_path, 'size': size}
                    flash(f'File "{original}" uploaded successfully!', 'success')

    # Get this user's recent uploads
    db = models.get_db()
    try:
        recent = db.execute(
            "SELECT * FROM uploaded_files WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
            (session['user_id'],)
        ).fetchall()
    except Exception:
        recent = []

    return render_template('seller/upload.html',
                           uploaded=uploaded, error=error, recent=recent,
                           nc=models.unread_count(session['user_id']))


@seller_bp.route('/orders')
@login_required
@seller_only
def orders():
    uid    = session['user_id']
    orders = models.get_seller_orders(uid)
    return render_template('seller/orders.html', orders=orders, nc=models.unread_count(uid))


# 
#  STATIC PAGES
# 

@buyer_bp.route('/about')
def about():
    return render_template('pages/about.html', **_ctx())


@buyer_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name', '').strip()
        email   = request.form.get('email', '').strip()
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not name or not email or not message:
            flash('Name, email, and message are required.', 'error')
            return render_template('pages/contact.html', **_ctx())
        if not validate_email(email):
            flash('Please enter a valid email address.', 'error')
            return render_template('pages/contact.html', **_ctx())
        models.create_contact_message(name, email, subject, message)
        flash('Message sent! We will get back to you soon.', 'success')
        return redirect(url_for('buyer.contact'))
    return render_template('pages/contact.html', **_ctx())


@buyer_bp.route('/faq')
def faq():
    return render_template('pages/faq.html', **_ctx())


@buyer_bp.route('/how-auctions-work')
def how_auctions():
    return render_template('pages/how_auctions.html', **_ctx())


@buyer_bp.route('/payment-guide')
def payment_guide():
    return render_template('pages/payment_guide.html', **_ctx())


@buyer_bp.route('/seller-guide')
def seller_guide():
    return render_template('pages/seller_guide.html', **_ctx())


@buyer_bp.route('/careers')
def careers():
    return render_template('pages/careers.html', **_ctx())


@buyer_bp.route('/blog')
def blog():
    return render_template('pages/blog.html', **_ctx())


@buyer_bp.route('/privacy-policy')
def privacy_policy():
    return render_template('pages/privacy_policy.html', **_ctx())


@buyer_bp.route('/terms-of-service')
def terms_of_service():
    return render_template('pages/terms_of_service.html', **_ctx())


@buyer_bp.route('/refund-policy')
def refund_policy():
    return render_template('pages/refund_policy.html', **_ctx())


@buyer_bp.route('/cookie-policy')
def cookie_policy():
    return render_template('pages/cookie_policy.html', **_ctx())


# ── Return Product ────────────────────────────────────────────────────────

RETURN_WINDOW_DAYS = 7

@buyer_bp.route('/return/<int:order_id>', methods=['GET', 'POST'])
@login_required
@buyer_only
def return_product(order_id):
    uid = session['user_id']
    order = models.get_order(order_id)

    # Validate order existence and ownership
    if not order or order['buyer_id'] != uid:
        flash('Order not found.', 'error')
        return redirect(url_for('buyer.orders'))

    # Validate order is delivered
    if order['status'] != 'Delivered':
        flash('Only delivered orders can be returned.', 'error')
        return redirect(url_for('buyer.orders'))

    # Calculate return eligibility
    delivered_at = order['updated_at'] or order['created_at']
    try:
        delivered_date = datetime.strptime(str(delivered_at)[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        delivered_date = datetime.utcnow()

    days_since = (datetime.utcnow() - delivered_date).days
    is_eligible = days_since <= RETURN_WINDOW_DAYS
    days_left   = max(0, RETURN_WINDOW_DAYS - days_since)

    # Check if return already exists
    existing_return = models.get_return_for_order(order_id)

    if request.method == 'POST':
        if not is_eligible:
            flash('Return window has expired.', 'error')
            return redirect(url_for('buyer.orders'))

        if existing_return:
            flash('A return request already exists for this order.', 'error')
            return redirect(url_for('buyer.orders'))

        reason      = request.form.get('reason', '').strip()
        description = request.form.get('description', '').strip()

        if not reason:
            flash('Please select a reason for return.', 'error')
            return render_template('buyer/return_product.html',
                order=order, is_eligible=is_eligible, days_left=days_left,
                existing_return=existing_return, delivered_date=delivered_date, **_ctx(uid))

        # Handle optional image upload
        image_path = ''
        upload_file = request.files.get('return_image')
        if upload_file and upload_file.filename:
            import uuid, werkzeug.utils as wu
            ext = os.path.splitext(wu.secure_filename(upload_file.filename))[1].lower()
            if ext in ('.jpg', '.jpeg', '.png', '.webp', '.gif'):
                fname = f"return_{order_id}_{uuid.uuid4().hex[:8]}{ext}"
                save_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                        'static', 'uploads', 'returns')
                os.makedirs(save_dir, exist_ok=True)
                upload_file.save(os.path.join(save_dir, fname))
                image_path = f'/static/uploads/returns/{fname}'

        models.create_return(order_id, uid, reason, description, image_path)
        models.add_notification(uid, f'Return request for order #QD{order_id:06d} submitted successfully.', ntype='order')
        flash('Return request submitted successfully!', 'success')
        return redirect(url_for('buyer.return_product', order_id=order_id))

    return render_template('buyer/return_product.html',
        order=order, is_eligible=is_eligible, days_left=days_left,
        existing_return=existing_return, delivered_date=delivered_date, **_ctx(uid))
