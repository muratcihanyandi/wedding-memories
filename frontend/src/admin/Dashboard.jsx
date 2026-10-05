import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { adminFetch } from "../lib/api.js";
import { humanSize, t } from "../texts.js";

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await adminFetch("/api/admin/stats");
        if (!cancelled) setStats(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return <p className="notice notice-error" role="alert">{error}</p>;
  }
  if (!stats) {
    return <div className="spinner" role="status" aria-label={t.loading} />;
  }

  const storage = stats.storage;
  const storagePercent = Math.min(100, storage.used_percent);

  return (
    <div className="fade-in">
      <div className="admin-title-row">
        <h2 className="serif">{t.adminPanel}</h2>
        <Link to="/admin/users" className="btn btn-outline btn-sm">
          {t.adminGuests} →
        </Link>
      </div>

      <section className="stat-grid" aria-label="İstatistikler">
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">👥</span>
          <span className="stat-value serif">{stats.users}</span>
          <span className="stat-label">{t.statUsers}</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">📸</span>
          <span className="stat-value serif">{stats.photos}</span>
          <span className="stat-label">{t.statPhotos}</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">🎥</span>
          <span className="stat-value serif">{stats.videos}</span>
          <span className="stat-label">{t.statVideos}</span>
        </div>
        <div className="stat-card">
          <span className="stat-icon" aria-hidden="true">💾</span>
          <span className="stat-value serif">{humanSize(stats.total_size)}</span>
          <span className="stat-label">{t.statSize}</span>
        </div>
      </section>

      <section className="card storage-card" aria-label={t.storageTitle}>
        <div className="storage-row">
          <strong>{t.storageTitle}</strong>
          <span>{t.storageUsage(humanSize(storage.total_bytes - storage.free_bytes), humanSize(storage.total_bytes))}</span>
        </div>
        <div className="storage-bar" role="progressbar" aria-valuenow={storage.used_percent} aria-valuemin={0} aria-valuemax={100}>
          <div
            className={`storage-fill${storage.warning ? " full" : ""}`}
            style={{ width: `${storagePercent}%` }}
          />
        </div>
        {storage.warning && (
          <p className="notice notice-warn" style={{ marginTop: 8 }} role="alert">
            {t.storageWarning}
          </p>
        )}
        {!storage.ok && (
          <p className="notice notice-error" style={{ marginTop: 8 }} role="alert">
            {t.storageError} {storage.message}
          </p>
        )}
      </section>
    </div>
  );
}
