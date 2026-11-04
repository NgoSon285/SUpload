export async function api(url, { method = "GET", body } = {}) {
  const isForm = body instanceof FormData;
  const res = await fetch(url, {
    method,
    headers: body && !isForm ? { "Content-Type": "application/json" } : undefined,
    body: body && !isForm ? JSON.stringify(body) : body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText || "Lỗi không xác định");
  return data;
}

export const imgUrl = (name) => `/uploads/${encodeURIComponent(name)}`;

export async function uploadImages(files) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const { files: names } = await api("/api/upload", { method: "POST", body: fd });
  return names;
}

export const configured = (s) =>
  !!s && (s.method === "api" ? !!(s.page_id && s.page_token_set) : !!s.page_url);

export const pageName = (s) => {
  if (!s) return "";
  if (s.method === "api") return s.page_name || (s.page_id ? `Page ${s.page_id}` : "");
  return s.page_url ? s.page_url.replace(/^https?:\/\/(www\.|m\.)?facebook\.com\//, "").replace(/\/$/, "") : "";
};

export const storage = {
  get(k, fallback = null) {
    try {
      const v = localStorage.getItem(k);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* trình duyệt chặn lưu trữ */
    }
  },
};
