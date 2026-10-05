import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiFetch, uploadFile } from "../lib/api.js";
import { humanSize, t } from "../texts.js";
import { CameraIcon, HeartIcon, ImageIcon, VideoIcon } from "../components/icons.jsx";

// Yukleme plani: fotograflar ONCE (en fazla 2 es zamanli - kucuk ve
// hizlidirlar), videolar fotograf kuyrugu bittikten sonra TEK TEK
// (buyuklerdir; Wi-Fi ve Raspberry Pi'yi yormamak icin). Videolar
// eklendikleri sirayla yuklenir.
const IMAGE_CONCURRENCY = 2;
const VIDEO_CONCURRENCY = 1;

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

  const itemsRef = useRef(items);
  // key -> isVideo (aktif yuklemelerin turu; es zamanlilik siniri icin)
  const inflight = useRef(new Map());
  const inputRef = useRef(null);

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

  const anyActive = items.some((i) => i.status === "uploading" || i.status === "waiting");

  // Uzun video yuklemelerinde telefon ekraninin kapanmasini engelle -
  // ekran kapaninca tarayici baglantiyi kesebiliyor ("baglanti hatasi"
  // genellikle bundan kaynaklanir). Yukleme bitince kilit kendiliginden
  // birakilir.
  useEffect(() => {
    if (!anyActive || !("wakeLock" in navigator)) return;
    let lock = null;
    let released = false;
    navigator.wakeLock
      .request("screen")
      .then((l) => {
        if (released) l.release().catch(() => {});
        else lock = l;
      })
      .catch(() => {
        /* desteklemeyen tarayicilar icin sessiz gec */
      });
    return () => {
      released = true;
      if (lock) lock.release().catch(() => {});
    };
  }, [anyActive]);

  // Tum dosyalar bitti ve hata yoksa basari ekranina gec
  useEffect(() => {
    if (items.length === 0) return;
    if (anyActive) return;
    const hasError = items.some((i) => i.status === "error");
    if (!hasError) {
      const timer = setTimeout(() => navigate("/success"), 600);
      return () => clearTimeout(timer);
    }
  }, [items, anyActive, navigate]);

  const updateItem = useCallback((key, patch) => {
    setItems((prev) => prev.map((i) => (i.key === key ? { ...i, ...patch } : i)));
  }, []);

  function activeOfType(isVideo) {
    let count = 0;
    for (const value of inflight.current.values()) {
      if (value === isVideo) count += 1;
    }
    return count;
  }

  async function beginUpload(item) {
    inflight.current.set(item.key, !item.isImage);
    updateItem(item.key, { status: "uploading", progress: 0, error: null });
    try {
      await uploadFile(item.file, (pct) => updateItem(item.key, { progress: pct }));
      updateItem(item.key, { status: "done", progress: 100 });
    } catch (err) {
      if (err.status === 401) {
        navigate("/", { replace: true });
        return;
      }
      updateItem(item.key, { status: "error", error: err.message });
    } finally {
      inflight.current.delete(item.key);
      startEligible(); // bir slot bosaldi - siradaki dosyayi baslat
    }
  }

  // Siralayici: once bekleyen FOTOGRAFLAR (2 es zamanliye kadar),
  // fotograflar bittiyse bekleyen VIDEOLAR (1 tane, ekleme sirasinda).
  function startEligible() {
    for (;;) {
      const waiting = itemsRef.current.filter(
        (i) => i.status === "waiting" && !inflight.current.has(i.key)
      );
      if (waiting.length === 0) return;

      const nextImage = waiting.find((i) => i.isImage);
      if (nextImage) {
        if (activeOfType(false) >= IMAGE_CONCURRENCY) return;
        beginUpload(nextImage);
      } else {
        // yalnizca videolar kaldi: tum fotograflar TAMAMEN bitsin,
        // sonra videolar tek tek, ekleme sirasiyla
        if (activeOfType(false) > 0) return;
        if (activeOfType(true) >= VIDEO_CONCURRENCY) return;
        beginUpload(waiting[0]);
      }
    }
  }

  // Yeni eklenen veya tekrar denenmis "waiting" dosya varsa siralayiciyi tetikle
  useEffect(() => {
    const hasWaiting = items.some(
      (i) => i.status === "waiting" && !inflight.current.has(i.key)
    );
    if (hasWaiting) {
      startEligible();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  function addFiles(fileList) {
    const accepted = Array.from(fileList).map(makeItem);
    if (accepted.length === 0) return;
    setItems((prev) => [...prev, ...accepted]);
    if (inputRef.current) inputRef.current.value = "";
  }

  function retry(key) {
    updateItem(key, { status: "waiting", progress: 0, error: null });
    startEligible();
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
        <input
          ref={inputRef}
          id="file-input"
          type="file"
          accept="image/*,video/*"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
        <button
          className="big-add"
          onClick={() => inputRef.current && inputRef.current.click()}
          aria-labelledby="add-label"
        >
          <CameraIcon size={34} />
          <span id="add-label">{items.length === 0 ? t.addFilesBtn : t.addMoreBtn}</span>
        </button>
      </section>

      {anyActive && (
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
