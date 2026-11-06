import { fitWindow, nodeDef, withDefaults } from "./nodes";

export { batchItems, splitBy } from "./nodes";

const MAX_POSTS = 1000;
const MAX_VISITS = 5000;

/* ---------- ngẫu nhiên có hạt: xem trước = khi chạy ---------- */
function hash(str) {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) { h = Math.imul(h ^ str.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
  return (h >>> 0) || 1;
}
export function seededRandom(key) {
  let a = hash(key);
  const r = () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  r.pick = (arr) => (arr.length ? arr[Math.floor(r() * arr.length)] : undefined);
  r.shuffle = (arr) => { const a2 = [...arr]; for (let i = a2.length - 1; i > 0; i--) { const j = Math.floor(r() * (i + 1)); [a2[i], a2[j]] = [a2[j], a2[i]]; } return a2; };
  return r;
}

/** {Chào|Xin chào} {bạn|mọi người} -> chọn ngẫu nhiên, hỗ trợ lồng nhau. */
export function spin(text, rand) {
  let s = text || "";
  for (let guard = 0; guard < 200; guard++) {
    const m = s.match(/\{([^{}]*\|[^{}]*)\}/);
    if (!m) break;
    s = s.slice(0, m.index) + rand.pick(m[1].split("|")) + s.slice(m.index + m[0].length);
  }
  return s;
}

/**
 * Duyệt flow từ các khối Bắt đầu và tính lịch đăng.
 * Mỗi khối chạy hàm run() trong lib/nodes.jsx với:
 *   d, t, now, ctx, rand, emit(item, time) -> thời điểm thực tế (đã áp khung giờ), go(time, ctx?) -> đi tiếp
 */
export function computeSchedule(nodes, edges, now = new Date(), seed = "") {
  const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
  const out = {};
  edges.forEach((e) => { if (byId[e.source] && byId[e.target]) (out[e.source] ||= []).push(e.target); });
  const posts = [];
  const times = {};
  const issues = {};
  const runs = {};
  const reached = new Set();
  let visits = 0;
  let truncated = false;

  const visit = (id, t, ctx, path) => {
    const node = byId[id];
    if (!node) return;
    if (path.has(id)) { issues[id] = "Flow bị lặp vòng tại đây"; return; }
    if (++visits > MAX_VISITS || posts.length >= MAX_POSTS) { truncated = true; return; }
    reached.add(id);
    runs[id] = (runs[id] || 0) + 1;
    const def = nodeDef(node.type);
    const d = withDefaults(node.type, node.data);
    const nextPath = new Set(path).add(id);
    const go = (time, c = ctx) => {
      if (!(id in times)) times[id] = time;
      (out[id] || []).forEach((tid) => visit(tid, time, c, nextPath));
    };

    if (d.disabled) return go(t);
    const problem = def.validate?.(d);
    if (problem) issues[id] = problem;

    const rand = seededRandom(`${seed}|${id}|${ctx.iter}`);
    const emit = (item, time) => {
      const at = fitWindow(time, ctx.window);
      if (posts.length >= MAX_POSTS) { truncated = true; return at; }
      const body = spin(item.message, rand);
      const message = [...ctx.prefix.map((x) => spin(x, rand)), body, ...ctx.suffix.map((x) => spin(x, rand))].filter((x) => x?.trim()).join("\n\n");
      if (!(id in times)) times[id] = at;
      const post = { nodeId: id, time: at, message, link: item.link || "", photos: item.photos || [] };
      if (item.video) Object.assign(post, { video: item.video, video_kind: item.video_kind || "video" });
      posts.push(post);
      return at;
    };
    if (problem && (node.type === "post" || node.type === "batch")) return go(t);
    def.run({ d, t, now, ctx, rand, emit, go });
  };

  const root = { prefix: [], suffix: [], window: null, iter: "0" };
  nodes.filter((n) => n.type === "start").forEach((n) => visit(n.id, now, root, new Set()));
  nodes.forEach((n) => { if (!reached.has(n.id)) issues[n.id] ||= "Chưa nối với khối Bắt đầu"; });
  posts.sort((a, b) => a.time - b.time);
  const perNode = {};
  posts.forEach((p) => (perNode[p.nodeId] = (perNode[p.nodeId] || 0) + 1));
  return { posts, times, issues, runs, perNode, truncated };
}

let seq = 0;
export const newId = (p = "n") => `${p}_${Date.now().toString(36)}${(seq++).toString(36)}`;

export const newNode = (type, position, data) => ({
  id: newId(), type, position, data: withDefaults(type, data), ...(nodeDef(type).deletable === false ? { deletable: false } : {}),
});

export function sampleFlow() {
  const n = [
    newNode("start", { x: 0, y: 0 }),
    newNode("window", { x: 0, y: 150 }, { days: ["1", "2", "3", "4", "5", "6", "0"], from: "08:00", to: "21:00" }),
    newNode("format", { x: 0, y: 300 }, { suffix: "#tiembanh #banhngon" }),
    newNode("post", { x: 0, y: 450 }, { message: "{Chào|Xin chào} cả nhà! Chúc mọi người một ngày vui vẻ 👋" }),
    newNode("wait", { x: 0, y: 630 }, { mode: "until", time: "08:00" }),
    newNode("batch", { x: 0, y: 780 }, { text: "Bài thứ nhất\n\nBài thứ hai\n\nBài thứ ba", gap: 3, unit: "h" }),
  ];
  return { nodes: n, edges: n.slice(1).map((x, i) => ({ id: `e_${n[i].id}_${x.id}`, source: n[i].id, target: x.id })), seed: newId("s") };
}
