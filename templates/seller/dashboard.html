{% extends "base.html" %}
{% block title %}Seller Dashboard — QuickDealr{% endblock %}
{% block extra_css %}
<style>
  :root{--accent:#4f6ef7;--mono:'DM Mono',monospace}
  .seller-page{max-width:1100px;margin:0 auto;padding:28px 16px}

  /* Header */
  .seller-header{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:24px;flex-wrap:wrap}
  .seller-header h1{font-size:1.4rem;font-weight:800;letter-spacing:-.03em}
  .seller-header p{font-size:.82rem;color:var(--muted);margin-top:3px}

  /* Stats grid */
  .seller-stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;margin-bottom:24px}
  .ss-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px 16px}
  .ss-num{font-size:1.55rem;font-weight:800;letter-spacing:-.04em;color:var(--text)}
  .ss-lbl{font-size:.67rem;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:3px}

  /* Earnings breakdown */
  .earnings-card{background:linear-gradient(135deg,rgba(79,110,247,.12),rgba(109,40,217,.08));border:1px solid rgba(79,110,247,.25);border-radius:14px;padding:20px 24px;margin-bottom:24px;display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
  @media(max-width:600px){.earnings-card{grid-template-columns:1fr}}
  .ec-item .ec-lbl{font-size:.68rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-bottom:5px}
  .ec-item .ec-val{font-size:1.45rem;font-weight:800;letter-spacing:-.03em}
  .ec-item .ec-sub{font-size:.72rem;color:var(--muted);margin-top:2px}

  /* Pending notice */
  .info-bar{background:rgba(245,158,11,.07);border:1px solid rgba(245,158,11,.2);border-radius:8px;padding:10px 14px;font-size:.8rem;color:#f59e0b;margin-bottom:18px;display:flex;align-items:center;gap:8px}

  /* Table cards */
  .seller-tbl-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;overflow:hidden;margin-bottom:20px}
  .stc-head{display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid var(--border)}
  .stc-head h2{font-size:.9rem;font-weight:700;color:var(--text);display:flex;align-items:center;gap:8px}
  .stc-head h2 svg{opacity:.6}

  /* Tables */
  .products-tbl{width:100%;border-collapse:collapse;font-size:.8rem}
  .products-tbl th{padding:10px 14px;text-align:left;font-size:.63rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;background:var(--surface2);border-bottom:1px solid var(--border);white-space:nowrap}
  .products-tbl td{padding:11px 14px;border-bottom:1px solid var(--border);vertical-align:middle;color:var(--text)}
  .products-tbl tbody tr:last-child td{border-bottom:none}
  .products-tbl tbody tr:hover td{background:rgba(255,255,255,.02)}

  .p-cell{display:flex;align-items:center;gap:10px}
  .p-thumb{width:38px;height:38px;object-fit:cover;border-radius:7px;background:var(--surface2);border:1px solid var(--border);flex-shrink:0}
  .p-name{font-weight:600;color:var(--text);font-size:.83rem}
  .p-id{font-size:.67rem;color:var(--muted);font-family:var(--mono,'monospace')}

  .badge{display:inline-flex;align-items:center;font-size:.67rem;font-weight:700;padding:2px 8px;border-radius:20px;border:1px solid}
  .badge-green{background:rgba(34,197,94,.1);color:#22c55e;border-color:rgba(34,197,94,.2)}
  .badge-amber{background:rgba(245,158,11,.1);color:#f59e0b;border-color:rgba(245,158,11,.2)}
  .badge-red{background:rgba(239,68,68,.1);color:#ef4444;border-color:rgba(239,68,68,.2)}
  .badge-blue{background:rgba(79,110,247,.1);color:#4f6ef7;border-color:rgba(79,110,247,.2)}
  .badge-purple{background:rgba(168,85,247,.1);color:#a855f7;border-color:rgba(168,85,247,.2)}
  .badge-muted{background:rgba(255,255,255,.06);color:var(--muted);border-color:var(--border)}

  .action-cell{display:flex;gap:5px;flex-wrap:wrap}
  .btn-xs{display:inline-flex;align-items:center;gap:4px;padding:5px 10px;border-radius:6px;font-size:.72rem;font-weight:600;cursor:pointer;border:1px solid;transition:all .15s;text-decoration:none;font-family:inherit;white-space:nowrap}
  .btn-edit{background:transparent;color:#4f6ef7;border-color:rgba(79,110,247,.3)}
  .btn-edit:hover{background:rgba(79,110,247,.08)}
  .btn-del{background:transparent;color:#ef4444;border-color:rgba(239,68,68,.3)}
  .btn-del:hover{background:rgba(239,68,68,.08)}
  .btn-primary{background:#4f6ef7;color:#fff;border-color:#4f6ef7}
  .btn-primary:hover{background:#3d5ce5}

  .price-cell{color:#22c55e;font-family:var(--mono,'monospace');font-size:.8rem}
  .profit-cell{color:#10b981;font-family:var(--mono,'monospace');font-size:.75rem}
  .mono{font-family:var(--mono,'monospace')}
  .muted{color:var(--muted)}

  .empty-dash{text-align:center;padding:48px 20px;color:var(--muted)}
  .empty-dash h3{font-size:1rem;font-weight:700;color:var(--text);margin:10px 0 6px}
  .empty-dash p{font-size:.82rem;margin-bottom:18px}
  .btn-add-first{display:inline-block;padding:9px 20px;background:#4f6ef7;color:#fff;border-radius:8px;font-size:.83rem;font-weight:600;text-decoration:none}
  .btn-add-first:hover{background:#3d5ce5}

  .auction-timer{font-family:var(--mono,'monospace');font-size:.78rem;color:#f59e0b;font-weight:600}
</style>
{% endblock %}

{% block content %}
<div class="seller-page">

  <!-- Header -->
  <div class="seller-header">
    <div>
      <h1>Seller Dashboard</h1>
      <p>Manage your products, track orders and earnings — all in one place.</p>
    </div>
    <a href="{{ url_for('seller.add_product') }}" class="btn-xs btn-primary" style="padding:9px 16px;font-size:.82rem">
      <svg width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Add Product
    </a>
  </div>

  <!-- Stats -->
  <div class="seller-stats">
    <div class="ss-card">
      <div class="ss-num">{{ products|length }}</div>
      <div class="ss-lbl">Total Listed</div>
    </div>
    <div class="ss-card">
      <div class="ss-num" style="color:#22c55e">{{ live|length }}</div>
      <div class="ss-lbl">Live Products</div>
    </div>
    <div class="ss-card">
      <div class="ss-num" style="color:#f59e0b">{{ pending|length }}</div>
      <div class="ss-lbl">Pending Approval</div>
    </div>
    <div class="ss-card">
      <div class="ss-num" style="color:#a855f7">{{ products|selectattr('is_auction','equalto',1)|list|length }}</div>
      <div class="ss-lbl">Auctions</div>
    </div>
    <div class="ss-card">
      <div class="ss-num">{{ total_views }}</div>
      <div class="ss-lbl">Total Views</div>
    </div>
    <div class="ss-card">
      <div class="ss-num">{{ seller_orders|length }}</div>
      <div class="ss-lbl">Total Orders</div>
    </div>
  </div>

  <!-- Earnings Breakdown -->
  <div class="earnings-card">
    <div class="ec-item">
      <div class="ec-lbl">Total Revenue</div>
      <div class="ec-val" style="color:#22c55e">&#8377;{{ "{:,.2f}".format(total_earned) }}</div>
      <div class="ec-sub">From all completed orders</div>
    </div>
    <div class="ec-item">
      <div class="ec-lbl">Active Listings</div>
      <div class="ec-val" style="color:#4f6ef7">{{ live|length }}</div>
      <div class="ec-sub">{{ products|selectattr('is_auction','equalto',1)|list|length }} auction{% if products|selectattr('is_auction','equalto',1)|list|length != 1 %}s{% endif %} running</div>
    </div>
    <div class="ec-item">
      <div class="ec-lbl">Wallet Balance</div>
      <div class="ec-val" style="color:#a855f7">&#8377;{{ "{:,.2f}".format(get_wallet(session.user_id)) }}</div>
      <div class="ec-sub"><a href="{{ url_for('wallet.wallet_home') }}" style="color:#a855f7;text-decoration:none">View &rarr;</a> &nbsp; <a href="{{ url_for('seller.withdraw') }}" style="color:#a855f7;text-decoration:none">Withdraw &rarr;</a></div>
    </div>
  </div>

  <!-- Pending approval notice -->
  {% if pending %}
  <div class="info-bar">
    <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
    You have <strong>{{ pending|length }}</strong> product(s) awaiting admin approval. They will go live once reviewed.
  </div>
  {% endif %}

  <!-- My Products -->
  <div class="seller-tbl-card">
    <div class="stc-head">
      <h2>
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/></svg>
        My Products
        <span style="background:rgba(255,255,255,.08);color:var(--muted);font-size:.67rem;font-weight:600;padding:2px 8px;border-radius:20px;border:1px solid var(--border)">{{ products|length }}</span>
      </h2>
      <a href="{{ url_for('seller.add_product') }}" class="btn-xs btn-primary">Add Product</a>
    </div>
    {% if products %}
    <div style="overflow-x:auto">
      <table class="products-tbl">
        <thead>
          <tr><th>Product</th><th>Category</th><th>Price</th><th>Stock</th><th>Views</th><th>Type</th><th>Status</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {% for p in products %}
          {% set st = p['status'] if p['status'] else ('approved' if p['approved'] else 'pending') %}
          <tr>
            <td>
              <div class="p-cell">
                <img src="{{ p['image'] or 'https://placehold.co/38x38/1e2333/4a5168?text=?' }}" class="p-thumb" alt="">
                <div>
                  <div class="p-name">{{ p['name'][:35] }}{% if p['name']|length > 35 %}…{% endif %}</div>
                  <div class="p-id">#{{ p['id'] }}</div>
                </div>
              </div>
            </td>
            <td><span class="badge badge-blue">{{ p['category'] }}</span></td>
            <td class="price-cell">&#8377;{{ "{:,.2f}".format(p['price']) }}</td>
            <td class="mono muted">{{ p['stock'] }}</td>
            <td class="mono muted">{{ p['views'] or 0 }}</td>
            <td>
              {% if p['is_auction'] %}<span class="badge badge-purple">Auction</span>
              {% else %}<span class="badge badge-muted">Fixed</span>{% endif %}
            </td>
            <td>
              {% if st == 'approved' %}<span class="badge badge-green">Live</span>
              {% elif st == 'pending' %}<span class="badge badge-amber">Pending</span>
              {% elif st == 'rejected' %}<span class="badge badge-red">Rejected</span>
              {% else %}<span class="badge badge-muted">Inactive</span>{% endif %}
            </td>
            <td>
              <div class="action-cell">
                <a href="{{ url_for('seller.edit_product', pid=p['id']) }}" class="btn-xs btn-edit">Edit</a>
                <form method="POST" action="{{ url_for('seller.delete_product', pid=p['id']) }}" onsubmit="return confirm('Delete this product?')">
                  <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                  <button type="submit" class="btn-xs btn-del">Delete</button>
                </form>
              </div>
            </td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <div class="empty-dash">
      <svg width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="color:var(--muted);margin-bottom:8px"><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z"/><line x1="3" y1="6" x2="21" y2="6"/><path d="M16 10a4 4 0 0 1-8 0"/></svg>
      <h3>No products yet</h3>
      <p>Start by listing your first product</p>
      <a href="{{ url_for('seller.add_product') }}" class="btn-add-first">Add Your First Product</a>
    </div>
    {% endif %}
  </div>

  <!-- Orders Received -->
  <div class="seller-tbl-card">
    <div class="stc-head">
      <h2>
        <svg width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        Orders Received
        <span style="background:rgba(255,255,255,.08);color:var(--muted);font-size:.67rem;font-weight:600;padding:2px 8px;border-radius:20px;border:1px solid var(--border)">{{ seller_orders|length }}</span>
      </h2>
    </div>
    {% if seller_orders %}
    <div style="overflow-x:auto">
      <table class="products-tbl">
        <thead>
          <tr><th>Order ID</th><th>Product</th><th>Buyer</th><th>Amount</th><th>Payment</th><th>Status</th><th>Date</th></tr>
        </thead>
        <tbody>
          {% for o in seller_orders %}
          <tr>
            <td class="mono muted" style="font-size:.72rem">QD{{ "%06d"|format(o['id']) }}</td>
            <td>{{ o['product_name'][:28] }}{% if o['product_name']|length > 28 %}…{% endif %}</td>
            <td class="muted">{{ o['buyer_name'] }}</td>
            <td class="price-cell">&#8377;{{ "{:,.2f}".format(o['total_amount'] or o['amount']) }}</td>
            
            <td><span class="badge badge-muted">{{ o['payment_method']|upper }}</span></td>
            <td>
              {% set s = o['status'] %}
              {% if s == 'Delivered' %}<span class="badge badge-green">{{ s }}</span>
              {% elif s == 'Shipped' %}<span class="badge badge-blue">{{ s }}</span>
              {% elif s == 'Confirmed' %}<span class="badge badge-amber">{{ s }}</span>
              {% elif s == 'Cancelled' %}<span class="badge badge-red">{{ s }}</span>
              {% else %}<span class="badge badge-muted">{{ s }}</span>{% endif %}
            </td>
            <td class="mono muted" style="font-size:.72rem">{{ o['created_at'][:10] if o['created_at'] else '—' }}</td>
          </tr>
          {% else %}
          <tr><td colspan="8" style="text-align:center;padding:32px;color:var(--muted);font-size:.82rem">No orders yet</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </div>
    {% else %}
    <div class="empty-dash" style="padding:32px 20px">
      <svg width="36" height="36" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24" style="color:var(--muted);margin-bottom:8px"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
      <h3>No orders yet</h3>
      <p>Orders placed for your products will appear here</p>
    </div>
    {% endif %}
  </div>

</div>
{% endblock %}
