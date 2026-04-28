/* 
   QuickDealr v2 — Main JavaScript
    */

//  Search autocomplete 
const searchInput = document.getElementById('searchInput');
const searchDrop  = document.getElementById('searchDrop');

if (searchInput && searchDrop) {
  let timer;
  searchInput.addEventListener('input', () => {
    clearTimeout(timer);
    const q = searchInput.value.trim();
    if (!q) { searchDrop.classList.remove('open'); return; }
    timer = setTimeout(() => fetchSuggestions(q), 220);
  });

  async function fetchSuggestions(q) {
    try {
      const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await r.json();
      if (!data.length) { searchDrop.classList.remove('open'); return; }
      searchDrop.innerHTML = data.map(p => `
        <div class="sdrop-item" onclick="location.href='/${p.is_auction ? 'auction' : 'product'}/${p.id}'">
          <img class="sdrop-img" src="${p.image || 'https://via.placeholder.com/40'}" alt="">
          <div class="sdrop-info">
            <div class="sdrop-name">${p.name}</div>
            <div class="sdrop-cat">${p.category}</div>
          </div>
          <span class="sdrop-price">Rs.${parseFloat(p.price).toFixed(0)}</span>
          ${p.is_auction ? '<span class="sdrop-badge">AUCTION</span>' : ''}
        </div>
      `).join('');
      searchDrop.classList.add('open');
    } catch (e) {
      searchDrop.classList.remove('open');
    }
  }

  document.addEventListener('click', e => {
    if (!e.target.closest('.search-wrap')) searchDrop.classList.remove('open');
  });
}

//  Chat FAB 
function toggleChat() {
  const w = document.getElementById('chatWidget');
  if (w) w.classList.toggle('open');
}

const botReplies = [
  "Thanks for reaching out! We'll assist you shortly.",
  "Our team is happy to help! Please describe your issue.",
  "You can track orders from 'My Orders' page.",
  "We offer 30-day hassle-free returns on all products.",
  "Auction bids are binding — please bid responsibly!",
  "Free shipping on orders above Rs.499 ",
  "Delivery usually takes 1-3 business days.",
];

function sendChatMsg() {
  const inp = document.getElementById('chatInputField');
  const box = document.getElementById('chatMessages');
  if (!inp || !inp.value.trim()) return;
  const msg = inp.value.trim();
  inp.value = '';

  const user = document.createElement('div');
  user.className = 'chat-bubble user';
  user.textContent = msg;
  box.appendChild(user);
  box.scrollTop = box.scrollHeight;

  setTimeout(() => {
    const bot = document.createElement('div');
    bot.className = 'chat-bubble bot';
    bot.textContent = botReplies[Math.floor(Math.random() * botReplies.length)];
    box.appendChild(bot);
    box.scrollTop = box.scrollHeight;
  }, 800);
}

function handleChatKey(e) {
  if (e.key === 'Enter') sendChatMsg();
}

//  Wishlist toggle 
async function toggleWish(pid, btn) {
  try {
    const r = await fetch(`/wishlist/toggle/${pid}`, { method: 'POST' });
    const d = await r.json();
    if (!d.ok) { location.href = '/login'; return; }
    btn.classList.toggle('liked', d.liked);
    showToast(d.liked ? 'Added to wishlist ' : 'Removed from wishlist', d.liked ? 'success' : 'error');
  } catch(e) {}
}

