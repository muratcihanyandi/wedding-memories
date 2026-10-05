// Album ve admin galerisinin paylastigi bilesenler:
// gorunum anahtari, tile, grid, kisi bolumleri ve lightbox.

import { useEffect } from "react";

import { humanSize, t } from "../texts.js";
import { CheckIcon, ImageIcon } from "./icons.jsx";

// ---------- gorunum anahtari: tum fotograflar / kisilere gore ----------

export function ViewToggle({ value, onChange }) {
  return (
    <div className="view-toggle" role="tablist" aria-label={t.viewAll + " / " + t.viewByPerson}>
      <button
        type="button"
        role="tab"
        aria-selected={value === "all"}
        className={value === "all" ? "active" : ""}
        onClick={() => onChange("all")}
      >
        {t.viewAll}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === "people"}
        className={value === "people" ? "active" : ""}
        onClick={() => onChange("people")}
      >
        {t.viewByPerson}
      </button>
    </div>
  );
}

// ---------- dosyalari yukleyene gore grupla ----------

export function groupByUploader(files) {
  const groups = [];
  const index = new Map();
  for (const file of files) {
    if (!index.has(file.uploader)) {
      const group = [];
      index.set(file.uploader, group);
      groups.push(group);
    }
    index.get(file.uploader).push(file);
  }
  return groups;
}

// ---------- ZIP secenekleri ----------

export function ZipButtons() {
  return (
    <div className="zip-buttons">
      <a className="btn btn-outline btn-sm" href="/api/album/zip?mode=grouped" title={t.zipGroupedHint}>
        📁 {t.zipGrouped}
      </a>
      <a className="btn btn-outline btn-sm" href="/api/album/zip?mode=flat" title={t.zipFlatHint}>
        🗂 {t.zipFlat}
      </a>
    </div>
  );
}

// ---------- galeri tile'i ----------

export function GalleryTile({ file, showUploader, selectMode, selected, onOpen, onToggle }) {
  return (
    <button
      className={`gallery-tile${selected ? " selected" : ""}`}
      onClick={() => (selectMode ? onToggle(file.id) : onOpen(file))}
      aria-label={`${file.original_filename} - ${file.uploader} - ${
        file.media_type === "video" ? "video" : "fotoğraf"
      }`}
    >
      {selectMode && (
        <span className="tile-check" aria-hidden="true">
          {selected && <CheckIcon size={16} />}
        </span>
      )}
      {file.media_type === "video" && <span className="tile-video-badge">▶ Video</span>}
      {showUploader && <span className="tile-uploader">{file.uploader}</span>}
      {file.exists_on_disk ? (
        <img
          src={`/api/album/thumbs/${file.id}`}
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

export function GalleryGrid({ files, showUploader, selectMode, selected, onOpen, onToggle }) {
  return (
    <div className="gallery">
      {files.map((file) => (
        <GalleryTile
          key={file.id}
          file={file}
          showUploader={showUploader}
          selectMode={selectMode}
          selected={selected && selected.has(file.id)}
          onOpen={onOpen}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}

// ---------- kisi bolumleri (kisilere gore gorunum) ----------

export function PersonSection({ files, selectMode, selected, onOpen, onToggle, showHeader }) {
  const uploader = files[0].uploader;
  return (
    <section className="person-section">
      {showHeader && (
        <header className="person-header">
          <span className="user-avatar" aria-hidden="true">
            {uploader.trim().charAt(0).toUpperCase() || "?"}
          </span>
          <h3 className="person-name serif">{uploader}</h3>
          <span className="text-soft">{t.userFiles(files.length)}</span>
        </header>
      )}
      <GalleryGrid
        files={files}
        showUploader={false}
        selectMode={selectMode}
        selected={selected}
        onOpen={onOpen}
        onToggle={onToggle}
      />
    </section>
  );
}

// ---------- lightbox ----------

export function GalleryLightbox({ files, index, onClose, onPrev, onNext, canDelete, onDelete }) {
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
          {file.exists_on_disk && (
            <a className="lightbox-btn" href={`/api/album/files/${file.id}/download`}>
              {t.downloadFile}
            </a>
          )}
          {canDelete && (
            <button className="lightbox-btn danger" onClick={() => onDelete(file)}>
              {t.deleteFile}
            </button>
          )}
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
            src={`/api/album/files/${file.id}/download`}
            controls
            autoPlay
            playsInline
            preload="metadata"
          />
        ) : (
          <img src={`/api/album/files/${file.id}/download`} alt={file.original_filename} />
        )}
        {files.length > 1 && (
          <button className="lightbox-nav" onClick={onNext} aria-label="Sonraki">›</button>
        )}
      </div>
    </div>
  );
}
