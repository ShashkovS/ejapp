// frontend/private/main.ts
import '../src/style.css';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';
const itemList = document.getElementById('item-list') as HTMLUListElement;
const itemForm = document.getElementById('item-form') as HTMLFormElement;
const logoutLink = document.getElementById('logout-link');

const accessToken = localStorage.getItem('accessToken');
const refreshToken = localStorage.getItem('refreshToken');

// Redirect to home if not logged in
if (!accessToken) {
  window.location.href = '/';
}

// Helper: authorized fetch
async function apiRequest(path: string, options: RequestInit = {}) {
  const headers = options.headers ? new Headers(options.headers) : new Headers();
  headers.set('Authorization', `Bearer ${localStorage.getItem('accessToken')}`);
  options.headers = headers;
  const response = await fetch(`${API_BASE}${path}`, options);
  // If access token expired (401), attempt refresh
  if (response.status === 401 && refreshToken) {
    const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${refreshToken}` },
    });
    if (refreshRes.ok) {
      const data = await refreshRes.json();
      localStorage.setItem('accessToken', data.access_token);
      // Retry original request with new token
      headers.set('Authorization', `Bearer ${data.access_token}`);
      return fetch(`${API_BASE}${path}`, options);
    }
  }
  return response;
}

// Fetch and display current items on page load
async function loadItems() {
  const res = await apiRequest('/items');
  if (res.ok) {
    const items = await res.json();
    itemList.innerHTML = ''; // clear list
    items.forEach((item: any) => {
      const li = document.createElement('li');
      li.textContent = item.title;
      itemList.appendChild(li);
    });
  } else {
    console.error('Failed to load items', res.status);
    if (res.status === 401) {
      alert('Session expired, please log in again');
      localStorage.clear();
      window.location.href = '/';
    }
  }
}

// Handle new item form submission
itemForm.onsubmit = async (e) => {
  e.preventDefault();
  const titleInput = document.getElementById('item-title') as HTMLInputElement;
  const title = titleInput.value;
  const res = await apiRequest('/items', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  });
  if (res.ok) {
    titleInput.value = '';
    await loadItems(); // refresh list to show new item
  } else {
    alert('Failed to add item');
  }
};

// Handle logout: clear tokens
logoutLink!.onclick = () => {
  localStorage.clear();
};

// Initial load
loadItems();
