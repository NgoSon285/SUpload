/** Gọi API của máy chủ SUpload. Ném Error(thông báo) nếu máy chủ trả lỗi. */
export async function api(url, { method = "GET", body } = {}) {
  const isForm = body instanceof FormData;
  const res = await fetch(url, {
    method,
    headers: body && !isForm ? { "Content-Type": "application/json" } : undefined,
    body: body && !isForm ? JSON.stringify(body) : body,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.error || res.statusText || "Lỗi không xác định");
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const imgUrl = (name) => `/uploads/${encodeURIComponent(name)}`;
