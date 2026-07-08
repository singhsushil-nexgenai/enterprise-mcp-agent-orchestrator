import React, { useState, useEffect, useCallback } from 'react';
import { submitJob, listJobs, cancelJob, getAuditTrail } from './api';

function StatusBadge({ status }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}

function SubmitForm({ onSubmitted }) {
  const [jobName, setJobName] = useState('');
  const [tableName, setTableName] = useState('');
  const [repo, setRepo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!jobName && !tableName) { setError('Enter job name or table name'); return; }
    setLoading(true);
    try {
      await submitJob({ job_name: jobName || null, table_name: tableName || null, repo: repo || null });
      setJobName(''); setTableName(''); setRepo('');
      onSubmitted();
    } catch (err) { setError(err.message); }
    setLoading(false);
  };

  return (
    <div className="card">
      <h2>Submit New Job</h2>
      <form onSubmit={handleSubmit}>
        <div className="form-row">
          <div>
            <label>Job Name</label>
            <input value={jobName} onChange={e => setJobName(e.target.value)} placeholder="e.g. cmpgn_api_dtl_stg_ddly" />
          </div>
          <div>
            <label>Table Name</label>
            <input value={tableName} onChange={e => setTableName(e.target.value)} placeholder="e.g. CMPGN.TGT.TABLE" />
          </div>
          <div>
            <label>Repo</label>
            <select value={repo} onChange={e => setRepo(e.target.value)}>
              <option value="">Auto-detect</option>
              <option value="cmpgn">cmpgn</option>
              <option value="uma">uma</option>
              <option value="rvnu">rvnu</option>
            </select>
          </div>
          <div style={{ alignSelf: 'flex-end' }}>
            <button className="btn btn-primary" disabled={loading}>{loading ? 'Submitting...' : 'Submit Job'}</button>
          </div>
        </div>
        {error && <p style={{ color: 'var(--danger)', fontSize: '0.85rem' }}>{error}</p>}
      </form>
    </div>
  );
}

function JobTable({ jobs, onRefresh, onSelectJob }) {
  return (
    <div className="card">
      <h2>Jobs <button className="refresh-btn" onClick={onRefresh}>&#x21bb; Refresh</button></h2>
      <table>
        <thead>
          <tr><th>ID</th><th>Job Name</th><th>Repo</th><th>Status</th><th>Updated</th><th>Artifact</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {jobs.map(j => (
            <tr key={j.job_id}>
              <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{j.job_id.slice(0, 8)}</td>
              <td>{j.requested_job_name || j.requested_table_name || '—'}</td>
              <td>{j.repo || 'auto'}</td>
              <td><StatusBadge status={j.status} /></td>
              <td style={{ fontSize: '0.8rem' }}>{new Date(j.updated_at).toLocaleString()}</td>
              <td>{j.artifact_url ? <a href={j.artifact_url} target="_blank" rel="noreferrer" className="btn btn-primary" style={{padding:'0.2rem 0.6rem',fontSize:'0.75rem',textDecoration:'none'}}>&#x1F4C4; View Report</a> : '—'}</td>
              <td>
                <button className="refresh-btn" onClick={() => onSelectJob(j.job_id)}>Audit</button>
                {['submitted','queued','running'].includes(j.status) && (
                  <button className="btn btn-danger" style={{ marginLeft: '0.25rem', padding: '0.15rem 0.5rem', fontSize: '0.75rem' }}
                    onClick={async () => { await cancelJob(j.job_id); onRefresh(); }}>Cancel</button>
                )}
              </td>
            </tr>
          ))}
          {jobs.length === 0 && <tr><td colSpan={7} style={{ textAlign: 'center', color: 'var(--muted)' }}>No jobs yet</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

function AuditPanel({ jobId, onClose }) {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    if (jobId) getAuditTrail(jobId).then(setEvents).catch(() => setEvents([]));
  }, [jobId]);

  if (!jobId) return null;
  return (
    <div className="card">
      <h2>Audit Trail — {jobId.slice(0, 8)} <button className="refresh-btn" onClick={onClose}>Close</button></h2>
      <div className="audit-panel">
        {events.map(ev => (
          <div key={ev.id} className="audit-item">
            <span className="ts">{new Date(ev.timestamp).toLocaleString()}</span>
            <strong>{ev.event_type}</strong> — {ev.detail} <em>({ev.actor})</em>
          </div>
        ))}
        {events.length === 0 && <p style={{ color: 'var(--muted)' }}>No audit events</p>}
      </div>
    </div>
  );
}

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);

  const refresh = useCallback(() => { listJobs().then(setJobs).catch(() => {}); }, []);

  useEffect(() => { refresh(); const t = setInterval(refresh, 5000); return () => clearInterval(t); }, [refresh]);

  return (
    <div className="container">
      <h1>Enterprise Orchestrator</h1>
      <SubmitForm onSubmitted={refresh} />
      <JobTable jobs={jobs} onRefresh={refresh} onSelectJob={setSelectedJob} />
      <AuditPanel jobId={selectedJob} onClose={() => setSelectedJob(null)} />
    </div>
  );
}
