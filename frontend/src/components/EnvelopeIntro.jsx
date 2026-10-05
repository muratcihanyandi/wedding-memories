// Site acilis intro'u: tozpembe zarf acilir, icinden el yazisi davetiye ve
// dugun geri sayimi cikar. Kagit parmakla yukari cekilerek scroll gibi
// yukselir; zarfin agzindan bos kagit gelir, geri itilirse zarfa girer.
// Yeterince cekilince kamera cok yavas yaklasir, kagit ekrani kaplar ve
// sitenin yazilari yavas yavas belirir.
import { useEffect, useRef, useState } from "react";

import { t } from "../texts.js";
import { ChevronUpIcon, HeartIcon } from "./icons.jsx";

// Dugun tarihi: 25 Ekim 2026, gun basi (yerel saat)
const WEDDING_AT = new Date(2026, 9, 25, 0, 0, 0).getTime();

const OPEN_DELAY_MS = 1000; // kapali zarf bekleme suresi
const HINT_DELAY_MS = 3900; // cekme ipucunun cikma zamani
const REVEAL_DELAY_MS = 1100; // zoom icinde sitenin belirmeye basladigi an
const LEAVE_MS = 2350; // zoom + belirmenin tamamlanmasi + pay
const TAP_MS = 300; // dokunma sayilma suresi
const ZOOM_SCALE_PAY = 1.12; // kagidin ekrani asan buyume payi

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
  const [dragging, setDragging] = useState(false);
  const [expanding, setExpanding] = useState(false);
  const rootRef = useRef(null);
  const stageRef = useRef(null);
  const paperRef = useRef(null);
  const envRef = useRef(null);
  // offset: + yukari cekilen kagit miktari, - zarfa geri itilen miktar (px)
  // drag baslangicindaki deger "offset"te korunur, "live" guncel konumdur
  const dragRef = useRef({ dragging: false, startY: 0, startedAt: 0, moved: false, offset: 0, live: 0, maxPush: 160 });

  useEffect(() => {
    const openTimer = setTimeout(() => setOpened(true), OPEN_DELAY_MS);
    const hintTimer = setTimeout(() => setHint(true), HINT_DELAY_MS);
    return () => {
      clearTimeout(openTimer);
      clearTimeout(hintTimer);
    };
  }, []);

  // Zoom icin kagidin yeterince cekilmis olmasi gerekir (ekran yuksekligine gore)
  function zoomThreshold() {
    return Math.min(280, Math.round(window.innerHeight * 0.3));
  }

  function applyOffset(offset) {
    const root = rootRef.current;
    if (!root) return;
    root.style.setProperty("--pull", `${Math.max(0, offset)}px`);
    root.style.setProperty("--push", `${Math.max(0, -offset)}px`);
  }

  function startZoom() {
    if (expanding) return;
    const stage = stageRef.current;
    const paper = paperRef.current;
    const root = rootRef.current;
    if (stage && paper && root) {
      const sr = stage.getBoundingClientRect();
      const pr = paper.getBoundingClientRect();
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const scale = Math.max(vw / pr.width, vh / pr.height) * ZOOM_SCALE_PAY;
      // Origin oyle secilir ki kagit olceklendiginde viewport'u tam kapsasin:
      // dikeyde kagit ust/alt kenarlarinin ekran disina tasacagi aralik;
      // mumkunse ekran merkezine yakin nokta kullanilir.
      const s1 = scale - 1;
      const oyMin = (pr.top * scale) / s1;
      const oyMax = (pr.bottom * scale - vh) / s1;
      const oy = Math.min(Math.max(vh / 2, oyMin), oyMax);
      const ox = vw / 2;
      stage.style.transformOrigin = `${(ox - sr.left).toFixed(1)}px ${(oy - sr.top).toFixed(1)}px`;
      root.style.setProperty("--zoom-scale", scale.toFixed(3));
    }
    dragRef.current.dragging = false;
    setDragging(false);
    setExpanding(true);
    // kagit ekran kaplarken sitenin yazilari yavas yavas belirir
    setTimeout(() => onReveal?.(), REVEAL_DELAY_MS);
    setTimeout(onDone, LEAVE_MS);
  }

  function onPointerDown(e) {
    if (expanding) return;
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      /* capture kurulamazsa surukleme yine calisir */
    }
    dragRef.current = {
      ...dragRef.current,
      dragging: true,
      startY: e.clientY,
      startedAt: Date.now(),
      moved: false,
    };
    setDragging(true);
    // Asagi itme siniri: kagit ust kenari yakanin altina indiginde tamamen gizlenir
    const paper = paperRef.current;
    const env = envRef.current;
    if (paper && env) {
      const pr = paper.getBoundingClientRect();
      const er = env.getBoundingClientRect();
      dragRef.current.maxPush = Math.max(40, er.top + er.height * 0.46 - pr.top + 12);
    }
  }

  function onPointerMove(e) {
    const d = dragRef.current;
    if (!d.dragging || expanding) return;
    const dy = e.clientY - d.startY; // yukari cekme: negatif
    if (Math.abs(dy) > 8) d.moved = true;
    let offset = d.offset - dy; // drag baslangicindan itibaren toplam
    if (offset < -d.maxPush) offset = -d.maxPush;
    d.live = offset;
    applyOffset(offset);
    if (offset >= zoomThreshold()) {
      d.dragging = false;
      startZoom(); // yeterince cekildi, kamera devralir
    }
  }

  function onPointerUp() {
    const d = dragRef.current;
    if (!d.dragging) return;
    d.dragging = false;
    d.offset = d.live; // kagit cekildigi yerde kalir (scroll gibi)
    setDragging(false);
    const isTap = !d.moved && Date.now() - d.startedAt < TAP_MS;
    if (isTap) startZoom();
  }

  function cancelDrag() {
    dragRef.current.dragging = false;
    setDragging(false);
  }

  const cls = [
    "intro-overlay",
    opened ? "is-open" : "",
    hint ? "show-hint" : "",
    expanding ? "is-expanding" : "",
    dragging ? "is-dragging" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div
      ref={rootRef}
      className={cls}
      role="button"
      tabIndex={0}
      aria-label={`${t.introHeadline} ${t.introPullHint}`}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " " || e.key === "ArrowUp") {
          e.preventDefault();
          startZoom();
        }
      }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={cancelDrag}
    >
      <div className="intro-stage" ref={stageRef}>
        <div className="envelope" ref={envRef}>
          <div className="env-back" aria-hidden="true" />
          <div className="env-flap" aria-hidden="true">
            <div className="env-face env-face-out" />
            <div className="env-face env-face-in" />
            <div className="env-seal">
              <HeartIcon size={18} />
            </div>
          </div>
          <div className="env-paper" ref={paperRef}>
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
