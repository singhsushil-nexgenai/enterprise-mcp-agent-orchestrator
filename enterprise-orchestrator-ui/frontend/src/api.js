const API_BASE = '/api';

export async function submitJob(payload) {
  const res = await fetch(`${API_BASE}/jobs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Submit failed');
  }
  return res.json();
}

export async function listJobs(limit = 50, offset = 0) {
  const res = await fetch(`${API_BASE}/jobs?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error('Failed to fetch jobs');
  return res.json();
}

export async function getJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`);
  if (!res.ok) throw new Error('Job not found');
  return res.json();
}

export async function cancelJob(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Cancel failed');
  }
  return res.json();
}

export async function getAuditTrail(jobId) {
  const res = await fetch(`${API_BASE}/jobs/${jobId}/audit`);
  if (!res.ok) throw new Error('Audit fetch failed');
  return res.json();
}
