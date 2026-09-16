const AV = {
  user: null,
  csrf() {
    const row = document.cookie.split('; ').find(v => v.startsWith('csrftoken='));
    return row ? decodeURIComponent(row.split('=').slice(1).join('=')) : '';
  },
  async firebaseSession() {
    try {
      const mod = await import('/static/js/firebase.js');
      const firebaseUser = mod.auth.currentUser;
      if (!firebaseUser) return false;
      const idToken = await firebaseUser.getIdToken();
      const res = await fetch('/api/auth/firebase-login/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json', Accept: 'application/json'},
        body: JSON.stringify({id_token: idToken})
      });
      if (!res.ok) return false;
      const data = await res.json();
      this.user = data.user || null;
      return true;
    } catch (_) {
      return false;
    }
  },
  async request(url, options = {}, allowAuthRetry = true) {
    const opts = { credentials: 'same-origin', ...options };
    opts.headers = { Accept: 'application/json', ...(opts.body ? {'Content-Type': 'application/json'} : {}), ...(opts.headers || {}) };
    if (['POST','PUT','PATCH','DELETE'].includes((opts.method || 'GET').toUpperCase())) {
      opts.headers['X-CSRFToken'] = this.csrf();
    }
    const res = await fetch(url, opts);
    let data = {};
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) {
      if (res.status === 401 && allowAuthRetry) {
        const synced = await this.firebaseSession();
        if (synced) return this.request(url, options, false);
      }
      if (res.status === 401) AV.user = null;
      const detail = data.detail || Object.values(data).flat().join(' ') || `Request failed (${res.status})`;
      throw Object.assign(new Error(detail), {status: res.status, data});
    }
    return data;
  },
  get(url) { return this.request(url); },
  post(url, body = {}) { return this.request(url, {method: 'POST', body: JSON.stringify(body)}); },
  async session() {
    try {
      const data = await this.get('/api/auth/me/');
      this.user = data.user;
      if (data.authenticated && data.user) return data;
    } catch (_) {}
    await this.firebaseSession();
    return {authenticated: !!this.user, user: this.user};
  },
  money(value) {
    return new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0}).format(Number(value || 0));
  },
  escape(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  }
};

function setBusy(button, busy, label = 'Working…') {
  if (!button) return;
  if (busy) {
    button.dataset.originalText = button.textContent;
    button.disabled = true;
    button.textContent = label;
  } else {
    button.disabled = false;
    button.textContent = button.dataset.originalText || button.textContent;
  }
}

function notify(message, type = 'info') {
  const host = document.getElementById('toastHost') || (() => {
    const el = document.createElement('div');
    el.id = 'toastHost'; document.body.appendChild(el); return el;
  })();
  const item = document.createElement('div');
  item.className = `toast ${type}`;
  item.textContent = message;
  host.appendChild(item);
  requestAnimationFrame(() => item.classList.add('show'));
  setTimeout(() => { item.classList.remove('show'); setTimeout(() => item.remove(), 250); }, 3200);
}

async function bootNav(options = {}) {
  const nav = document.getElementById('navbar');
  if (!nav) return;
  try { await AV.session(); } catch (_) { AV.user = null; }
  const user = AV.user;
  nav.innerHTML = `
    <div class="nav-inner">
      <a class="brand" href="/static/index.html"><span class="brand-mark">AV</span><span>AV Room</span></a>
      <div class="nav-links">
        <a href="/static/index.html">Availability</a>
        ${user ? '<a href="/static/my-bookings.html">My bookings</a><a href="/static/book.html">Reserve</a>' : ''}
        ${user?.is_staff ? '<a href="/static/dashboard.html">Staff</a>' : ''}
      </div>
      <div class="nav-account">
        ${user ? `<span class="user-pill"><span class="avatar">${AV.escape((user.name || user.username).charAt(0).toUpperCase())}</span>${AV.escape(user.name)}${user.is_staff ? '<b>Admin</b>' : ''}</span><button class="link-button" id="logoutBtn">Log out</button>` : '<a class="button button-small" href="/static/login.html">Log in</a>'}
      </div>
      <button class="menu-toggle" id="menuToggle" aria-label="Toggle menu">☰</button>
    </div>`;

  document.getElementById('menuToggle')?.addEventListener('click', () => nav.classList.toggle('open'));
  document.getElementById('logoutBtn')?.addEventListener('click', async () => {
    try {
      await AV.post('/api/auth/logout/');
      try { const mod = await import('/static/js/firebase.js'); await mod.signOut(mod.auth); } catch (_) {}
      AV.user = null;
      location.href = '/static/index.html';
    } catch (err) { notify(err.message, 'error'); }
  });
}

function requireUser() {
  if (!AV.user) {
    location.href = '/static/login.html?next=' + encodeURIComponent(location.pathname + location.search);
    return false;
  }
  return true;
}

function requireAdmin() {
  if (!AV.user?.is_staff) {
    location.href = '/static/login.html?next=' + encodeURIComponent('/static/dashboard.html');
    return false;
  }
  return true;
}
