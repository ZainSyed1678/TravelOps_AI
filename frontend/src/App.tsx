import React, { useState, useEffect } from 'react';

interface ServiceStatus {
  status: string;
  details?: Record<string, any>;
}

interface ReadyResponse {
  status: string;
  timestamp: string;
  services: {
    postgres: ServiceStatus;
    redis: ServiceStatus;
    qdrant: ServiceStatus;
    neo4j: ServiceStatus;
  };
}

interface VersionResponse {
  name: string;
  version: string;
  environment: string;
  status: string;
}

export default function App() {
  const [version, setVersion] = useState<VersionResponse | null>(null);
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const [verRes, readyRes] = await Promise.all([
        fetch('/version').then((r) => r.json()),
        fetch('/ready').then((r) => r.json()),
      ]);
      setVersion(verRes);
      setReady(readyRes);
    } catch (err: any) {
      setError(err.message || 'Failed to connect to backend API');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem' }}>
      <header style={{ borderBottom: '1px solid #334155', paddingBottom: '1.5rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <h1 style={{ margin: 0, fontSize: '2rem', fontWeight: 700, color: '#38bdf8' }}>
              ✈️ TravelOps AI
            </h1>
            <p style={{ margin: '0.25rem 0 0 0', color: '#94a3b8' }}>
              Production Agentic AI + RAG + GraphRAG + ML Travel Operations Platform
            </p>
          </div>
          <button
            onClick={fetchHealth}
            style={{
              padding: '0.6rem 1.2rem',
              backgroundColor: '#0284c7',
              color: '#ffffff',
              border: 'none',
              borderRadius: '6px',
              fontWeight: 600,
            }}
          >
            {loading ? 'Refreshing...' : 'Refresh Status'}
          </button>
        </div>
      </header>

      {error && (
        <div
          style={{
            backgroundColor: '#451a1a',
            border: '1px solid #dc2626',
            borderRadius: '8px',
            padding: '1rem',
            marginBottom: '1.5rem',
            color: '#fca5a5',
          }}
        >
          <strong>Connection Notice:</strong> {error}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
        <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#e2e8f0', fontSize: '1.1rem' }}>Platform Status</h3>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>System:</strong> {version?.name || 'TravelOps AI'}
          </p>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Version:</strong> <code style={{ color: '#38bdf8' }}>{version?.version || '0.1.0'}</code>
          </p>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Environment:</strong> <code style={{ color: '#a855f7' }}>{version?.environment || 'development'}</code>
          </p>
          <p style={{ margin: '0.5rem 0' }}>
            <strong>Readiness:</strong>{' '}
            <span
              style={{
                color: ready?.status === 'ready' ? '#4ade80' : '#f87171',
                fontWeight: 'bold',
              }}
            >
              {ready?.status?.toUpperCase() || 'CHECKING...'}
            </span>
          </p>
        </div>

        <div style={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 1rem 0', color: '#e2e8f0', fontSize: '1.1rem' }}>Core Data Infrastructure</h3>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            <li style={{ padding: '0.4rem 0', display: 'flex', justifyContent: 'space-between' }}>
              <span>PostgreSQL (Relational Store)</span>
              <span style={{ color: ready?.services?.postgres?.status === 'connected' ? '#4ade80' : '#fbbf24' }}>
                {ready?.services?.postgres?.status || 'uninitialized'}
              </span>
            </li>
            <li style={{ padding: '0.4rem 0', display: 'flex', justifyContent: 'space-between' }}>
              <span>Redis (Cache / Session Store)</span>
              <span style={{ color: ready?.services?.redis?.status === 'connected' ? '#4ade80' : '#fbbf24' }}>
                {ready?.services?.redis?.status || 'uninitialized'}
              </span>
            </li>
            <li style={{ padding: '0.4rem 0', display: 'flex', justifyContent: 'space-between' }}>
              <span>Qdrant (Vector Database)</span>
              <span style={{ color: ready?.services?.qdrant?.status === 'connected' ? '#4ade80' : '#fbbf24' }}>
                {ready?.services?.qdrant?.status || 'uninitialized'}
              </span>
            </li>
            <li style={{ padding: '0.4rem 0', display: 'flex', justifyContent: 'space-between' }}>
              <span>Neo4j (Knowledge Graph)</span>
              <span style={{ color: ready?.services?.neo4j?.status === 'connected' ? '#4ade80' : '#fbbf24' }}>
                {ready?.services?.neo4j?.status || 'uninitialized'}
              </span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}
