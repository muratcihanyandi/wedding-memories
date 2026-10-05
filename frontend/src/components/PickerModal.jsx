// Site tasarimina uygun dosya secme penceresi.
//
// Tarayici guvenligi geregi web sayfasi cihazin galerisini dogrudan
// tarayamaz; "Galeriden Sec" sistemi native seciciyi acar (telefonda
// zaten guzel bir foto galeri arayuzudur). Secilen dosyalar BU modalda
// site tasarimiyla uyumlu ızgarada listelenir; tekil isaretleme /
// kaldirma yapilip toplu yuklenir.

import { useEffect, useRef, useState } from "react";

import { humanSize, t } from "../texts.js";
import { CameraIcon, CheckIcon, ImageIcon, VideoIcon } from "./icons.jsx";

let pickerKeySeq = 0;

export default function PickerModal({ onConfirm, onClose }) {
  const [picked, setPicked] = useState([]); // {key, file, url, isImage, checked}
  const galleryInput = useRef(null);
  const cameraInput = useRef(null);

  // Kapanista olusturulan object URL'leri temizle
  useEffect(() => {
    return () => {
      setPicked((current) => {
        current.forEach((p) => p.url && URL.revokeObjectURL(p.url));
        return current;
      });
    };
  }, []);

  function addFiles(fileList) {
    const fresh = Array.from(fileList).map((file) => ({
      key: `p${++pickerKeySeq}`,
      file,
      isImage: file.type.startsWith("image/"),
      url: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
      checked: true,
    }));
    if (fresh.length > 0) {
      setPicked((prev) => [...prev, ...fresh]);
    }
    if (galleryInput.current) galleryInput.current.value = "";
    if (cameraInput.current) cameraInput.current.value = "";
  }

  function toggleCheck(key) {
    setPicked((prev) => prev.map((p) => (p.key === key ? { ...p, checked: !p.checked } : p)));
  }

  function removeItem(key) {
    setPicked((prev) => {
      const target = prev.find((p) => p.key === key);
      if (target && target.url) URL.revokeObjectURL(target.url);
      return prev.filter((p) => p.key !== key);
    });
  }

  const checkedFiles = picked.filter((p) => p.checked);
  const totalSize = checkedFiles.reduce((sum, p) => sum + p.file.size, 0);

  return (
    <div
      className="overlay"
      role="presentation"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="dialog picker-dialog" role="dialog" aria-modal="true" aria-labelledby="picker-title">
        <h2 id="picker-title" className="serif">{t.pickerTitle}</h2>
        <p className="text-soft" style={{ marginBottom: 12 }}>{t.pickerHint}</p>

        <input
          ref={galleryInput}
          type="file"
          accept="image/*,video/*"
          multiple
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />
        <input
          ref={cameraInput}
          type="file"
          accept="image/*,video/*"
          capture="environment"
          hidden
          onChange={(e) => addFiles(e.target.files)}
        />

        {picked.length === 0 ? (
          <div className="picker-sources">
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={() => galleryInput.current && galleryInput.current.click()}
            >
              <ImageIcon size={22} /> {t.pickerGallery}
            </button>
            <button
              type="button"
              className="btn btn-outline btn-block"
              onClick={() => cameraInput.current && cameraInput.current.click()}
            >
              <CameraIcon size={22} /> {t.pickerCamera}
            </button>
          </div>
        ) : (
          <>
            <ul className="picker-grid">
              {picked.map((p) => (
                <li key={p.key} className={`picker-tile${p.checked ? " selected" : ""}`}>
                  <button
                    type="button"
                    className="picker-preview"
                    onClick={() => toggleCheck(p.key)}
                    aria-label={`${p.file.name} ${p.checked ? "- seçimden çıkar" : "- seç"}`}
                    aria-pressed={p.checked}
                  >
                    {p.isImage ? (
                      <img src={p.url} alt="" />
                    ) : (
                      <span className="picker-video" aria-hidden="true">
                        <VideoIcon size={28} />
                      </span>
                    )}
                    <span className="tile-check" aria-hidden="true">
                      {p.checked && <CheckIcon size={14} />}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="picker-remove"
                    onClick={() => removeItem(p.key)}
                    aria-label={t.removeBtn}
                  >
                    ×
                  </button>
                  <span className="picker-name" title={p.file.name}>
                    {p.file.name}
                  </span>
                </li>
              ))}
            </ul>

            <div className="picker-actions">
              <span className="text-soft">
                {t.pickerSelected(checkedFiles.length)} · {humanSize(totalSize)}
              </span>
              <div className="picker-action-buttons">
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => galleryInput.current && galleryInput.current.click()}
                >
                  {t.pickerAddMore}
                </button>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={checkedFiles.length === 0}
                  onClick={() => onConfirm(checkedFiles.map((p) => p.file))}
                >
                  {t.pickerUpload(checkedFiles.length)}
                </button>
              </div>
            </div>
          </>
        )}

        <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 12 }} onClick={onClose}>
          {t.cancel}
        </button>
      </div>
    </div>
  );
}
