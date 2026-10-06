import React, { useState, useEffect } from 'react';

function App() {
  const [healthStatus, setHealthStatus] = useState('checking...');

  useEffect(() => {
    fetch('http://127.0.0.1:8000/health')
      .then((res) => {
        if (!res.ok) throw new Error('Network error');
        return res.json();
      })
      .then((data) => setHealthStatus(`${data.status} (version ${data.version})`))
      .catch(() => setHealthStatus('backend offline'));
  }, []);

  return (
    <div style={{ fontFamily: 'system-ui, -apple-system, sans-serif', padding: '2rem', maxWidth: '800px', margin: '0 auto', color: '#1f2937' }}>
      <header style={{ borderBottom: '1px solid #e5e7eb', paddingBottom: '1rem', marginBottom: '2rem' }}>
        <h1 style={{ margin: 0, color: '#111827', fontSize: '2rem' }}>LocalDoc AI</h1>
        <p style={{ color: '#4b5563', margin: '0.5rem 0 0', fontSize: '1rem' }}>
          Local-first, privacy-preserving AI document agent
        </p>
      </header>
      <main>
        <div style={{ padding: '1.5rem', borderRadius: '8px', background: '#f9fafb', border: '1px solid #e5e7eb' }}>
          <h2 style={{ fontSize: '1.25rem', marginTop: 0, color: '#111827' }}>System Foundation Status</h2>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Frontend:</strong> Operational (React + Vite)
          </p>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Backend Health:</strong> <code>{healthStatus}</code>
          </p>
          <p style={{ margin: '0.5rem 0', fontSize: '0.875rem', color: '#6b7280' }}>
            Phase 1 Foundation ready. RAG pipeline, local embeddings, and model integrations will be attached in subsequent phases.
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;
