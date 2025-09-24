// frontend/src/main.ts
import './style.css'; // include Tailwind styles

const loginForm = document.getElementById('login-form') as HTMLFormElement;
const registerForm = document.getElementById('register-form') as HTMLFormElement;
const googleBtn = document.getElementById('google-btn') as HTMLButtonElement;

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

// Helper: save tokens to localStorage
function storeTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem('accessToken', accessToken);
  localStorage.setItem('refreshToken', refreshToken);
}

// Handle registration form submit
registerForm.onsubmit = async (e) => {
  e.preventDefault();
  const email = (document.getElementById('reg-email') as HTMLInputElement).value;
  const password = (document.getElementById('reg-pass') as HTMLInputElement).value;
  try {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error(`Register failed: ${res.status}`);
    const data = await res.json();
    // Expect { access_token, refresh_token, token_type }
    storeTokens(data.access_token, data.refresh_token);
    // Redirect to private page on success
    window.location.href = '/private/'; // note trailing slash for correct routing
  } catch (err) {
    console.error(err);
    alert('Registration failed');
  }
};

// Handle login form submit
loginForm.onsubmit = async (e) => {
  e.preventDefault();
  const email = (document.getElementById('login-email') as HTMLInputElement).value;
  const password = (document.getElementById('login-pass') as HTMLInputElement).value;
  try {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error(`Login failed: ${res.status}`);
    const data = await res.json();
    storeTokens(data.access_token, data.refresh_token);
    window.location.href = '/private/';
  } catch (err) {
    console.error(err);
    alert('Login failed');
  }
};

// Handle Google login button (simulated for offline use)
googleBtn.onclick = async () => {
  try {
    // Call our backend's Google OAuth callback simulation endpoint
    const res = await fetch(`${API_BASE}/auth/google/callback?code=dummy`);
    if (!res.ok) throw new Error(`Google login failed: ${res.status}`);
    const data = await res.json();
    storeTokens(data.access_token, data.refresh_token);
    window.location.href = '/private/';
  } catch (err) {
    console.error(err);
    alert('Google login failed');
  }
};
