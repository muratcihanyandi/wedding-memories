import { useEffect, useMemo, useState } from "react";

import { apiFetch } from "../lib/api.js";
import { t } from "../texts.js";
import { BrandMark } from "../components/icons.jsx";
import {
  GalleryGrid,
  GalleryLightbox,
  PersonSection,
  ViewToggle,
  ZipButtons,
  groupByUploader,
} from "../components/gallery.jsx";

// /album - HERKESE ACIK tum anilar galerisi (giris gerektirmez).
// Iki gorunum: tum fotograflar tek duvar / kisilere gore bolumler.

export default function Album() {
  const [files, setFiles] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("all"); // all | people
  const [lightbox, setLightbox] = useState(null); // { list, index }

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiFetch("/api/album/files");
        if (!cancelled) setFiles(data.files);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const groups = useMemo(() => (files ? groupByUploader(files) : []), [files]);

  function openLightbox(file, list) {
    const index = list.findIndex((f) => f.id === file.id);
    const exists = list.filter((f) => f.exists_on_disk);
    // Lightbox yalnizca diskte olan dosyalar arasinda gezinir
    const lbIndex = exists.findIndex((f) => f.id === file.id);
    setLightbox({ list: exists, index: lbIndex >= 0 ? lbIndex : index });
  }

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
        {files.length > 0 && <ZipButtons />}
      </header>

      {files.length > 0 && (
        <div className="album-toolbar">
          <ViewToggle value={view} onChange={setView} />
          <span className="text-soft">{t.filesCount(files.length)}</span>
        </div>
      )}

      {files.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon" aria-hidden="true">🤍</div>
          <p>{t.albumEmpty}</p>
        </div>
      ) : view === "all" ? (
        <GalleryGrid files={files} showUploader onOpen={(f) => openLightbox(f, files)} />
      ) : (
        groups.map((group) => (
          <PersonSection
            key={group[0].uploader}
            files={group}
            showHeader
            onOpen={(f) => openLightbox(f, group)}
          />
        ))
      )}

      {lightbox && (
        <GalleryLightbox
          files={lightbox.list}
          index={lightbox.index}
          onClose={() => setLightbox(null)}
          onPrev={() =>
            setLightbox((lb) => ({ ...lb, index: (lb.index - 1 + lb.list.length) % lb.list.length }))
          }
          onNext={() => setLightbox((lb) => ({ ...lb, index: (lb.index + 1) % lb.list.length }))}
        />
      )}
    </main>
  );
}
