import { auth, signInWithEmailAndPassword, createUserWithEmailAndPassword } from '/static/js/firebase.js';

const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');
const loginTab = document.getElementById('loginTab');
const registerTab = document.getElementById('registerTab');
const alertBox = document.getElementById('authAlert');

function authMessage(text, type = 'error') {
  alertBox.textContent = text;
  alertBox.className = `alert show ${type}`;
}

function switchMode(register) {
  loginForm.classList.toggle('hidden', register);
  registerForm.classList.toggle('hidden', !register);
  loginTab.classList.toggle('active', !register);
  registerTab.classList.toggle('active', register);
  alertBox.className = 'alert';
}

loginTab.addEventListener('click', () => switchMode(false));
registerTab.addEventListener('click', () => switchMode(true));

const next = new URLSearchParams(location.search).get('next');

function friendlyFirebaseError(error) {
  const code = error?.code || '';
  const messages = {
    'auth/invalid-credential': 'Invalid email or password.',
    'auth/invalid-login-credentials': 'Invalid email or password.',
    'auth/email-already-in-use': 'That email is already registered.',
    'auth/weak-password': 'Choose a stronger password.',
    'auth/invalid-email': 'Enter a valid email address.',
    'auth/too-many-requests': 'Too many attempts. Please try again later.'
  };
  return messages[code] || error?.message || 'Authentication failed.';
}

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  alertBox.className = 'alert';
  const button = document.getElementById('loginButton');
  setBusy(button, true, 'Signing in…');
  try {
    const credential = await signInWithEmailAndPassword(
      auth,
      document.getElementById('loginUsername').value.trim(),
      document.getElementById('loginPassword').value
    );
    const idToken = await credential.user.getIdToken(true);
    await AV.post('/api/auth/firebase-login/', { id_token: idToken });
    notify('Welcome back.', 'success');
    setTimeout(() => { location.href = next || '/static/index.html'; }, 150);
  } catch (error) {
    authMessage(friendlyFirebaseError(error));
  } finally {
    setBusy(button, false);
  }
});

registerForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  alertBox.className = 'alert';
  const email = document.getElementById('registerEmail').value.trim().toLowerCase();
  const button = document.getElementById('registerButton');
  setBusy(button, true, 'Creating…');
  try {
    const credential = await createUserWithEmailAndPassword(
      auth,
      email,
      document.getElementById('registerPassword').value
    );
    const idToken = await credential.user.getIdToken(true);
    await AV.post('/api/auth/register-profile/', {
      id_token: idToken,
      first_name: document.getElementById('firstName').value.trim(),
      last_name: document.getElementById('lastName').value.trim(),
      username: document.getElementById('registerUsername').value.trim().toLowerCase()
    });
    notify('Account created. You are signed in.', 'success');
    setTimeout(() => { location.href = next || '/static/my-bookings.html'; }, 150);
  } catch (error) {
    authMessage(error?.message?.includes('username') ? error.message : friendlyFirebaseError(error));
  } finally {
    setBusy(button, false);
  }
});

bootNav();
