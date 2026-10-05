import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, setCsrfToken } from "../lib/api.js";
import { t } from "../texts.js";
import { BrandMark } from "../components/icons.jsx";

export default function AdminLogin() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await apiFetch("/api/admin/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setCsrfToken(data.csrf_token);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="public-shell" style={{ justifyContent: "center" }}>
      <div className="public-hero" style={{ paddingBottom: 0 }}>
        <span className="heart" aria-hidden="true" style={{ color: "var(--gold)" }}>
          <BrandMark size={42} />
        </span>
        <h1 className="serif">{t.adminLoginTitle}</h1>
      </div>

      <section className="card" style={{ padding: "26px 22px" }}>
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="admin-user">{t.adminUsername}</label>
            <input
              id="admin-user"
              className="input"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={busy}
              autoFocus
            />
          </div>
          <div className="field" style={{ marginTop: 14 }}>
            <label htmlFor="admin-pass">{t.adminPassword}</label>
            <input
              id="admin-pass"
              className="input"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={busy}
            />
          </div>
          {error && (
            <p className="notice notice-error" style={{ marginTop: 12 }} role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn btn-primary btn-block" style={{ marginTop: 18 }} disabled={busy}>
            {busy ? t.loading : t.adminLoginBtn}
          </button>
        </form>
      </section>
    </main>
  );
}
