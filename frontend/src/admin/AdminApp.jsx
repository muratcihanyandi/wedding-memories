import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { adminFetch, clearCsrfToken } from "../lib/api.js";
import { t } from "../texts.js";
import { BrandMark } from "../components/icons.jsx";

export default function AdminApp() {
  const navigate = useNavigate();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await adminFetch("/api/admin/me");
        if (!cancelled) {
          setChecked(true);
        }
      } catch {
        if (!cancelled) navigate("/admin/login", { replace: true });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  async function logout() {
    try {
      await adminFetch("/api/admin/logout", { method: "POST" });
    } catch {
      /* oturum zaten yok sayilir */
    }
    clearCsrfToken();
    navigate("/admin/login", { replace: true });
  }

  if (!checked) {
    return (
      <main className="admin-shell">
        <div className="spinner" role="status" aria-label={t.loading} />
      </main>
    );
  }

  return (
    <main className="admin-shell">
      <header className="admin-topbar">
        <NavLink to="/admin" className="admin-brand serif">
          <BrandMark size={26} />
          {t.appTitle}
        </NavLink>
        <nav className="admin-nav" aria-label="Yönetim menüsü">
          <NavLink to="/admin" end className={({ isActive }) => (isActive ? "active" : "")}>
            {t.adminPanel}
          </NavLink>
          <NavLink to="/admin/users" className={({ isActive }) => (isActive ? "active" : "")}>
            {t.adminGuests}
          </NavLink>
          <NavLink to="/admin/settings" className={({ isActive }) => (isActive ? "active" : "")}>
            {t.adminSettings}
          </NavLink>
          <button className="btn btn-ghost btn-sm" onClick={logout}>
            {t.adminLogout}
          </button>
        </nav>
      </header>
      <Outlet />
    </main>
  );
}
