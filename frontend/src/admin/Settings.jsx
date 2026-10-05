import { useEffect, useState } from "react";

import { adminFetch } from "../lib/api.js";
import { t } from "../texts.js";

const FIELDS = [
  { key: "wedding_title", label: t.settingsWeddingTitle },
  { key: "welcome_text", label: t.settingsWelcomeText, textarea: true },
  { key: "upload_welcome_text", label: t.settingsUploadText, textarea: true },
  { key: "success_text", label: t.settingsSuccessText },
  { key: "public_url", label: t.settingsPublicUrl, hint: t.settingsPublicUrlHint },
];

export default function Settings() {
  const [values, setValues] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cleanupResult, setCleanupResult] = useState("");
  const [qrNonce, setQrNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await adminFetch("/api/admin/settings");
        if (!cancelled) setValues(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const body = {};
      FIELDS.forEach((f) => (body[f.key] = values[f.key] || ""));
      await adminFetch("/api/admin/settings", {
        method: "PUT",
        body: JSON.stringify(body),
      });
      setSaved(true);
      setQrNonce((n) => n + 1); // QR'i yeni PUBLIC_URL ile tazele
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runCleanup() {
    setCleanupResult("");
    try {
      const result = await adminFetch("/api/admin/cleanup", { method: "POST" });
      setCleanupResult(t.cleanupDone(result.removed_records, result.orphan_files));
    } catch (err) {
      setCleanupResult(err.message);
    }
  }

  if (error && !values) {
    return <p className="notice notice-error" role="alert">{error}</p>;
  }
  if (!values) {
    return <div className="spinner" role="status" aria-label={t.loading} />;
  }

  return (
    <div className="fade-in">
      <div className="admin-title-row">
        <h2 className="serif">{t.settingsTitle}</h2>
      </div>

      <section className="card">
        <form className="settings-form" onSubmit={save}>
          {FIELDS.map((field) => (
            <div className="field" key={field.key}>
              <label htmlFor={`set-${field.key}`}>{field.label}</label>
              {field.textarea ? (
                <textarea
                  id={`set-${field.key}`}
                  className="input"
                  value={values[field.key] || ""}
                  onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
                  disabled={busy}
                />
              ) : (
                <input
                  id={`set-${field.key}`}
                  className="input"
                  type={field.key === "public_url" ? "url" : "text"}
                  value={values[field.key] || ""}
                  onChange={(e) => setValues({ ...values, [field.key]: e.target.value })}
                  disabled={busy}
                />
              )}
              {field.hint && <span className="text-soft">{field.hint}</span>}
            </div>
          ))}

          {error && <p className="notice notice-error" role="alert">{error}</p>}
          {saved && <p className="notice notice-success" role="status">{t.settingsSaved}</p>}

          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy ? t.loading : t.settingsSave}
          </button>
        </form>
      </section>

      <h3 className="settings-section-title serif">{t.qrTitle}</h3>
      <section className="card qr-box">
        <img
          src={`/api/admin/qr.png?size=512&v=${qrNonce}`}
          alt="Düğün QR kodu"
          width={240}
          height={240}
        />
        <p className="text-soft center" style={{ maxWidth: "42ch" }}>{t.qrHint}</p>
        <a className="btn btn-outline btn-sm" href={`/api/admin/qr.png?size=2048&v=${qrNonce}`} download>
          {t.qrDownload}
        </a>
      </section>

      <h3 className="settings-section-title serif">{t.maintenanceTitle}</h3>
      <section className="card" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div>
          <button className="btn btn-outline btn-sm" onClick={runCleanup}>
            {t.maintenanceCleanup}
          </button>
          <p className="text-soft" style={{ marginTop: 6 }}>{t.maintenanceCleanupHint}</p>
          {cleanupResult && <p className="notice notice-success" role="status">{cleanupResult}</p>}
        </div>
        <a className="btn btn-outline btn-sm" href="/api/admin/backup.sqlite" style={{ alignSelf: "flex-start" }}>
          {t.maintenanceBackup}
        </a>
      </section>
    </div>
  );
}
