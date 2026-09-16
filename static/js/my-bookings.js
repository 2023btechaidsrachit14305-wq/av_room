const list = document.getElementById('bookingsList');
const alertBox = document.getElementById('pageAlert');
const filter = document.getElementById('bookingFilter');
const refreshButton = document.getElementById('refreshBookings');
const lastUpdated = document.getElementById('lastUpdated');
const statTotal = document.getElementById('statTotal');
const statActive = document.getElementById('statActive');
const statDueSoon = document.getElementById('statDueSoon');
const statReturned = document.getElementById('statReturned');

let allBookings = [];

function showError(text) {
  alertBox.textContent = text;
  alertBox.className = 'alert show error';
}

function clearError() {
  alertBox.className = 'alert';
  alertBox.textContent = '';
}

function parseLocalDate(value) {
  return value ? new Date(`${value}T00:00:00`) : null;
}

function daysUntil(value) {
  const due = parseLocalDate(value);
  if (!due) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.ceil((due - today) / 86400000);
}

function badge(status) {
  const map = {reserved:'warn', checked_out:'ok', returned:'ok', cancelled:'danger'};
  const label = String(status || 'unknown').replaceAll('_', ' ');
  return `<span class="status ${map[status] || ''}">${AV.escape(label)}</span>`;
}

function dueLabel(booking) {
  if (booking.status !== 'checked_out' && booking.status !== 'reserved') return '';
  const days = daysUntil(booking.due_date);
  if (days === null) return '';
  if (days < 0) return `<span class="due-note overdue">${Math.abs(days)} day(s) overdue</span>`;
  if (days === 0) return '<span class="due-note due-today">Due today</span>';
  if (days <= 2) return `<span class="due-note due-soon">Due in ${days} day(s)</span>`;
  return `<span class="due-note">${days} day(s) remaining</span>`;
}

function filteredBookings() {
  const value = filter.value;
  if (value === 'active') return allBookings.filter(b => ['reserved', 'checked_out'].includes(b.status));
  return value === 'all' ? allBookings : allBookings.filter(b => b.status === value);
}

function updateStats() {
  const active = allBookings.filter(b => ['reserved', 'checked_out'].includes(b.status));
  const dueSoon = active.filter(b => {
    const days = daysUntil(b.due_date);
    return days !== null && days <= 2;
  });
  statTotal.textContent = allBookings.length;
  statActive.textContent = active.length;
  statDueSoon.textContent = dueSoon.length;
  statReturned.textContent = allBookings.filter(b => b.status === 'returned').length;
}

function renderBookings() {
  const rows = filteredBookings();
  if (!rows.length) {
    list.innerHTML = `<div class="empty booking-empty">
      <div class="empty-icon">▣</div>
      <h3>${allBookings.length ? 'No bookings in this filter' : 'No bookings yet'}</h3>
      <p>${allBookings.length ? 'Try another filter to see your other reservations.' : 'Your reservations will appear here as soon as you make one.'}</p>
      ${allBookings.length ? '' : '<a class="button button-small" href="/static/index.html">Find equipment</a>'}
    </div>`;
    return;
  }

  list.innerHTML = `<div class="cards booking-cards">${rows.map(b => {
    const due = dueLabel(b);
    const refund = b.status === 'returned' ? `<div class="booking-money"><span>Refund</span><strong>${AV.money(b.refund_amount)}</strong></div>` : '';
    const late = b.late_fee_charged > 0 ? `<div class="tiny overdue-fee">Late fee: ${AV.money(b.late_fee_charged)}</div>` : '';
    const cancel = b.status === 'reserved' ? `<button class="button button-danger button-small" data-cancel="${AV.escape(b.id)}">Cancel reservation</button>` : '';
    return `<article class="equipment-card booking-card">
      <div class="meta booking-meta">${badge(b.status)}<span class="chip">#${AV.escape(b.id)}</span></div>
      <div class="booking-title"><h3>${AV.escape(b.equipment_unit?.name || 'Equipment')}</h3><p class="tiny">${AV.escape(b.equipment_unit?.asset_tag || 'Asset')} · ${AV.escape(b.equipment_unit?.category || '')}</p></div>
      <div class="booking-dates"><div><span class="tiny">Borrowing period</span><strong>${AV.escape(b.start_date)} → ${AV.escape(b.due_date)}</strong></div>${due}</div>
      <div class="booking-money"><span>Deposit</span><strong>${AV.money(b.deposit_charged)}</strong></div>
      ${late}${refund}
      ${b.status === 'returned' ? `<p class="tiny">Returned on ${AV.escape(b.returned_date || '—')}</p>` : ''}
      ${cancel}
    </article>`;
  }).join('')}</div>`;

  list.querySelectorAll('[data-cancel]').forEach(button => {
    button.addEventListener('click', () => cancelBooking(button.dataset.cancel));
  });
}

async function loadBookings() {
  clearError();
  refreshButton.disabled = true;
  refreshButton.textContent = 'Refreshing…';
  lastUpdated.textContent = 'Syncing with your account…';
  try {
    await AV.session();
    if (!AV.user) {
      location.href = '/static/login.html?next=' + encodeURIComponent('/static/my-bookings.html');
      return;
    }
    const data = await AV.get('/api/my-bookings/');
    allBookings = Array.isArray(data) ? data : [];
    updateStats();
    renderBookings();
    lastUpdated.textContent = `Synced just now · ${allBookings.length} booking${allBookings.length === 1 ? '' : 's'}`;
  } catch (error) {
    allBookings = [];
    updateStats();
    showError(`We couldn't load your bookings. ${error.message || 'Please try again.'}`);
    list.innerHTML = `<div class="empty booking-empty"><div class="empty-icon">!</div><h3>Unable to load bookings</h3><p>Your data may still be saved. Refresh the page or try again.</p><button class="button button-small" id="retryBookings" type="button">Try again</button></div>`;
    document.getElementById('retryBookings')?.addEventListener('click', loadBookings);
    lastUpdated.textContent = 'Last sync failed';
  } finally {
    refreshButton.disabled = false;
    refreshButton.textContent = '↻ Refresh';
  }
}

async function cancelBooking(id) {
  if (!confirm('Cancel this reservation?')) return;
  try {
    await AV.post(`/api/bookings/${encodeURIComponent(id)}/cancel/`);
    notify('Reservation cancelled.', 'success');
    await loadBookings();
  } catch (error) {
    showError(error.message || 'Unable to cancel the reservation.');
  }
}

filter.addEventListener('change', renderBookings);
refreshButton.addEventListener('click', loadBookings);

bootNav().then(loadBookings);
