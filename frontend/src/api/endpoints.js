/** Toàn bộ API của máy chủ, gom theo nhóm. Giao diện chỉ gọi qua đây, không viết URL rải rác. */
import { api } from "./client";

const json = (method) => (url, body) => api(url, { method, body });
const post = json("POST");
const put = json("PUT");
const del = (url) => api(url, { method: "DELETE" });

export const stateApi = {
  get: () => api("/api/state"),
  previewPlan: (posts) => post("/api/plan/preview", { posts }),
  runMaintenance: () => post("/api/maintenance/run"),
};

export const mediaApi = {
  async upload(files) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return (await api("/api/upload", { method: "POST", body: fd })).files;
  },
  list: async () => (await api("/api/media")).media,
  remove: (name) => del(`/api/media/${encodeURIComponent(name)}`),
};

export const libraryApi = {
  list: () => api("/api/library"),
  add: (body) => post("/api/library", body),
  edit: (id, body) => put(`/api/library/${id}`, body),
  remove: (id) => del(`/api/library/${id}`),
  used: (id) => post(`/api/library/${id}/used`),
};

export const postsApi = {
  add: (body) => post("/api/posts", body),
  edit: (id, body) => put(`/api/posts/${id}`, body),
  remove: (id, { force = false } = {}) => del(`/api/posts/${id}${force ? "?force=1" : ""}`),
  retry: (id) => post(`/api/posts/${id}/retry`),
  clearDone: () => post("/api/clear-done"),
};

export const flowsApi = {
  list: async () => (await api("/api/flows")).flows,
  save: (id, body) => put(`/api/flows/${id}`, body),
  duplicate: (id) => post(`/api/flows/${id}/duplicate`),
  import: (flow) => post("/api/flows/import", { flow }),
  remove: (id, { withPosts = false } = {}) => del(`/api/flows/${id}${withPosts ? "?delete_posts=1" : ""}`),
  run: (body) => post("/api/flows/run", body),
};

export const pagesApi = {
  add: (body) => post("/api/pages", body),
  edit: (id, body) => put(`/api/pages/${id}`, body),
  remove: (id) => del(`/api/pages/${id}`),
  setDefault: (id) => post(`/api/pages/${id}/default`),
  test: (id) => post(`/api/pages/${id}/test`),
};

export const importApi = {
  templateUrl: (format = "csv") => `/api/import/template?format=${format}`,
  preview: (file) => {
    const fd = new FormData();
    fd.append("file", file);
    return api("/api/import/preview", { method: "POST", body: fd });
  },
  commit: (rows, { skipErrors = false } = {}) => post("/api/import/commit", { rows, skip_errors: skipErrors }),
};

export const insightsApi = {
  get: ({ days = 30, page = "" } = {}) => api(`/api/insights?days=${days}${page ? `&page=${page}` : ""}`),
  refresh: () => post("/api/insights/refresh"),
};

export const aiApi = {
  models: () => api("/api/ai/models"),
  suggest: (body) => post("/api/ai/suggest", body),
};

export const systemApi = {
  info: () => api("/api/system"),
  setAutostart: (enabled) => post("/api/system/autostart", { enabled }),
  shutdown: () => post("/api/system/shutdown"),
};

export const settingsApi = {
  save: (body) => post("/api/settings", body),
  testConnection: () => post("/api/test-connection"),
  fetchPages: (body) => post("/api/fb/pages", body),
  selectPage: (id) => post("/api/fb/select-page", { id }),
  browser: (action) => post(`/api/browser/${action}`),
};
