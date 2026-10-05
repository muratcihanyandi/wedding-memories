import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch } from "../lib/api.js";
import { t } from "../texts.js";
import { CheckIcon } from "../components/icons.jsx";

export default function Success() {
  const navigate = useNavigate();
  const [name, setName] = useState(null);
  const [config, setConfig] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await apiFetch("/api/me");
        if (cancelled) return;
        setName(me.user.display_name);
      } catch {
        navigate("/", { replace: true });
        return;
      }
      try {
        const cfg = await apiFetch("/api/config");
        if (!cancelled) setConfig(cfg);
      } catch {
        /* varsayilan metin */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const successText = config?.success_text || "Anıların başarıyla kaydedildi! 🤍";

  return (
    <main className="public-shell">
      <div className="success-wrap">
        <div className="success-ring" aria-hidden="true">
          <CheckIcon size={44} />
        </div>
        <h1 className="serif" style={{ fontSize: "2rem" }}>
          {successText}
        </h1>
        {name && <p className="subtitle">{t.successThanks(name)}</p>}
        <button
          className="btn btn-primary"
          style={{ marginTop: 18, minWidth: 240 }}
          onClick={() => navigate("/upload")}
        >
          {t.addMoreLink}
        </button>
        <button className="btn btn-ghost" onClick={() => navigate("/")}>
          {t.goBack}
        </button>
      </div>
    </main>
  );
}
