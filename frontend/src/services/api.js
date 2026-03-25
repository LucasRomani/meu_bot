import { io } from 'socket.io-client';

const API_BASE = import.meta.env.VITE_API_URL || '';

export function getSocket(token) {
  return io(API_BASE, {
    query: { token },
    transports: ['websocket', 'polling'],
  });
}

export async function apiLogin(username, password) {
  const res = await fetch(`${API_BASE}/api/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  return res.json();
}

export async function apiRegister(username, password) {
  const res = await fetch(`${API_BASE}/api/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  return res.json();
}

export async function apiUploadCSV(file, type, token) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  const res = await fetch(`${API_BASE}/api/upload-csv`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  return res.json();
}

export async function apiGetStatus(token) {
  const res = await fetch(`${API_BASE}/api/status`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function apiGetHistory(token) {
  const res = await fetch(`${API_BASE}/api/history`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function apiGetExecutionLogs(executionId, token) {
  const res = await fetch(`${API_BASE}/api/history/${executionId}/logs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function apiGetCredentials(token) {
  const res = await fetch(`${API_BASE}/api/credentials`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

export async function apiSaveCredential(credentialData, token) {
  const res = await fetch(`${API_BASE}/api/credentials`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(credentialData),
  });
  return res.json();
}
