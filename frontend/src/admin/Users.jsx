import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { adminFetch } from "../lib/api.js";
import { formatDate, humanSize, t } from "../texts.js";

export default function Users() {
  const [users, setUsers] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await adminFetch("/api/admin/users");
        if (!cancelled) setUsers(data.users);
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
  if (!users) {
    return <div className="spinner" role="status" aria-label={t.loading} />;
  }

  return (
    <div className="fade-in">
      <div className="admin-title-row">
        <h2 className="serif">{t.usersTitle}</h2>
        <span className="text-soft">{t.filesCount(users.length)}</span>
      </div>

      {users.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon" aria-hidden="true">🤍</div>
          <p>{t.emptyUsers}</p>
        </div>
      ) : (
        <div className="user-list">
          {users.map((user) => (
            <Link key={user.id} to={`/admin/users/${user.id}`} className="user-row">
              <span className="user-avatar" aria-hidden="true">
                {user.display_name.trim().charAt(0).toUpperCase() || "?"}
              </span>
              <span className="user-row-main">
                <span className="user-row-name">{user.display_name}</span>
                <span className="user-row-meta">
                  {user.file_count > 0
                    ? `${t.userFiles(user.file_count)} · ${humanSize(user.total_size)}`
                    : t.userNoFiles}
                </span>
              </span>
              <span className="user-row-meta">
                {formatDate(user.created_at)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
