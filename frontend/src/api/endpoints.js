/** Toàn bộ API của máy chủ, gom theo nhóm. Giao diện chỉ gọi qua đây, không viết URL rải rác. */
import { api } from "./client";

const json = (method) => (url, body) => api(url, { method, body });
const post = json("POST");
const put = json("PUT");
const del = (url) => api(url, { method: "DELETE" });

export const stateApi = {
  get: () => api("/api/state"),
  previewPlan: (posts) => post("/api/plan/preview", { posts }),
};

export const mediaApi = {
  async upload(files) {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return (await api("/api/upload", { method: "POST", body: fd })).files;
  },
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

export const settingsApi = {
  save: (body) => post("/api/settings", body),
  testConnection: () => post("/api/test-connection"),
  fetchPages: (body) => post("/api/fb/pages", body),
  selectPage: (id) => post("/api/fb/select-page", { id }),
  browser: (action) => post(`/api/browser/${action}`),
};
