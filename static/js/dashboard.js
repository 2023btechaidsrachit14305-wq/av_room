const wrap = document.getElementById('table-wrap');
const message = document.getElementById('message');
const stats = document.getElementById('stats');
const adminForm = document.getElementById('adminForm');
const adminModal = document.getElementById('adminModal');

function showMessage(text, error = false) { message.textContent = text; message.className = `alert show ${error ? 'error' : 'success'}`; }
function statusBadge(status) { const type = status === 'checked_out' ? 'ok' : 'warn'; return `<span class="status ${type}">${AV.escape(status.replace('_',' '))}</span>`; }

async function loadDashboard() {
  if (!requireAdmin()) return;
  try {
    const rows = await AV.get('/api/dashboard/');
    const overdue = rows.filter(r => r.days_overdue > 0).length;
    const checkedOut = rows.filter(r => r.status === 'checked_out').length;
    if (stats) stats.innerHTML = `<div class="stat"><div class="num">${rows.length}</div><div class="label">Needs attention</div></div><div class="stat"><div class="num">${overdue}</div><div class="label">Overdue</div></div><div class="stat"><div class="num">${checkedOut}</div><div class="label">Checked out</div></div><div class="stat"><div class="num">${rows.filter(r => r.days_overdue === 0).length}</div><div class="label">Due soon</div></div>`;
    if (!rows.length) { wrap.innerHTML = '<div class="empty"><h3>All clear</h3><p>No active reservations need attention right now.</p></div>'; return; }
    wrap.innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Booking</th><th>Borrower</th><th>Equipment</th><th>Due</th><th>Status</th><th>Actions</th></tr></thead><tbody>${rows.map(b => `<tr data-id="${b.id}"><td>#${b.id}</td><td><strong>${AV.escape(b.borrower.name)}</strong><br><span class="tiny">@${AV.escape(b.borrower.username)}</span></td><td><strong>${AV.escape(b.equipment_unit.name)}</strong><br><span class="tiny">${AV.escape(b.equipment_unit.asset_tag)}</span></td><td>${AV.escape(b.due_date)}<br><span class="tiny">${b.days_overdue ? `${b.days_overdue} day(s) overdue` : 'Due soon'}</span></td><td>${statusBadge(b.status)}</td><td class="actions">${b.status === 'reserved' ? '<button class="button button-small" data-action="checkout">Check out</button>' : '<button class="button button-small button-secondary" data-action="return">Return</button><select class="transfer-select"><option value="">Transfer…</option></select>'}</td></tr>`).join('')}</tbody></table></div>`;
    if (rows.some(r => r.status === 'checked_out')) {
      const users = await AV.get('/api/borrowers/');
      rows.filter(r => r.status === 'checked_out').forEach(b => {
        const select = wrap.querySelector(`tr[data-id="${b.id}"] .transfer-select`); if (!select) return;
        users.filter(u => u.id !== b.borrower_id).forEach(u => { const option = document.createElement('option'); option.value = u.id; option.textContent = `${u.name} (@${u.username})`; select.appendChild(option); });
      });
    }
  } catch (err) { showMessage(err.message, true); }
}

wrap.addEventListener('click', async e => {
  const button = e.target.closest('button[data-action]'); if (!button) return;
  const id = button.closest('tr').dataset.id; setBusy(button, true, button.dataset.action === 'checkout' ? 'Checking out…' : 'Returning…');
  try {
    if (button.dataset.action === 'checkout') { await AV.post(`/api/bookings/${id}/checkout/`); notify('Equipment checked out.', 'success'); }
    else { const result = await AV.post(`/api/bookings/${id}/return/`); notify(`Returned · late fee ${AV.money(result.late_fee)} · refund ${AV.money(result.refund_amount)}.`, 'success'); }
    await loadDashboard();
  } catch (err) { showMessage(err.message, true); }
});

wrap.addEventListener('change', async e => {
  const select = e.target.closest('.transfer-select'); if (!select || !select.value) return;
  const id = select.closest('tr').dataset.id; setBusy(select, true, 'Transferring…');
  try { const result = await AV.post(`/api/bookings/${id}/transfer/`, { new_borrower_id: Number(select.value) }); notify(`Transferred. Due date remains ${result.due_date_unchanged}.`, 'success'); await loadDashboard(); }
  catch (err) { showMessage(err.message, true); select.disabled = false; select.value = ''; }
});

document.getElementById('addAdminBtn')?.addEventListener('click', () => adminModal?.classList.add('show'));
document.getElementById('closeAdmin')?.addEventListener('click', () => adminModal?.classList.remove('show'));
adminModal?.addEventListener('click', e => { if (e.target === adminModal) adminModal.classList.remove('show'); });
adminForm?.addEventListener('submit', async e => {
  e.preventDefault(); const button = adminForm.querySelector('button[type="submit"]'); setBusy(button, true, 'Creating…');
  try { await AV.post('/api/admins/', { name: adminForm.name.value.trim(), username: adminForm.username.value.trim(), email: adminForm.email.value.trim(), password: adminForm.password.value }); adminForm.reset(); adminModal.classList.remove('show'); notify('Admin account created.', 'success'); }
  catch (err) { showMessage(err.message, true); }
  finally { setBusy(button, false); }
});
bootNav().then(loadDashboard);
