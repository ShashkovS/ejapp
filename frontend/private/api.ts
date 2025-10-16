import type { ReportsResponse } from './types';

const API_BASE = (import.meta as any).env?.VITE_API_BASE || 'http://localhost:8000';

function clearSession() {
  localStorage.removeItem('accessToken');
  localStorage.removeItem('refreshToken');
}

export function logout() {
  clearSession();
  window.location.href = '/';
}

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) {
    return null;
  }
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${refreshToken}` },
  });
  if (!response.ok) {
    return null;
  }
  const data = await response.json();
  localStorage.setItem('accessToken', data.access_token);
  localStorage.setItem('refreshToken', data.refresh_token);
  return data.access_token as string;
}

async function authorizedFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const headers = new Headers(options.headers);
  const accessToken = localStorage.getItem('accessToken');
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }
  options.headers = headers;

  const response = await fetch(`${API_BASE}${path}`, options);
  if (response.status !== 401) {
    return response;
  }

  const refreshedToken = await refreshAccessToken();
  if (!refreshedToken) {
    logout();
    throw new Error('Session expired');
  }

  headers.set('Authorization', `Bearer ${refreshedToken}`);
  return fetch(`${API_BASE}${path}`, options);
}

export async function fetchReports(): Promise<ReportsResponse> {
  const response = await authorizedFetch('/private/reports');
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || 'Unable to load reports');
  }
  return response.json();
}
