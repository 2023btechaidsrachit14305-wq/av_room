const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const loginTab = document.getElementById('loginTab');
const registerTab = document.getElementById('registerTab');
const alertBox = document.getElementById('authAlert');

function authMessage(text, type='error'){ alertBox.textContent=text; alertBox.className=`alert show ${type}`; }
function switchMode(register){
  loginForm.classList.toggle('hidden', register);
  registerForm.classList.toggle('hidden', !register);
  loginTab.classList.toggle('active', !register);
  registerTab.classList.toggle('active', register);
  alertBox.className='alert';
}
loginTab.addEventListener('click', () => switchMode(false));
registerTab.addEventListener('click', () => switchMode(true));

const next = new URLSearchParams(location.search).get('next');

loginForm.addEventListener('submit', async e => {
  e.preventDefault(); alertBox.className='alert';
  const button=document.getElementById('loginButton'); setBusy(button,true,'Signing in…');
  try { await AV.post('/api/auth/login/', {username:document.getElementById('loginUsername').value, password:document.getElementById('loginPassword').value}); notify('Welcome back.','success'); setTimeout(()=>location.href=next || '/static/index.html',180); }
  catch(err){ authMessage(err.message); }
  finally{ setBusy(button,false); }
});

registerForm.addEventListener('submit', async e => {
  e.preventDefault(); alertBox.className='alert';
  const button=document.getElementById('registerButton'); setBusy(button,true,'Creating…');
  try {
    await AV.post('/api/auth/register/', {
      first_name:document.getElementById('firstName').value,
      last_name:document.getElementById('lastName').value,
      username:document.getElementById('registerUsername').value,
      email:document.getElementById('registerEmail').value,
      password:document.getElementById('registerPassword').value
    });
    notify('Account created. You are signed in.','success');
    setTimeout(()=>location.href=next || '/static/my-bookings.html',180);
  } catch(err){ authMessage(err.message); }
  finally{ setBusy(button,false); }
});

bootNav();
