import { useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import Home from "./pages/Home.jsx";
import Upload from "./pages/Upload.jsx";
import Success from "./pages/Success.jsx";
import Album from "./pages/Album.jsx";
import AdminLogin from "./admin/Login.jsx";
import AdminApp from "./admin/AdminApp.jsx";
import Dashboard from "./admin/Dashboard.jsx";
import Users from "./admin/Users.jsx";
import UserDetail from "./admin/UserDetail.jsx";
import AdminGallery from "./admin/AdminGallery.jsx";
import Settings from "./admin/Settings.jsx";
import EnvelopeIntro from "./components/EnvelopeIntro.jsx";

export default function App() {
  // Zarf intro'su her sayfa yuklemesinde gosterilir; oturum yonlendirmesi
  // altta calismaya devam eder, overlay route degisiminden etkilenmez.
  const [introDone, setIntroDone] = useState(false);
  const [revealed, setRevealed] = useState(false);

  function handleIntroDone() {
    setIntroDone(true);
    // giris sayfasindaysa isim alani odaklansin
    document.querySelector(".public-shell .input")?.focus();
  }

  return (
    <BrowserRouter>
      {!introDone && (
        <EnvelopeIntro onReveal={() => setRevealed(true)} onDone={handleIntroDone} />
      )}
      <div className={revealed ? "app-root" : "app-root is-veiled"}>
        <Routes>
          {/* Public akis */}
          <Route path="/" element={<Home />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/success" element={<Success />} />

          {/* Admin */}
          <Route path="/album" element={<Album />} />
          <Route path="/admin/login" element={<AdminLogin />} />
          <Route path="/admin" element={<AdminApp />}>
            <Route index element={<Dashboard />} />
            <Route path="users" element={<Users />} />
            <Route path="users/:id" element={<UserDetail />} />
            <Route path="gallery" element={<AdminGallery />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
