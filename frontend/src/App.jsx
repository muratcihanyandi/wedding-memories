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

export default function App() {
  return (
    <BrowserRouter>
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
    </BrowserRouter>
  );
}
