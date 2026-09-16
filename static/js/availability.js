const form = document.getElementById('availability-form');
const results = document.getElementById('results');
const alertBox = document.getElementById('searchAlert');
const startInput = document.getElementById('start_date');
const endInput = document.getElementById('end_date');
const searchButton = document.getElementById('searchBtn');

const today = new Date();
const todayISO = new Date(today.getTime() - today.getTimezoneOffset() * 60000).toISOString().slice(0,10);
startInput.min = todayISO; endInput.min = todayISO;
startInput.value = todayISO;
const tomorrow = new Date(today); tomorrow.setDate(today.getDate() + 1);
endInput.value = new Date(tomorrow.getTime() - tomorrow.getTimezoneOffset() * 60000).toISOString().slice(0,10);

function showAlert(text, type='success') { alertBox.textContent = text; alertBox.className = `alert show ${type}`; }
function clearAlert(){ alertBox.className='alert'; alertBox.textContent=''; }

form.addEventListener('submit', async e => {
  e.preventDefault(); clearAlert(); results.innerHTML='';
  if (endInput.value <= startInput.value) return showAlert('End date must be after the start date.', 'error');
  setBusy(searchButton, true, 'Searching…');
  try {
    const qs = new URLSearchParams({category: document.getElementById('category').value, start_date:startInput.value, end_date:endInput.value});
    const data = await AV.get(`/api/availability/?${qs}`);
    if (!data.length) { showAlert('Nothing is free for those dates. Try another date range.', 'error'); results.innerHTML='<div class="empty">No equipment units match this date range.</div>'; return; }
    showAlert(`${data.length} unit${data.length === 1 ? '' : 's'} available.`);
    results.innerHTML = data.map(u => `<article class="equipment-card"><div class="meta"><span class="chip">${AV.escape(u.equipment_type.category)}</span><span class="status ok">Available</span></div><div><h3>${AV.escape(u.equipment_type.name)}</h3><p class="tiny">Asset tag · ${AV.escape(u.asset_tag)}</p></div><div class="price-row"><span><span class="tiny">Deposit</span><br><strong>${AV.money(u.equipment_type.deposit_amount)}</strong></span><a class="button button-small" href="/static/book.html?unit=${u.id}&start=${startInput.value}&due=${endInput.value}">Reserve</a></div></article>`).join('');
  } catch (err) { showAlert(err.message, 'error'); }
  finally { setBusy(searchButton, false); }
});
