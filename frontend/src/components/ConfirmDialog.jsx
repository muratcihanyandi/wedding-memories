import { t } from "../texts.js";

// Tum silme islemlerinde "Bu islem geri alinamaz" uyarisini gosteren
// onay diyalogu (spec #19).
export default function ConfirmDialog({ title, message, confirmLabel, onConfirm, onCancel, busy }) {
  return (
    <div className="overlay" role="presentation" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="dialog" role="alertdialog" aria-modal="true" aria-labelledby="confirm-title">
        <h2 id="confirm-title">{title}</h2>
        <p style={{ whiteSpace: "pre-line" }}>{message}</p>
        <div className="dialog-actions">
          <button className="btn btn-danger" onClick={onConfirm} disabled={busy} autoFocus>
            {busy ? t.loading : confirmLabel || t.delete}
          </button>
          <button className="btn btn-outline" onClick={onCancel} disabled={busy}>
            {t.cancel}
          </button>
        </div>
      </div>
    </div>
  );
}
