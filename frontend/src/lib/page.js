/** Thông tin Page đang kết nối, suy ra từ cài đặt. */
export const configured = (s) =>
  !!s && (s.method === "api" ? !!(s.page_id && s.page_token_set) : !!s.page_url);

export const pageName = (s) => {
  if (!s) return "";
  if (s.method === "api") return s.page_name || (s.page_id ? `Page ${s.page_id}` : "");
  return s.page_url ? s.page_url.replace(/^https?:\/\/(www\.|m\.)?facebook\.com\//, "").replace(/\/$/, "") : "";
};
