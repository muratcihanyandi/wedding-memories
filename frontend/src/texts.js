// Tum Turkce arayuz metinleri tek yerden yonetilir (spec #43, #46).
// Admin panelinden degistirilebilen metinler (wedding_title vb.)
// sunucudan /api/config ile gelir; buradaki degerler yalnizca yedek.

export const t = {
  appTitle: "Wedding Memories",

  // Karşılama
  namePrompt: "Adın nedir?",
  namePlaceholder: "Örn. Elif",
  continueBtn: "Devam Et",
  nameExistsTitle: "Bu isim daha önce kullanılmış",
  nameExistsText: (name) => `“${name}” adıyla biri daha önce anı paylaşmış.`,
  samePersonBtn: "Aynı kişiyim, devam et",
  differentPersonBtn: "Farklı bir kişiyim",
  guestFallback: "Misafir",

  // Zarf girisi (intro)
  introHeadline: "Evleniyoruz...",
  introCountdownLabel: "25 Ekim'e kalan süre",
  introDayUnit: "gün",
  introMarried: "Evlendik 🤍",
  introPullHint: "Zarfı yukarı çekin",

  // Yükleme
  hello: (name) => `Merhaba ${name}! 🤍`,
  addFilesBtn: "+ Fotoğraf veya Video Ekle",
  addMoreBtn: "+ Daha Ekle",
  uploading: "Yükleniyor...",
  uploaded: "Yüklendi ✓",
  waiting: "Sırada",
  error: "Hata",
  retryBtn: "Tekrar Dene",
  removeBtn: "Kaldır",
  uploadWarning: "Yükleme sürerken bu sayfayı kapatmayın.",
  filesCount: (n) => `${n} dosya`,

  // Başarı
  successTitle: "Teşekkürler! 🤍",
  successThanks: (name) => `${name}, anılarını bizimle paylaştığın için teşekkür ederiz.`,
  addMoreLink: "Başka Anı Ekle",

  // Albüm (/album) - herkese acik
  albumTitle: "Düğün Anıları",
  albumNav: "Albüm",
  albumAll: "Tümü",
  albumEmpty: "Henüz yüklenen anı yok. 🤍",
  albumZipAll: "Tümünü ZIP indir",
  uploadedBy: (name) => name,
  viewAll: "Tüm Fotoğraflar",
  viewByPerson: "Kişilere Göre",
  zipGrouped: "Klasörlü ZIP",
  zipGroupedHint: "Her kişi kendi klasöründe",
  zipFlat: "Tek Klasör ZIP",
  zipFlatHint: "Tüm dosyalar birlikte",

  // Admin galeri
  adminGallery: "Galeri",

  // Genel
  loading: "Yükleniyor...",
  connectionError: "Bağlantı kurulamadı. Wi-Fi bağlantınızı kontrol edip tekrar deneyin.",
  serverError: "Bir hata oluştu. Lütfen tekrar deneyin.",
  goBack: "Geri Dön",

  // Admin - giriş
  adminLoginTitle: "Yönetim Paneli",
  adminUsername: "Kullanıcı Adı",
  adminPassword: "Şifre",
  adminLoginBtn: "Giriş Yap",

  // Admin - panel
  adminPanel: "Panel",
  adminGuests: "Katılımcılar",
  adminSettings: "Ayarlar",
  adminLogout: "Çıkış",
  statUsers: "Katılımcı",
  statPhotos: "Fotoğraf",
  statVideos: "Video",
  statFiles: "Toplam Dosya",
  statSize: "Kullanılan Alan",
  storageTitle: "Depolama",
  storageWarning: "Depolama alanı %90 dolu!",
  storageError: "Depolama cihazı bağlı değil!",
  storageUsage: (used, total) => `${used} / ${total}`,

  // Admin - kullanıcılar
  usersTitle: "Katılımcılar",
  userFiles: (n) => `${n} dosya`,
  userNoFiles: "Henüz dosya yok",
  lastUpload: "Son yükleme",
  emptyUsers: "Henüz kimse anı paylaşmadı. 🤍",

  // Admin - galeri
  downloadAllZip: "Tümünü ZIP indir",
  deleteUser: "Katılımcıyı Sil",
  deleteFile: "Dosyayı Sil",
  deleteSelected: (n) => `${n} dosyayı sil`,
  confirmDeleteUser: (name) =>
    `${name} adlı katılımcının TÜM dosyaları kalıcı olarak silinecek.\n\nBu işlem geri alınamaz. Emin misiniz?`,
  confirmDeleteFiles: (n) =>
    `Seçilen ${n} dosya kalıcı olarak silinecek.\n\nBu işlem geri alınamaz. Emin misiniz?`,
  confirmDeleteFile: "Bu dosya kalıcı olarak silinecek. Bu işlem geri alınamaz. Emin misiniz?",
  downloadFile: "İndir",
  missingFile: "Dosya diskte bulunamadı",
  selectMode: "Seç",
  cancel: "Vazgeç",
  delete: "Sil",
  close: "Kapat",

  // Admin - ayarlar
  settingsTitle: "Ayarlar",
  settingsWeddingTitle: "Düğün / Çift Adı",
  settingsWelcomeText: "Karşılama Mesajı",
  settingsUploadText: "Yükleme Sayfası Mesajı",
  settingsSuccessText: "Başarı Mesajı",
  settingsPublicUrl: "QR Kod Adresi (PUBLIC_URL)",
  settingsPublicUrlHint: "Örn. http://192.168.1.50:33464 veya https://site.com",
  settingsSave: "Kaydet",
  settingsSaved: "Ayarlar kaydedildi ✓",
  qrTitle: "QR Kod",
  qrHint: "Bu kodu düğün alanına bastırabilirsiniz. Katılımcılar telefonla okutup siteye giriş yapar.",
  qrDownload: "Yüksek Çözünürlüklü PNG İndir",
  maintenanceTitle: "Bakım",
  maintenanceCleanup: "Tutarlılık Kontrolü",
  maintenanceCleanupHint: "Veritabanı ile disk arasında tutumsuz kayıt varsa temizler.",
  maintenanceBackup: "Veritabanı Yedeğini İndir",
  cleanupDone: (removed, orphan) =>
    `${removed} eksik kayıt temizlendi, ${orphan} yetim dosya bulundu.`,
};

// Bayt sayisini okunur boyuta cevirir: 1536 -> "1,5 KB"
export function humanSize(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const formatted = unit === 0 ? `${value}` : value.toFixed(1).replace(".", ",");
  return `${formatted} ${units[unit]}`;
}

export function formatDate(iso) {
  try {
    return new Date(iso).toLocaleDateString("tr-TR", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "";
  }
}
