import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { adminFetch } from "../lib/api.js";
import { humanSize, t } from "../texts.js";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import { CheckIcon, ImageIcon, VideoIcon } from "../components/icons.jsx";

function Tile({ file, selected, selectMode, onOpen, onToggle }) {
  return (
    <button
      className={`gallery-tile${selected ? " selected" : ""}`}
      onClick={() => (selectMode ? onToggle(file.id) : onOpen(file))}
      aria-label={`${file.original_filename} - ${file.media_type === "video" ? "video" : "fotoğraf"}`}
    >
      {selectMode && (
        <span className="tile-check" aria-hidden="true">
          {selected && <CheckIcon size={16} />}
        </span>
      )}
      {file.media_type === "video" && <span className="tile-video-badge">▶ Video</span>}
      {file.exists_on_disk ? (
        <img
          src={`/api/admin/thumbs/${file.id}`}
          alt={file.original_filename}
          loading="lazy"
          onError={(e) => {
            e.currentTarget.replaceWith(
              Object.assign(document.createElement("div"), {
                className: "tile-missing",
                textContent: file.media_type === "video" ? "▶ Video" : "Fotoğraf",
              })
            );
          }}
        />
      ) : (
        <div className="tile-missing">
          <ImageIcon size={18} />
          {t.missingFile}
        </div>
      )}
    </button>
  );
}

function Lightbox({ files, index, onClose, onPrev, onNext, onDelete }) {
  const file = files[index];

  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") onPrev();
      if (e.key === "ArrowRight") onNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose, onPrev, onNext]);

  return (
    <div className="lightbox" role="dialog" aria-modal="true" aria-label={file.original_filename}>
      <div className="lightbox-top">
        <span className="lightbox-name">{file.original_filename}</span>
        <div className="lightbox-actions">
          <span className="lightbox-name" style={{ flex: "0 0 auto" }}>{humanSize(file.size)}</span>
          {file.exists_on_disk && (
            <a className="lightbox-btn" href={`/api/admin/files/${file.id}/download`}>
              {t.downloadFile}
            </a>
          )}
          <button className="lightbox-btn danger" onClick={() => onDelete(file)}>
            {t.deleteFile}
          </button>
          <button className="lightbox-btn" onClick={onClose}>
            {t.close}
          </button>
        </div>
      </div>
      <div className="lightbox-body">
        {files.length > 1 && (
          <button className="lightbox-nav" onClick={onPrev} aria-label="Önceki">‹</button>
        )}
        {file.media_type === "video" ? (
          <video
            src={`/api/admin/files/${file.id}/download`}
            controls
            autoPlay
            playsInline
            preload="metadata"
          />
        ) : (
          <img src={`/api/admin/files/${file.id}/download`} alt={file.original_filename} />
        )}
        {files.length > 1 && (
          <button className="lightbox-nav" onClick={onNext} aria-label="Sonraki">›</button>
        )}
      </div>
    </div>
  );
}

