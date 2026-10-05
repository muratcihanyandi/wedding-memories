import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, uploadFile } from "../lib/api.js";
import { humanSize, t } from "../texts.js";
import { CameraIcon, HeartIcon, ImageIcon, VideoIcon } from "../components/icons.jsx";
import PickerModal from "../components/PickerModal.jsx";

const MAX_CONCURRENT = 2; // Pi ve WiFi'yi yormadan iki dosya ayni anda

let fileKeySeq = 0;

function makeItem(file) {
  const isImage = file.type.startsWith("image/");
  return {
    key: `f${++fileKeySeq}`,
    file,
    name: file.name,
    size: file.size,
    isImage,
    previewUrl: isImage ? URL.createObjectURL(file) : null,
    progress: 0,
    status: "waiting", // waiting | uploading | done | error
    error: null,
  };
}

function FileRow({ item, onRetry, onRemove }) {
  const [previewFailed, setPreviewFailed] = useState(false);
  const busy = item.status === "uploading" || item.status === "waiting";

  return (
    <li className="file-row">
      {item.isImage && !previewFailed ? (
        <img
          className="file-thumb"
          src={item.previewUrl}
          alt=""
          onError={() => setPreviewFailed(true)}
        />
      ) : (
        <span className="file-thumb-icon" aria-hidden="true">
          {item.isImage ? <ImageIcon size={26} /> : <VideoIcon size={26} />}
        </span>
      )}

      <div className="file-info">
        <p className="file-name" title={item.name}>
          {item.name}
        </p>
        <div className="file-meta">
          <span>{humanSize(item.size)}</span>
          {item.status === "waiting" && <span className="text-soft">{t.waiting}</span>}
          {item.status === "uploading" && <span>{t.uploading} %{item.progress}</span>}
          {item.status === "done" && <span className="status-done">{t.uploaded}</span>}
          {item.status === "error" && <span className="status-error">{item.error}</span>}
        </div>
        {item.status === "uploading" && (
          <div className="progress" role="progressbar" aria-valuenow={item.progress} aria-valuemin={0} aria-valuemax={100}>
            <div className="progress-fill" style={{ width: `${item.progress}%` }} />
          </div>
        )}
        {item.status === "done" && (
          <div className="progress">
            <div className="progress-fill" style={{ width: "100%" }} />
          </div>
        )}
      </div>

      <div className="file-actions">
        {item.status === "error" && (
          <button className="btn btn-outline btn-sm" onClick={() => onRetry(item.key)}>
            {t.retryBtn}
          </button>
        )}
        {!busy && (
          <button className="btn btn-ghost btn-sm" onClick={() => onRemove(item.key)}>
            {t.removeBtn}
          </button>
        )}
      </div>
    </li>
  );
}

export default function Upload() {
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [config, setConfig] = useState(null);
  const [items, setItems] = useState([]);
  const [pickerOpen, setPickerOpen] = useState(false);

  const itemsRef = useRef(items);
  const inflight = useRef(new Set());

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  // Oturum kontrolu - oturumsuz giris yapilamaz
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await apiFetch("/api/me");
        if (cancelled) return;
        setUser(me.user);
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

  // Sayfadan cikis uyrisi (spec #27)
  useEffect(() => {
    const handler = (event) => {
      const active = itemsRef.current.some((i) => i.status === "uploading" || i.status === "waiting");
      if (active) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  // Tum dosyalar bitti ve hata yoksa basari ekranina gec
  useEffect(() => {
    if (items.length === 0) return;
    const active = items.some((i) => i.status === "uploading" || i.status === "waiting");
    if (active) return;
    const hasError = items.some((i) => i.status === "error");
    if (!hasError) {
      const timer = setTimeout(() => navigate("/success"), 600);
      return () => clearTimeout(timer);
    }
  }, [items, navigate]);

  const updateItem = useCallback((key, patch) => {
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  }, []);

  const processQueue = useCallback(async () => {
    // Inflight set'i senkron gunceller; itemsRef'e bakarak siradaki
    // bekleyen dosyayi sec. Ayni dosyayi iki isciye vermeyi engeller.
    for (;;) {
      const next = itemsRef.current.find(
        (i) => i.status === "waiting" && !inflight.current.has(i.key)
      );
      if (!next) break;
      inflight.current.add(next.key);
      updateItem(next.key, { status: "uploading", progress: 0, error: null });
      try {
        await uploadFile(next.file, (pct) => updateItem(next.key, { progress: pct }));
        updateItem(next.key, { status: "done", progress: 100 });
      } catch (err) {
        if (err.status === 401) {
          navigate("/", { replace: true });
          return;
        }
        updateItem(next.key, { status: "error", error: err.message });
      } finally {
        inflight.current.delete(next.key);
      }
    }
  }, [navigate, updateItem]);

  // Yeni eklenen "waiting" dosyalar varken kuyrugu yeniden tetikle
  useEffect(() => {
    const hasWaiting = items.some((i) => i.status === "waiting" && !inflight.current.has(i.key));
    if (hasWaiting) {
      processQueue();
    }
  }, [items, processQueue]);

  function addFiles(fileList) {
    const accepted = Array.from(fileList).map(makeItem);
    if (accepted.length === 0) return;
    setItems((prev) => [...prev, ...accepted]);
  }

  function retry(key) {
    updateItem(key, { status: "waiting", progress: 0, error: null });
    processQueue();
  }

  function remove(key) {
    setItems((prev) => {
      const target = prev.find((i) => i.key === key);
      if (target && target.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter((i) => i.key !== key);
    });
  }

  useEffect(() => {
    return () => {
      itemsRef.current.forEach((i) => i.previewUrl && URL.revokeObjectURL(i.previewUrl));
    };
  }, []);

  if (!user) {
    return (
      <main className="public-shell">
        <div className="spinner" role="status" aria-label={t.loading} />
      </main>
    );
  }

  const activeCount = items.filter((i) => i.status === "uploading" || i.status === "waiting").length;
  const welcome = config?.upload_welcome_text || "Bu geceden kalan güzel anılarını bizimle paylaş.";

  return (
    <main className="public-shell">
      <header className="public-hero" style={{ paddingBottom: 0 }}>
        <span className="heart" aria-hidden="true">
          <HeartIcon size={40} />
        </span>
        <h1 className="serif">{t.hello(user.display_name)}</h1>
        <p className="subtitle">{welcome}</p>
      </header>

      <section>
        <button
          className="big-add"
          onClick={() => setPickerOpen(true)}
          aria-labelledby="add-label"
        >
          <CameraIcon size={34} />
          <span id="add-label">{items.length === 0 ? t.addFilesBtn : t.addMoreBtn}</span>
        </button>
        <p className="text-soft center" style={{ marginTop: 10 }}>
          Fotoğraflar ve videolar aynı anda seçilebilir.
        </p>
        {pickerOpen && (
          <PickerModal
            onConfirm={(files) => {
              setPickerOpen(false);
              addFiles(files);
            }}
            onClose={() => setPickerOpen(false)}
          />
        )}
      </section>

      {activeCount > 0 && (
        <p className="notice notice-warn" role="status">
          {t.uploadWarning}
        </p>
      )}

      {items.length > 0 && (
        <section aria-label="Yükleme listesi">
          <ul className="upload-list" style={{ listStyle: "none" }}>
            {items.map((item) => (
              <FileRow key={item.key} item={item} onRetry={retry} onRemove={remove} />
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
