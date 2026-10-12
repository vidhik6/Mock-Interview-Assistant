const form = document.getElementById('authForm');
const statusEl = document.getElementById('authStatus');
const titleEl = document.getElementById('authTitle');
const hintEl = document.getElementById('authHint');
const submitEl = document.getElementById('authSubmit');
let mode = 'login';

function setMode(nextMode) {
  mode = nextMode;
  const registering = mode === 'register';
  document.querySelectorAll('.auth-tab').forEach(tab => tab.classList.toggle('active', tab.dataset.mode === mode));
  titleEl.textContent = registering ? 'Create your account' : 'Welcome back';
  hintEl.textContent = registering ? 'Your sessions will be private to this account.' : 'Use your account to continue practicing.';
  submitEl.textContent = registering ? 'Create account' : 'Log in';
  document.getElementById('password').autocomplete = registering ? 'new-password' : 'current-password';
}

document.querySelectorAll('.auth-tab').forEach(tab => tab.addEventListener('click', () => setMode(tab.dataset.mode)));
form.addEventListener('submit', async event => {
  event.preventDefault();
  statusEl.textContent = 'Working...';
  submitEl.disabled = true;
  try {
    const response = await fetch(`/api/auth/${mode === 'register' ? 'register' : 'login'}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: document.getElementById('username').value, password: document.getElementById('password').value }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail?.message || 'Authentication failed.');
    const next = new URLSearchParams(window.location.search).get('next');
    window.location.href = next && next.startsWith('/') ? next : '/practice';
  } catch (error) {
    statusEl.textContent = error.message;
  } finally {
    submitEl.disabled = false;
  }
});