//  Countdown timers (product cards & ending list) 
function formatTime(secs) {
  if (secs <= 0) return 'Ended';
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m`;
  return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
}

// Card timers
const cardTimers = document.querySelectorAll('.pcard-timer[data-secs]');
cardTimers.forEach(el => {
  let secs = parseInt(el.dataset.secs) || 0;
  function tick() {
    el.textContent = secs > 0 ? formatTime(secs) : 'Ended';
    if (secs <= 300) el.style.color = 'var(--red)';
    if (secs > 0) secs--;
  }
  tick();
  setInterval(tick, 1000);
});

// Auction grid countdown chips
const auctionCountdowns = document.querySelectorAll('.auction-countdown[data-secs]');
auctionCountdowns.forEach(el => {
  let secs = parseInt(el.dataset.secs) || 0;
  const valEl = el.querySelector('.countdown-val');
  if (!valEl) return;
  function tick() {
    if (secs <= 0) { valEl.textContent = 'Ended'; return; }
    valEl.textContent = formatTime(secs);
    if (secs <= 300) el.classList.add('urgent');
    secs--;
  }
  tick();
  setInterval(tick, 1000);
});

// Ending-soon row timers
const endingTimers = document.querySelectorAll('.ending-timer[data-secs]');
endingTimers.forEach(el => {
  let secs = parseInt(el.dataset.secs) || 0;
  function tick() {
    el.textContent = secs > 0 ? formatTime(secs) : 'Ended';
    if (secs > 0) secs--;
  }
  tick();
  setInterval(tick, 1000);
});

//  Toast system 
function showToast(msg, type = 'success') {
  const zone = document.getElementById('toastZone');
  if (!zone) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `
    <span class="toast-icon">${type === 'success' ? '' : 'x'}</span>
    <span>${msg}</span>
    <button class="toast-close" onclick="this.closest('.toast').remove()">×</button>`;
  zone.appendChild(t);
  setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(32px)'; t.style.transition='all .3s'; setTimeout(()=>t.remove(),300); }, 4000);
}

// Auto-dismiss existing flash toasts
document.querySelectorAll('.toast[data-auto]').forEach(t => {
  setTimeout(() => {
    t.style.opacity='0';
    t.style.transform='translateX(32px)';
    t.style.transition='all .3s';
    setTimeout(()=>t.remove(),300);
  }, 4000);
});

//  Image fallback 
document.querySelectorAll('img').forEach(img => {
  img.addEventListener('error', () => {
    if (!img.src.includes('placeholder')) img.src = 'https://via.placeholder.com/300x300?text=No+Image';
  });
});

//  Poll for new notifications 
async function checkNotifications() {
  try {
    const r = await fetch('/api/notifications');
    const data = await r.json();
    if (data.length > 0) {
      data.forEach(n => showToast(n.message, 'error'));
    }
  } catch(e) {}
}
if (document.querySelector('.nav-icon-btn')) {
  setInterval(checkNotifications, 30000);
}

/* 
   QuickDealr v3 — RBAC-aware JS additions
    */

//  Search (buyer-only pages call this) 
const searchInputEl = document.getElementById('searchInput');
const searchDropEl  = document.getElementById('searchDrop');
if (searchInputEl && searchDropEl) {
  let timer;
  searchInputEl.addEventListener('input', () => {
    clearTimeout(timer);
    const q = searchInputEl.value.trim();
    if (!q) { searchDropEl.classList.remove('open'); return; }
    timer = setTimeout(async () => {
      try {
        const r    = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
        const data = await r.json();
        if (!data.data || !data.data.length) { searchDropEl.classList.remove('open'); return; }
        searchDropEl.innerHTML = data.data.map(p => `
          <div class="sdrop-item" onclick="location.href='/${p.is_auction ? 'auction' : 'product'}/${p.id}'">
            <img class="sdrop-img" src="${p.image || 'https://via.placeholder.com/40'}" alt="">
            <div class="sdrop-info">
              <div class="sdrop-name">${p.name}</div>
              <div class="sdrop-cat">${p.category}</div>
            </div>
            <span class="sdrop-price">Rs.${parseFloat(p.price).toFixed(0)}</span>
            ${p.is_auction ? '<span class="sdrop-badge">AUCTION</span>' : ''}
          </div>`).join('');
        searchDropEl.classList.add('open');
      } catch (e) { searchDropEl.classList.remove('open'); }
    }, 220);
  });
  document.addEventListener('click', e => {
    if (!e.target.closest('.search-wrap')) searchDropEl.classList.remove('open');
  });
}

// ── Hero live auction count ──
async function fetchLiveCount() {
  const el = document.getElementById('liveCount');
  if (!el) return;
  try {
    const r = await fetch('/api/live_auctions');
    const d = await r.json();
    if (d.data !== undefined) el.textContent = d.data;
  } catch(e) { el.textContent = '—'; }
}
if (document.getElementById('liveCount')) {
  fetchLiveCount();
  setInterval(fetchLiveCount, 15000);
}
