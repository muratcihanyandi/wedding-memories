import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { adminFetch } from "../lib/api.js";
import { humanSize, t } from "../texts.js";
import { BrandMark, ImageIcon, VideoIcon } from "../components/icons.jsx";

// /album - tum anilarin sade galerisi: yukleyenler + medya + ZIP.
// Ayarlar/istatistik YOKTUR; yalnizca admin oturumu ile erisilir.

function Lightbox({ files, index, onClose, onPrev, onNext }) {
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
        <span className="lightbox-name">
          {file.original_filename} · {file.uploader}
        </span>
        <div className="lightbox-actions">
          <span className="lightbox-name" style={{ flex: "0 0 auto" }}>{humanSize(file.size)}</span>
          <a className="lightbox-btn" href={`/api/admin/files/${file.id}/download`}>
            {t.downloadFile}
          </a>
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
          <video src={`/api/admin/files/${file.id}/download`} controls autoPlay playsInline preload="metadata" />
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

function AlbumTile({ file, onOpen }) {
  return (
    <button
      className="gallery-tile"
      onClick={() => onOpen(file)}
      aria-label={`${file.original_filename} - ${file.uploader} - ${
        file.media_type === "video" ? "video" : "fotoğraf"
      }`}
    >
      {file.media_type === "video" && <span className="tile-video-badge">▶ Video</span>}
      <span className="tile-uploader">{file.uploader}</span>
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

export default function Album() {
  const navigate = useNavigate();
  const [files, setFiles] = useState(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [lightboxIndex, setLightboxIndex] = useState(-1);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await adminFetch("/api/album/files");
        if (!cancelled) setFiles(data.files);
      } catch (err) {
        if (err.status === 401) {
          navigate("/admin/login", { replace: true });
          return;
        }
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  const uploaders = useMemo(() => {
    if (!files) return [];
    const seen = [];
    for (const f of files) {
      if (!seen.includes(f.uploader)) seen.push(f.uploader);
    }
    return seen;
  }, [files]);

  const visible = useMemo(
    () => (files ? (filter ? files.filter((f) => f.uploader === filter) : files) : []),
    [files, filter]
  );
  const lightboxFiles = visible.filter((f) => f.exists_on_disk);

  if (error) {
    return (
      <main className="admin-shell">
        <p className="notice notice-error" role="alert">{error}</p>
      </main>
    );
  }
  if (!files) {
    return (
      <main className="admin-shell">
        <div className="spinner" role="status" aria-label={t.loading} />
      </main>
    );
  }

  return (
    <main className="admin-shell fade-in">
      <header className="admin-topbar">
        <span className="admin-brand serif">
          <BrandMark size={26} />
          {t.albumTitle}
        </span>
        {files.length > 0 && (
          <a className="btn btn-outline btn-sm" href="/api/album/zip">
            {t.albumZipAll}
          </a>
        )}
      </header>

      {uploaders.length > 1 && (
        <div className="filter-chips" role="group" aria-label="Yükleyene göre filtrele">
          <button
            className={`chip${filter === "" ? " active" : ""}`}
            onClick={() => setFilter("")}
          >
            {t.albumAll} ({files.length})
          </button>
          {uploaders.map((name) => (
            <button
              key={name}
              className={`chip${filter === name ? " active" : ""}`}
              onClick={() => setFilter(name)}
            >
              {name} ({files.filter((f) => f.uploader === name).length})
            </button>
          ))}
        </div>
      )}

      {files.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon" aria-hidden="true">🤍</div>
          <p>{t.albumEmpty}</p>
        </div>
      ) : (
        <div className="gallery">
          {visible.map((file) => (
            <AlbumTile
              key={file.id}
              file={file}
              onOpen={(f) => setLightboxIndex(visible.findIndex((v) => v.id === f.id))}
            />
          ))}
        </div>
      )}

      {lightboxIndex >= 0 && lightboxFiles[lightboxIndex] && (
        <Lightbox
          files={lightboxFiles}
          index={lightboxIndex}
          onClose={() => setLightboxIndex(-1)}
          onPrev={() => setLightboxIndex((i) => (i - 1 + lightboxFiles.length) % lightboxFiles.length)}
          onNext={() => setLightboxIndex((i) => (i + 1) % lightboxFiles.length)}
        />
      )}
    </main>
  );
}
