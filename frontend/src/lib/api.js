// API istemcisi - tum istekler X-Requested-With header'i tasir (CSRF
// savunmasi), hatalar Turkce kullanici mesajlarina cevrilir (spec #45).

const CSRF_KEY = "wm_csrf";

export function getCsrfToken() {
  return sessionStorage.getItem(CSRF_KEY) || "";
}

export function setCsrfToken(token) {
  sessionStorage.setItem(CSRF_KEY, token);
}

export function clearCsrfToken() {
  sessionStorage.removeItem(CSRF_KEY);
}

function defaultError(status) {
  if (status === 401) return "Oturumunuz sona erdi.";
  if (status === 413) return "Bu dosya çok büyük. Lütfen daha küçük bir dosya seçin.";
  if (status === 415) return "Bu dosya türü desteklenmiyor. Lütfen fotoğraf veya video seçin.";
  if (status === 422) return "Geçersiz istek. Lütfen girdiğiniz bilgileri kontrol edin.";
  if (status === 429) return "Çok fazla deneme yaptınız. Lütfen biraz bekleyip tekrar deneyin.";
  if (status === 503) return "Sunucu şu anda hazır değil. Lütfen birazdan tekrar deneyin.";
  return "Bir hata oluştu. Lütfen tekrar deneyin.";
}

export function makeError(status, detail) {
  const err = new Error(detail || defaultError(status));
  err.status = status;
  return err;
}

export async function apiFetch(path, options = {}) {
  const headers = { "X-Requested-With": "XMLHttpRequest", ...(options.headers || {}) };
  const hasBody = options.body !== undefined;
  if (hasBody && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  let res;
  try {
    res = await fetch(path, { ...options, headers });
  } catch {
    const err = new Error("Bağlantı kurulamadı. Wi-Fi bağlantınızı kontrol edip tekrar deneyin.");
    err.status = 0;
    throw err;
  }
  let data = null;
  if (res.status !== 204) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  }
  if (!res.ok) {
    throw makeError(res.status, data && data.detail);
  }
  return data;
}

// Admin istekleri - mutating cagrilara CSRF token'i ekler.
export async function adminFetch(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const headers = { ...(options.headers || {}) };
  if (method !== "GET" && method !== "HEAD") {
    headers["X-CSRF-Token"] = getCsrfToken();
  }
  return apiFetch(path, { ...options, headers });
}

// Tek dosyalik XHR yukleme - gercek progress yuzdesi icin fetch yerine
// XMLHttpRequest kullanilir (fetch'de upload progress yoktur).
export function uploadFile(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/uploads");
    xhr.setRequestHeader("X-Requested-With", "XMLHttpRequest");
    xhr.responseType = "text";

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };
    xhr.onload = () => {
      let data = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        data = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data);
      } else {
        reject(makeError(xhr.status, data && data.detail));
      }
    };
    xhr.onerror = () => {
      const err = new Error("Bağlantı kesildi. Wi-Fi bağlantınızı kontrol edip tekrar deneyin.");
      err.status = 0;
      reject(err);
    };
    // Bilincli olarak timeout YOK (xhr.timeout = 0): GB boyutlu dugun
    // videolari yavas Wi-Fi'da dakikalar surebilir.

    const form = new FormData();
    form.append("files", file, file.name);
    xhr.send(form);
  });
}
