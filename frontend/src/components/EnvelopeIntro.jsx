// Site acilis intro'u: tozpembe zarf acilir, icinden el yazisi davetiye ve
// 25 Ekim geri sayimi cikar; zarf parmakla yukari cekilince site acilir.
import { useEffect, useRef, useState } from "react";

import { t } from "../texts.js";
import { ChevronUpIcon, HeartIcon } from "./icons.jsx";

// Dugun tarihi: 25 Ekim 2026, gun basi (yerel saat)
const WEDDING_AT = new Date(2026, 9, 25, 0, 0, 0).getTime();

const OPEN_DELAY_MS = 1000; // kapali zarf bekleme suresi
const HINT_DELAY_MS = 3900; // cekme ipucunun cikma zamani
const LEAVE_MS = 880; // kapanis kayma animasyonu + pay
const DRAG_RESISTANCE = 0.55; // cekme direnci (zarf agirligi hissi)
const DRAG_CLOSE_THRESHOLD = -70; // kapanis icin gereken cekme mesafesi (px)

function pad2(n) {
  return String(n).padStart(2, "0");
}

function Countdown() {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const remaining = WEDDING_AT - now;
  if (remaining <= 0) {
    return <span className="cd-married">{t.introMarried}</span>;
  }
  const total = Math.floor(remaining / 1000);
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return (
    <>
      <span className="cd-num">{days}</span> {t.introDayUnit}{" "}
      <span className="cd-num">{pad2(hours)}</span>:<span className="cd-num">{pad2(minutes)}</span>:
      <span className="cd-num">{pad2(seconds)}</span>
    </>
  );
}

export default function EnvelopeIntro({ onReveal, onDone }) {
  const [opened, setOpened] = useState(false);
  const [hint, setHint] = useState(false);
  const [drag, setDrag] = useState({ active: false, y: 0 });
  const [leaving, setLeaving] = useState(false);
  const dragRef = useRef(null);

  useEffect(() => {
    const openTimer = setTimeout(() => setOpened(true), OPEN_DELAY_MS);
    const hintTimer = setTimeout(() => setHint(true), HINT_DELAY_MS);
    return () => {
      clearTimeout(openTimer);
      clearTimeout(hintTimer);
    };
  }, []);

  function close() {
    if (leaving) return;
    setLeaving(true);
    onReveal?.(); // zarf kayarken siteyle birlikte yumusakca belirsin
    setTimeout(onDone, LEAVE_MS);
  }

  function onPointerDown(e) {
    if (leaving) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { startY: e.clientY, startedAt: Date.now(), moved: false, y: 0 };
    setDrag({ active: true, y: 0 });
  }

  function onPointerMove(e) {
    const d = dragRef.current;
    if (!d) return;
    const dy = e.clientY - d.startY;
    if (dy < -8) d.moved = true;
    if (dy < 0) {
      const y = Math.round(dy * DRAG_RESISTANCE);
      d.y = y;
      setDrag({ active: true, y });
    }
  }

  function onPointerUp() {
    const d = dragRef.current;
    if (!d) return;
    dragRef.current = null;
    const isTap = !d.moved && Date.now() - d.startedAt < 350;
    if (isTap || d.y < DRAG_CLOSE_THRESHOLD) {
      close();
    } else {
      setDrag({ active: false, y: 0 });
    }
  }

  function cancelDrag() {
    dragRef.current = null;
    setDrag({ active: false, y: 0 });
  }

  const cls = [
    "intro-overlay",
    opened ? "is-open" : "",
    hint ? "show-hint" : "",
    leaving ? "is-leaving" : "",
    drag.active ? "is-dragging" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const ty = leaving ? "-104%" : `${drag.y}px`;

  return (
    <div
      className={cls}
      style={{ transform: `translate3d(0, ${ty}, 0)` }}
      role="button"
      tabIndex={0}
      aria-label={`${t.introHeadline} ${t.introPullHint}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowUp") {
          e.preventDefault();
          close();
        }
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={cancelDrag}
    >
      <div className="intro-stage">
        <div className="envelope">
          <div className="env-back" aria-hidden="true" />
          <div className="env-flap" aria-hidden="true">
            <div className="env-face env-face-out" />
            <div className="env-face env-face-in" />
            <div className="env-seal">
              <HeartIcon size={18} />
            </div>
          </div>
          <div className="env-paper">
            <span className="paper-heart" aria-hidden="true">
              <HeartIcon size={20} />
            </span>
            <p className="paper-script">{t.introHeadline}</p>
            <span className="paper-divider" aria-hidden="true" />
            <p className="paper-count-label">{t.introCountdownLabel}</p>
            <p className="paper-count">
              <Countdown />
            </p>
          </div>
          <div className="env-front" aria-hidden="true">
            <svg className="env-fold" viewBox="0 0 100 70" preserveAspectRatio="none">
              <path d="M0 0 L50 32 L100 0" />
              <path d="M0 70 L50 32 L100 70" />
            </svg>
          </div>
        </div>
        <div className="intro-hint" aria-hidden="true">
          <ChevronUpIcon size={22} />
          <span>{t.introPullHint}</span>
        </div>
      </div>
    </div>
  );
}
