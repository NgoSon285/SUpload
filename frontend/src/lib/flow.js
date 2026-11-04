import dayjs from "dayjs";
import { unitMs } from "./time";

/** Tách nội dung "Nhiều bài": mỗi bài cách nhau bởi ít nhất 1 dòng trống. */
export const splitParagraphs = (text) =>
  (text || "")
    .split(/\n\s*\n/)
    .map((s) => s.trim())
    .filter(Boolean);

/** Danh sách bài sinh ra từ node "Nhiều bài": đoạn thứ i đi kèm ảnh thứ i. */
export function batchItems(data) {
  const paras = splitParagraphs(data.text);
  const photos = data.photos || [];
  const n = Math.max(paras.length, photos.length);
  return Array.from({ length: n }, (_, i) => ({
    message: paras[i] ?? data.caption ?? "",
    photos: photos[i] ? [photos[i]] : [],
    link: "",
  }));
}

function nextAt(t, hhmm) {
  const [h, m] = (hhmm || "08:00").split(":").map(Number);
  let x = dayjs(t).hour(h).minute(m).second(0).millisecond(0);
  if (!x.isAfter(t)) x = x.add(1, "day");
  return x.toDate();
}

/**
 * Duyệt flow từ các node "Bắt đầu", tính thời điểm đăng cho từng bài.
 * Trả về { posts, times: {nodeId: Date}, issues: {nodeId: string}, unreachable: Set }
 */
export function computeSchedule(nodes, edges, now = new Date()) {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const out = {};
  edges.forEach((e) => (out[e.source] ||= []).push(e.target));
  const posts = [];
  const times = {};
  const issues = {};
  const reached = new Set();

  const visit = (id, t, path) => {
    const node = byId[id];
    if (!node || path.has(id)) {
      if (node) issues[id] = "Flow bị lặp vòng tại đây";
      return;
    }
    reached.add(id);
    const d = node.data || {};
    let next = t;
    if (node.type === "start") {
      next = d.mode === "at" && d.at ? new Date(d.at) : now;
      times[id] = next;
    } else if (node.type === "post") {
      times[id] = t;
      if (!d.message?.trim() && !(d.photos || []).length && !d.link?.trim()) issues[id] = "Bài viết đang trống";
      else posts.push({ nodeId: id, time: t, message: d.message || "", link: d.link || "", photos: d.photos || [] });
    } else if (node.type === "batch") {
      times[id] = t;
      const items = batchItems(d);
      const gap = Math.max(1, Number(d.gap) || 1) * unitMs(d.unit || "h");
      if (!items.length) issues[id] = "Chưa có nội dung hoặc ảnh";
      items.forEach((it, i) => posts.push({ nodeId: id, index: i, time: new Date(+t + i * gap), ...it }));
      if (items.length) next = new Date(+t + (items.length - 1) * gap);
    } else if (node.type === "wait") {
      next = d.mode === "until" ? nextAt(t, d.time) : new Date(+t + Math.max(0, Number(d.value) || 0) * unitMs(d.unit || "h"));
      times[id] = next;
    }
    const p2 = new Set(path).add(id);
    (out[id] || []).forEach((tid) => visit(tid, next, p2));
  };

  nodes.filter((n) => n.type === "start").forEach((n) => visit(n.id, now, new Set()));
  const unreachable = new Set(nodes.filter((n) => !reached.has(n.id)).map((n) => n.id));
  unreachable.forEach((id) => (issues[id] ||= "Chưa nối với khối Bắt đầu"));
  posts.sort((a, b) => a.time - b.time);
  return { posts, times, issues, unreachable };
}

let seq = 0;
export const newId = (p = "n") => `${p}_${Date.now().toString(36)}${(seq++).toString(36)}`;

export const NODE_DEFAULTS = {
  start: () => ({ mode: "now", at: null }),
  post: () => ({ message: "", link: "", photos: [] }),
  batch: () => ({ text: "", photos: [], caption: "", gap: 1, unit: "h" }),
  wait: () => ({ mode: "duration", value: 1, unit: "d", time: "08:00" }),
};

export function sampleFlow() {
  const ids = [newId(), newId(), newId(), newId()];
  return {
    nodes: [
      { id: ids[0], type: "start", position: { x: 0, y: 0 }, data: { mode: "now", at: null }, deletable: false },
      { id: ids[1], type: "post", position: { x: 0, y: 150 }, data: { message: "Chào mừng bạn đến với Page! 👋", link: "", photos: [] } },
      { id: ids[2], type: "wait", position: { x: 0, y: 330 }, data: { mode: "until", value: 1, unit: "d", time: "08:00" } },
      { id: ids[3], type: "batch", position: { x: 0, y: 480 }, data: { text: "Bài thứ nhất\n\nBài thứ hai\n\nBài thứ ba", photos: [], caption: "", gap: 3, unit: "h" } },
    ],
    edges: ids.slice(1).map((id, i) => ({ id: `e_${ids[i]}_${id}`, source: ids[i], target: id })),
  };
}
