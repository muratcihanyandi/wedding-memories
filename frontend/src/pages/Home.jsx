import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch } from "../lib/api.js";
import { t } from "../texts.js";
import { HeartIcon } from "../components/icons.jsx";

export default function Home() {
  const navigate = useNavigate();
  const [config, setConfig] = useState(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [nameExists, setNameExists] = useState(null); // girilen isim

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await apiFetch("/api/me");
        if (!cancelled && me && me.user) {
          navigate("/upload", { replace: true });
          return;
        }
      } catch {
        /* oturum yok - normal akis */
      }
      try {
        const cfg = await apiFetch("/api/config");
        if (!cancelled) setConfig(cfg);
      } catch {
        /* config yoksa varsayilan metinler gosterilir */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  async function submitName(ifExists) {
    const trimmed = name.trim();
    if (!trimmed) {
      setError(t.namePrompt);
      return;
    }
    setBusy(true);
    setError("");
    try {
      await apiFetch("/api/session", {
        method: "POST",
        body: JSON.stringify({ name: trimmed, if_exists: ifExists || undefined }),
      });
      navigate("/upload");
    } catch (err) {
      if (err.status === 409) {
        setNameExists(trimmed);
      } else {
        setError(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  const weddingTitle = config?.wedding_title || "Wedding Memories";
  const welcomeText = config?.welcome_text || "Bu güzel günün anılarını bizimle paylaşın. 🤍";

  if (nameExists) {
    return (
      <main className="public-shell">
        <div className="overlay" style={{ position: "static", padding: 0, background: "transparent", backdropFilter: "none" }}>
          <div className="dialog" role="dialog" aria-modal="true" aria-labelledby="exists-title">
            <h2 id="exists-title">{t.nameExistsTitle}</h2>
            <p>{t.nameExistsText(nameExists)}</p>
            <div className="dialog-actions">
              <button className="btn btn-primary" onClick={() => submitName("reuse")} disabled={busy}>
                {t.samePersonBtn}
              </button>
              <button className="btn btn-outline" onClick={() => submitName("new")} disabled={busy}>
                {t.differentPersonBtn}
              </button>
              <button className="btn btn-ghost" onClick={() => setNameExists(null)}>
                {t.goBack}
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="public-shell">
      <header className="public-hero">
        <span className="heart" aria-hidden="true">
          <HeartIcon size={44} />
        </span>
        <span className="eyebrow">Wedding Memories</span>
        <h1 className="serif">{weddingTitle}</h1>
        <p className="subtitle">{welcomeText}</p>
      </header>

      <section className="card" style={{ padding: "26px 22px" }}>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submitName();
          }}
        >
          <div className="field">
            <label htmlFor="name">{t.namePrompt}</label>
            <input
              id="name"
              className="input"
              type="text"
              inputMode="text"
              autoComplete="given-name"
              maxLength={64}
              placeholder={t.namePlaceholder}
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={busy}
              autoFocus
            />
          </div>
          {error && (
            <p className="notice notice-error" style={{ marginTop: 12 }} role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: 16 }} disabled={busy}>
            {busy ? t.loading : t.continueBtn}
          </button>
        </form>
      </section>

      <p className="text-soft center" style={{ marginTop: 4 }}>
        Fotoğraf ve videoların yalnızca çift tarafından görüntülenir. 🤍
      </p>
    </main>
  );
}
