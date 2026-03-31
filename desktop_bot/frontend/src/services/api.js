import { io } from 'socket.io-client';

let API_BASE = import.meta.env.VITE_API_URL || '';
if (window.location.protocol === 'file:') {
  API_BASE = 'http://localhost:5000';
}

export function getSocket() {
  return io(API_BASE, {
    transports: ['websocket', 'polling'],
  });
}

export async function apiUploadCSV(file, type) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('type', type);
  const res = await fetch(`${API_BASE}/api/upload-csv`, {
    method: 'POST',
    body: formData,
  });
  return res.json();
}

export async function apiGetStatus() {
  const res = await fetch(`${API_BASE}/api/status`);
  return res.json();
}
