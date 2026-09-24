import { useState, useEffect } from 'react';
import { CacheStats, ReadyResponse } from '../types/travel';

export const DiagnosticsView = () => {
  const [ready, setReady] = useState<ReadyResponse | null>(null);
  const [cacheStats, setCacheStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [flushMessage, setFlushMessage] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoading(true);
    setError(null);
    try {
      const [readyRes, cacheRes] = await Promise.all([
        fetch('/ready').then((r) => r.json()).catch(() => null),
        fetch('/api/v1/cache/stats').then((r) => r.json()).catch(() => null),
      ]);
      setReady(readyRes);
      setCacheStats(cacheRes);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch diagnostics');
    } finally {
      setLoading(false);
    }
  };

  const handleFlushCache = async () => {
    try {
      const res = await fetch('/api/v1/cache/flush?namespace=travelops', { method: 'DELETE' });
      const data = await res.json();
      setFlushMessage(data.message || 'Cache flushed successfully');
      fetchDiagnostics();
      setTimeout(() => setFlushMessage(null), 3000);
    } catch (err: any) {
      setFlushMessage(`Flush error: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchDiagnostics();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between pb-4 border-b border-slate-800">
        <div>
          <h2 className="text-xl font-bold text-white">Platform Health & Telemetry</h2>
          <p className="text-xs text-slate-400">
            Real-time diagnostics across infrastructure, caching, and observability services
          </p>
        </div>
        <button
          onClick={fetchDiagnostics}
          className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white transition-colors"
        >
          {loading ? 'Refreshing...' : '🔄 Refresh Metrics'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-950/80 border border-red-800 rounded-lg text-xs text-red-300">
          {error}
        </div>
      )}

      {flushMessage && (
        <div className="p-3 bg-emerald-950/80 border border-emerald-800 rounded-lg text-xs text-emerald-300">
          {flushMessage}
        </div>
      )}

      {/* Infrastructure Readiness Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { name: 'PostgreSQL Relational DB', key: 'postgres', desc: 'Domain models & durable sessions' },
          { name: 'Redis Cache & Hot Tier', key: 'redis', desc: 'Short-term memory & flight query cache' },
          { name: 'Qdrant Vector Engine', key: 'qdrant', desc: 'Dense embeddings & policy semantic index' },
          { name: 'Neo4j Knowledge Graph', key: 'neo4j', desc: 'Multi-hop ontology & GraphRAG traversal' },
        ].map((svc) => {
          const status = ready?.services?.[svc.key as keyof typeof ready.services]?.status || 'unknown';
          const isHealthy = status === 'connected' || status === 'ready';

          return (
            <div
              key={svc.key}
              className="bg-slate-900 border border-slate-800 p-4 rounded-xl space-y-2"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-300">{svc.name}</span>
                <span
                  className={`w-2.5 h-2.5 rounded-full ${
                    isHealthy ? 'bg-emerald-400 ring-2 ring-emerald-900' : 'bg-amber-400 ring-2 ring-amber-900'
                  }`}
                />
              </div>
              <div className="text-xs font-mono font-bold text-white capitalize">{status}</div>
              <p className="text-[11px] text-slate-500">{svc.desc}</p>
            </div>
          );
        })}
      </div>

      {/* Cache Telemetry Panel */}
      <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-base font-bold text-white">Distributed Cache Layer</h3>
            <p className="text-xs text-slate-400">
              Active Engine: <span className="font-mono text-sky-400 font-bold">{cacheStats?.backend || 'loading'}</span>
            </p>
          </div>
          <button
            onClick={handleFlushCache}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-red-600/80 hover:bg-red-600 text-white transition-colors"
          >
            Flush Cache
          </button>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-center">
            <div className="text-xs text-slate-400">Hit Rate</div>
            <div className="text-xl font-bold text-emerald-400 mt-1">
              {cacheStats ? `${Math.round(cacheStats.hit_rate * 100)}%` : '0%'}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-center">
            <div className="text-xs text-slate-400">Total Hits</div>
            <div className="text-xl font-bold text-white mt-1">
              {cacheStats?.hits ?? 0}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-center">
            <div className="text-xs text-slate-400">Total Misses</div>
            <div className="text-xl font-bold text-slate-300 mt-1">
              {cacheStats?.misses ?? 0}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-center">
            <div className="text-xs text-slate-400">Active Keys</div>
            <div className="text-xl font-bold text-sky-400 mt-1">
              {cacheStats?.keys_count ?? 0}
            </div>
          </div>

          <div className="bg-slate-950 p-3 rounded-xl border border-slate-800/80 text-center">
            <div className="text-xs text-slate-400">Writes / Deletes</div>
            <div className="text-sm font-bold text-slate-300 mt-2">
              {cacheStats?.writes ?? 0} / {cacheStats?.deletes ?? 0}
            </div>
          </div>
        </div>
      </div>

      {/* External Portals & Dashboards */}
      <div className="bg-slate-900 border border-slate-800 p-6 rounded-2xl space-y-3">
        <h3 className="text-base font-bold text-white">Observability & Developer Portals</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <a
            href="http://localhost:3001"
            target="_blank"
            rel="noreferrer"
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-sky-500 transition-all block group"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-white group-hover:text-sky-400">
                📈 Grafana Dashboard
              </span>
              <span className="text-xs text-slate-500">Port 3001 ↗</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Pre-provisioned TravelOps Overview with RPS, P95 latency, and HITL gauges.
            </p>
          </a>

          <a
            href="http://localhost:9090"
            target="_blank"
            rel="noreferrer"
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-amber-500 transition-all block group"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-white group-hover:text-amber-400">
                🔥 Prometheus Metrics
              </span>
              <span className="text-xs text-slate-500">Port 9090 ↗</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Direct telemetry scraping and PromQL time-series expression console.
            </p>
          </a>

          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="p-4 rounded-xl bg-slate-950 border border-slate-800 hover:border-emerald-500 transition-all block group"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-white group-hover:text-emerald-400">
                📖 OpenAPI 3.1 Swagger
              </span>
              <span className="text-xs text-slate-500">/docs ↗</span>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Interactive REST endpoints across RAG, Graph, ML, Agents, and Caching.
            </p>
          </a>
        </div>
      </div>
    </div>
  );
};