export default function UserDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [error, setError] = useState("");
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [lightboxIndex, setLightboxIndex] = useState(-1);
  const [dialog, setDialog] = useState(null); // {type: 'user'|'files'|'file', fileIds, file}
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await adminFetch(`/api/admin/users/${id}`);
      setUser(data);
    } catch (err) {
      setError(err.message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  function toggleSelect(fileId) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  }

  function openLightbox(file) {
    setLightboxIndex(user.files.findIndex((f) => f.id === file.id));
  }

  async function doDelete() {
    if (!dialog) return;
    setBusy(true);
    try {
      if (dialog.type === "user") {
        await adminFetch(`/api/admin/users/${user.id}`, { method: "DELETE" });
        navigate("/admin/users", { replace: true });
        return;
      }
      if (dialog.type === "file") {
        await adminFetch(`/api/admin/files/${dialog.file.id}`, { method: "DELETE" });
      } else if (dialog.type === "files") {
        await adminFetch("/api/admin/files/delete-batch", {
          method: "POST",
          body: JSON.stringify({ ids: Array.from(selected) }),
        });
      }
      setDialog(null);
      setSelected(new Set());
      setSelectMode(false);
      setLightboxIndex(-1);
      await load();
    } catch (err) {
      setError(err.message);
      setDialog(null);
    } finally {
      setBusy(false);
    }
  }

  if (error) {
    return <p className="notice notice-error" role="alert">{error}</p>;
  }
  if (!user) {
    return <div className="spinner" role="status" aria-label={t.loading} />;
  }

  const totalSize = user.files.reduce((sum, f) => sum + f.size, 0);
  const lightboxFiles = user.files.filter((f) => f.exists_on_disk);
  const lightboxCurrent = lightboxIndex >= 0 ? lightboxFiles[lightboxIndex] : null;

  return (
    <div className="fade-in">
      <div className="admin-title-row">
        <div>
          <h2 className="serif" style={{ marginBottom: 2 }}>{user.display_name}</h2>
          <span className="text-soft">
            {t.userFiles(user.files.length)} · {humanSize(totalSize)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {user.files.length > 0 && (
            <a
              className="btn btn-outline btn-sm"
              href={`/api/admin/users/${user.id}/zip`}
            >
              {t.downloadAllZip}
            </a>
          )}
          <button
            className="btn btn-outline btn-sm"
            onClick={() => {
              setSelectMode((v) => !v);
              setSelected(new Set());
            }}
          >
            {selectMode ? t.cancel : t.selectMode}
          </button>
          <button
            className="btn btn-danger btn-sm"
            onClick={() => setDialog({ type: "user" })}
          >
            {t.deleteUser}
          </button>
        </div>
      </div>

      {selectMode && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 10,
            marginBottom: 14,
            flexWrap: "wrap",
          }}
        >
          <span className="text-soft">{selected.size} seçili</span>
          <button
            className="btn btn-danger btn-sm"
            disabled={selected.size === 0}
            onClick={() => setDialog({ type: "files" })}
          >
            {t.deleteSelected(selected.size)}
          </button>
        </div>
      )}

      {user.files.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon" aria-hidden="true">🤍</div>
          <p>{t.userNoFiles}</p>
        </div>
      ) : (
        <div className="gallery">
          {user.files.map((file) => (
            <Tile
              key={file.id}
              file={file}
              selected={selected.has(file.id)}
              selectMode={selectMode}
              onOpen={openLightbox}
              onToggle={toggleSelect}
            />
          ))}
        </div>
      )}

      {lightboxCurrent && (
        <Lightbox
          files={lightboxFiles}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(-1)}
          onPrev={() => setLightboxIndex((i) => (i - 1 + lightboxFiles.length) % lightboxFiles.length)}
          onNext={() => setLightboxIndex((i) => (i + 1) % lightboxFiles.length)}
          onDelete={(file) => setDialog({ type: "file", file })}
        />
      )}

      {dialog?.type === "user" && (
        <ConfirmDialog
          title={t.deleteUser}
          message={t.confirmDeleteUser(user.display_name)}
          confirmLabel={t.deleteUser}
          onConfirm={doDelete}
          onCancel={() => setDialog(null)}
          busy={busy}
        />
      )}
      {dialog?.type === "files" && (
        <ConfirmDialog
          title={t.deleteSelected(selected.size)}
          message={t.confirmDeleteFiles(selected.size)}
          confirmLabel={t.delete}
          onConfirm={doDelete}
          onCancel={() => setDialog(null)}
          busy={busy}
        />
      )}
      {dialog?.type === "file" && (
        <ConfirmDialog
          title={t.deleteFile}
          message={t.confirmDeleteFile}
          confirmLabel={t.deleteFile}
          onConfirm={doDelete}
          onCancel={() => setDialog(null)}
          busy={busy}
        />
      )}
    </div>
  );
}
