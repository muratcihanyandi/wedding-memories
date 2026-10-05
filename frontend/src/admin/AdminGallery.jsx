import { useCallback, useEffect, useMemo, useState } from "react";

import { adminFetch } from "../lib/api.js";
import { t } from "../texts.js";
import ConfirmDialog from "../components/ConfirmDialog.jsx";
import {
  GalleryGrid,
  GalleryLightbox,
  PersonSection,
  ViewToggle,
  ZipButtons,
  groupByUploader,
} from "../components/gallery.jsx";

// /admin/galeri - tum anilarin yonetim gorunumu: hem tek duvar hem kisilere
// gore bolumler; secim/silme + ZIP indirme.

export default function AdminGallery() {
  const [files, setFiles] = useState(null);
  const [error, setError] = useState("");
  const [view, setView] = useState("all"); // all | people
  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [lightbox, setLightbox] = useState(null); // { list, index }
  const [dialog, setDialog] = useState(null); // { type: 'file'|'files', file? }
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await adminFetch("/api/album/files");
      setFiles(data.files);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const groups = useMemo(() => (files ? groupByUploader(files) : []), [files]);

  function toggleSelect(fileId) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  }

  function openLightbox(file, list) {
    const exists = list.filter((f) => f.exists_on_disk);
    const lbIndex = exists.findIndex((f) => f.id === file.id);
    setLightbox({ list: exists, index: lbIndex >= 0 ? lbIndex : 0 });
  }

  async function doDelete() {
    if (!dialog) return;
    setBusy(true);
    try {
      if (dialog.type === "file") {
        await adminFetch(`/api/admin/files/${dialog.file.id}`, { method: "DELETE" });
      } else {
        await adminFetch("/api/admin/files/delete-batch", {
          method: "POST",
          body: JSON.stringify({ ids: Array.from(selected) }),
        });
      }
      setDialog(null);
      setSelected(new Set());
      setSelectMode(false);
      setLightbox(null);
      await load();
    } catch (err) {
      setError(err.message);
      setDialog(null);
    } finally {
      setBusy(false);
    }
  }

  if (error && !files) {
    return <p className="notice notice-error" role="alert">{error}</p>;
  }
  if (!files) {
    return <div className="spinner" role="status" aria-label={t.loading} />;
  }

  return (
    <div className="fade-in">
      <div className="admin-title-row">
        <h2 className="serif">{t.adminGallery}</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {files.length > 0 && <ZipButtons />}
          <button
            className="btn btn-outline btn-sm"
            onClick={() => {
              setSelectMode((v) => !v);
              setSelected(new Set());
            }}
          >
            {selectMode ? t.cancel : t.selectMode}
          </button>
        </div>
      </div>

      {error && <p className="notice notice-error" role="alert" style={{ marginBottom: 12 }}>{error}</p>}

      {selectMode && (
        <div className="album-toolbar" style={{ marginBottom: 14 }}>
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

      {files.length > 0 && !selectMode && (
        <div className="album-toolbar" style={{ marginBottom: 16 }}>
          <ViewToggle value={view} onChange={setView} />
          <span className="text-soft">{t.filesCount(files.length)}</span>
        </div>
      )}

      {files.length === 0 ? (
        <div className="empty-state card">
          <div className="empty-icon" aria-hidden="true">🤍</div>
          <p>{t.albumEmpty}</p>
        </div>
      ) : view === "all" || selectMode ? (
        <GalleryGrid
          files={files}
          showUploader
          selectMode={selectMode}
          selected={selected}
          onToggle={toggleSelect}
          onOpen={(f) => openLightbox(f, files)}
        />
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
          onPrev={() => setLightbox((lb) => ({ ...lb, index: (lb.index - 1 + lb.list.length) % lb.list.length }))}
          onNext={() => setLightbox((lb) => ({ ...lb, index: (lb.index + 1) % lb.list.length }))}
          canDelete
          onDelete={(file) => setDialog({ type: "file", file })}
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
