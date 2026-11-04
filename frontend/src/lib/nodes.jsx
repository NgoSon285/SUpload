/**
 * Danh mục khối của Flow.
 *
 * Mỗi khối khai báo:
 *   label, color, icon, group, desc   -> hiển thị ở bảng khối & trên bảng vẽ
 *   defaults()                         -> dữ liệu ban đầu
 *   fields                             -> bảng Thuộc tính tự sinh từ danh sách này
 *   summary(d, info)                   -> dòng mô tả ngắn trên khối
 *   validate(d)                        -> chuỗi cảnh báo hoặc null
 *   run(api)                           -> logic tính lịch (xem lib/flow.js)
 *
 * Thêm loại khối mới = thêm một mục vào NODES, không cần sửa giao diện.
 */
import {
  IconFlag, IconPencil, IconStack2, IconHourglass, IconCalendarTime, IconRepeat, IconHash,
} from "@tabler/icons-react";
import { unitLabel, unitMs } from "./time";

export const DAYS = [
  { value: "1", label: "T2" }, { value: "2", label: "T3" }, { value: "3", label: "T4" }, { value: "4", label: "T5" },
  { value: "5", label: "T6" }, { value: "6", label: "T7" }, { value: "0", label: "CN" },
];
const DAY_NAME = { 0: "Chủ nhật", 1: "Thứ Hai", 2: "Thứ Ba", 3: "Thứ Tư", 4: "Thứ Năm", 5: "Thứ Sáu", 6: "Thứ Bảy" };

export const SEPARATORS = {
  blank: { label: "Dòng trống", re: /\n\s*\n/ },
  dashes: { label: "Dòng ---", re: /\n\s*-{3,}\s*\n/ },
  line: { label: "Mỗi dòng", re: /\n/ },
};
export const splitBy = (text, sep = "blank") =>
  (text || "").split((SEPARATORS[sep] || SEPARATORS.blank).re).map((s) => s.trim()).filter(Boolean);

const toMin = (hhmm) => { const [h, m] = (hhmm || "00:00").split(":").map(Number); return h * 60 + (m || 0); };
const atMin = (t, min, addDays = 0) => { const d = new Date(t); d.setDate(d.getDate() + addDays); d.setHours(Math.floor(min / 60), min % 60, 0, 0); return d; };

/** Đẩy thời điểm t vào khung giờ cho phép (ngày trong tuần + giờ từ..đến). */
export function fitWindow(t, win) {
  if (!win) return t;
  const days = new Set((win.days?.length ? win.days : ["0", "1", "2", "3", "4", "5", "6"]).map(Number));
  const from = toMin(win.from), to = toMin(win.to);
  for (let k = 0; k < 8; k++) {
    const day = atMin(t, 0, k);
    if (!days.has(day.getDay())) continue;
    const start = atMin(t, from, k), end = atMin(t, to, k);
    if (k === 0) {
      if (t < start) return start;
      if (t <= end) return t;
      continue;
    }
    return start;
  }
  return t;
}

/* ---------- các khối ---------- */
export const NODES = {
  start: {
    label: "Bắt đầu", color: "teal", icon: IconFlag, group: "Khởi đầu", desc: "Thời điểm flow bắt đầu chạy",
    source: true, target: false, deletable: false,
    defaults: () => ({ mode: "now", at: null }),
    fields: [
      { key: "mode", kind: "segmented", options: [{ value: "now", label: "Khi bấm Chạy" }, { value: "at", label: "Vào lúc…" }] },
      { key: "at", kind: "datetime", label: "Thời điểm bắt đầu", show: (d) => d.mode === "at" },
      { kind: "note", text: "Các khối nối phía sau lần lượt tính giờ đăng từ thời điểm này." },
    ],
    summary: (d) => (d.mode === "at" && d.at ? null : "Ngay khi bấm Chạy"),
    validate: (d) => (d.mode === "at" && !d.at ? "Chưa chọn thời điểm bắt đầu" : null),
    run: ({ d, now, go }) => go(d.mode === "at" && d.at ? new Date(d.at) : now),
  },

  post: {
    label: "Bài viết", color: "indigo", icon: IconPencil, group: "Nội dung", desc: "Một bài với nội dung, ảnh, link",
    defaults: () => ({ message: "", link: "", photos: [], variants: false }),
    fields: [
      { key: "variants", kind: "switch", label: "Nhiều phiên bản nội dung", desc: "Viết nhiều phiên bản, cách nhau bởi một dòng ---; mỗi lần chạy chọn ngẫu nhiên 1 bản." },
      { key: "message", kind: "textarea", label: "Nội dung", minRows: 4, placeholder: "Nội dung bài viết…",
        desc: (d) => (d.variants ? `${splitBy(d.message, "dashes").length} phiên bản · ` : "") + "Có thể dùng {a|b|c} để chọn ngẫu nhiên một từ" },
      { key: "photos", kind: "photos", label: "Ảnh" },
      { key: "link", kind: "text", label: "Link", placeholder: "https://..." },
    ],
    summary: (d) => d.message?.trim() || d.link || (d.photos?.length ? "Bài chỉ có ảnh" : null),
    validate: (d) => (!d.message?.trim() && !d.photos?.length && !d.link?.trim() ? "Bài viết đang trống" : null),
    run: ({ d, t, rand, emit, go }) => {
      const msg = d.variants ? rand.pick(splitBy(d.message, "dashes")) || "" : d.message || "";
      const at = emit({ message: msg, link: d.link || "", photos: d.photos || [] }, t);
      go(at);
    },
  },

  batch: {
    label: "Nhiều bài", color: "violet", icon: IconStack2, group: "Nội dung", desc: "Dán nhiều đoạn / thả nhiều ảnh, mỗi cái một bài",
    defaults: () => ({ text: "", sep: "blank", photos: [], perPost: 1, caption: "", gap: 1, unit: "h", order: "seq", limit: 0 }),
    fields: [
      { key: "sep", kind: "segmented", label: "Tách bài theo", options: Object.entries(SEPARATORS).map(([value, s]) => ({ value, label: s.label })) },
      { key: "text", kind: "textarea", label: "Nội dung các bài", minRows: 6,
        placeholder: (d) => (d.sep === "line" ? "Bài 1\nBài 2\nBài 3" : d.sep === "dashes" ? "Bài 1 (có thể nhiều đoạn)\n---\nBài 2" : "Bài thứ nhất…\n\nBài thứ hai…"),
        desc: (d) => `${splitBy(d.text, d.sep).length} đoạn · hỗ trợ {a|b|c}` },
      { key: "photos", kind: "photos", label: "Ảnh", desc: "Ảnh được chia lần lượt cho từng bài theo thứ tự." },
      { key: "perPost", kind: "number", label: "Số ảnh mỗi bài", min: 1, max: 10, show: (d) => (d.photos || []).length > 1 },
      { key: "caption", kind: "text", label: "Chú thích cho bài không có đoạn đi kèm", placeholder: "Có thể để trống", show: (d) => photoGroups(d).length > splitBy(d.text, d.sep).length },
      { kind: "duration", label: "Các bài cách nhau", valueKey: "gap", unitKey: "unit", min: 1 },
      { key: "order", kind: "segmented", label: "Thứ tự đăng", options: [{ value: "seq", label: "Theo thứ tự" }, { value: "shuffle", label: "Xáo ngẫu nhiên" }] },
      { key: "limit", kind: "number", label: "Giới hạn số bài", desc: "0 = đăng tất cả", min: 0, max: 500 },
      { kind: "note", color: "violet", text: (d) => `Khối này tạo ${batchItems(d).length} bài.` },
    ],
    summary: (d) => { const n = batchItems(d).length; return n ? `${n} bài · cách nhau ${d.gap || 1} ${unitLabel(d.unit)}${d.order === "shuffle" ? " · xáo trộn" : ""}` : null; },
    validate: (d) => (!batchItems(d).length ? "Chưa có nội dung hoặc ảnh" : null),
    run: ({ d, t, rand, emit, go }) => {
      let items = batchItems(d);
      if (d.order === "shuffle") items = rand.shuffle(items);
      if (Number(d.limit) > 0) items = items.slice(0, Number(d.limit));
      const gap = Math.max(1, Number(d.gap) || 1) * unitMs(d.unit);
      let cur = t;
      items.forEach((it, i) => { cur = emit(it, i === 0 ? cur : new Date(+cur + gap)); });
      go(cur);
    },
  },

  format: {
    label: "Định dạng", color: "pink", icon: IconHash, group: "Nội dung", desc: "Thêm phần đầu/cuối (hashtag, chữ ký) cho các bài phía sau",
    defaults: () => ({ prefix: "", suffix: "" }),
    fields: [
      { key: "prefix", kind: "textarea", label: "Thêm vào đầu mỗi bài", minRows: 2, placeholder: "🔥 KHUYẾN MÃI" },
      { key: "suffix", kind: "textarea", label: "Thêm vào cuối mỗi bài", minRows: 2, placeholder: "#tiembanh #banhngon\nHotline: 0900 000 000" },
      { kind: "note", text: "Áp dụng cho mọi bài nối phía sau khối này. Có thể xếp nhiều khối Định dạng nối tiếp nhau." },
    ],
    summary: (d) => [d.prefix && `Đầu: ${d.prefix}`, d.suffix && `Cuối: ${d.suffix}`].filter(Boolean).join("\n") || null,
    validate: (d) => (!d.prefix?.trim() && !d.suffix?.trim() ? "Chưa có nội dung định dạng" : null),
    run: ({ d, t, ctx, go }) => go(t, { ...ctx, prefix: [...ctx.prefix, d.prefix].filter((x) => x?.trim()), suffix: [d.suffix, ...ctx.suffix].filter((x) => x?.trim()) }),
  },

  wait: {
    label: "Chờ", color: "orange", icon: IconHourglass, group: "Thời gian", desc: "Nghỉ một khoảng, ngẫu nhiên, hoặc đợi tới giờ/thứ cố định",
    defaults: () => ({ mode: "duration", value: 1, unit: "d", min: 30, max: 90, runit: "m", time: "08:00", dow: "1" }),
    fields: [
      { key: "mode", kind: "select", label: "Kiểu chờ", options: [
        { value: "duration", label: "Chờ một khoảng cố định" }, { value: "random", label: "Chờ ngẫu nhiên trong khoảng" },
        { value: "until", label: "Đợi tới giờ cố định (hằng ngày)" }, { value: "weekday", label: "Đợi tới thứ trong tuần" }] },
      { kind: "duration", label: "Thời gian chờ", valueKey: "value", unitKey: "unit", min: 0, show: (d) => d.mode === "duration" },
      { kind: "range", label: "Chờ từ … đến …", minKey: "min", maxKey: "max", unitKey: "runit", show: (d) => d.mode === "random",
        desc: "Mỗi lần chạy chọn một giá trị ngẫu nhiên, giúp lịch đăng tự nhiên hơn." },
      { key: "dow", kind: "chips", label: "Vào thứ", options: DAYS, show: (d) => d.mode === "weekday" },
      { key: "time", kind: "time", label: "Lúc", show: (d) => d.mode === "until" || d.mode === "weekday",
        desc: (d) => (d.mode === "until" ? "Nếu đã qua giờ này hôm nay thì đợi tới hôm sau." : undefined) },
    ],
    summary: (d) => ({
      duration: `Chờ ${d.value || 0} ${unitLabel(d.unit)}`,
      random: `Chờ ngẫu nhiên ${d.min}–${d.max} ${unitLabel(d.runit)}`,
      until: `Đợi tới ${d.time || "08:00"} lần kế tiếp`,
      weekday: `Đợi tới ${DAY_NAME[d.dow] || ""} lúc ${d.time || "08:00"}`,
    }[d.mode]),
    validate: (d) => (d.mode === "random" && Number(d.max) < Number(d.min) ? "Giá trị “đến” phải lớn hơn “từ”" : null),
    run: ({ d, t, rand, go }) => {
      if (d.mode === "random") {
        const lo = Number(d.min) || 0, hi = Math.max(lo, Number(d.max) || 0);
        return go(new Date(+t + Math.round((lo + rand() * (hi - lo)) * unitMs(d.runit))));
      }
      if (d.mode === "until" || d.mode === "weekday") {
        const m = toMin(d.time || "08:00");
        for (let k = 0; k < 8; k++) {
          const c = atMin(t, m, k);
          if (c > t && (d.mode === "until" || c.getDay() === Number(d.dow))) return go(c);
        }
        return go(t);
      }
      return go(new Date(+t + Math.max(0, Number(d.value) || 0) * unitMs(d.unit)));
    },
  },

  window: {
    label: "Khung giờ", color: "cyan", icon: IconCalendarTime, group: "Thời gian", desc: "Chỉ đăng vào ngày & giờ cho phép",
    defaults: () => ({ days: ["1", "2", "3", "4", "5", "6", "0"], from: "08:00", to: "21:00" }),
    fields: [
      { key: "days", kind: "chips", multiple: true, label: "Ngày được đăng", options: DAYS },
      { kind: "timerange", label: "Trong khoảng giờ", fromKey: "from", toKey: "to" },
      { kind: "note", text: "Mọi bài phía sau rơi ngoài khung này sẽ tự lùi sang đầu khung kế tiếp." },
    ],
    summary: (d) => {
      const all = (d.days || []).length === 7;
      const wk = ["1", "2", "3", "4", "5"].every((x) => d.days?.includes(x)) && d.days.length === 5;
      const days = all ? "Mọi ngày" : wk ? "T2–T6" : DAYS.filter((x) => d.days?.includes(x.value)).map((x) => x.label).join(", ");
      return `${days} · ${d.from}–${d.to}`;
    },
    validate: (d) => (!d.days?.length ? "Chưa chọn ngày nào" : toMin(d.to) <= toMin(d.from) ? "Giờ kết thúc phải sau giờ bắt đầu" : null),
    run: ({ d, t, ctx, go }) => { const c = { ...ctx, window: d }; go(fitWindow(t, d), c); },
  },

  repeat: {
    label: "Lặp lại", color: "grape", icon: IconRepeat, group: "Thời gian", desc: "Chạy các khối phía sau nhiều lần",
    defaults: () => ({ times: 3, every: 1, unit: "d" }),
    fields: [
      { key: "times", kind: "number", label: "Số lần", min: 1, max: 100 },
      { kind: "duration", label: "Mỗi lần cách nhau", valueKey: "every", unitKey: "unit", min: 1 },
      { kind: "note", text: (d) => `Các khối nối phía sau được chạy ${d.times || 1} lần. Kết hợp với Nhiều bài + Xáo ngẫu nhiên để mỗi lần đăng một thứ tự khác.` },
    ],
    summary: (d) => `${d.times || 1} lần · mỗi ${d.every || 1} ${unitLabel(d.unit)}`,
    validate: () => null,
    run: ({ d, t, ctx, go }) => {
      const n = Math.max(1, Math.min(100, Number(d.times) || 1));
      const step = Math.max(1, Number(d.every) || 1) * unitMs(d.unit);
      for (let i = 0; i < n; i++) go(new Date(+t + i * step), { ...ctx, iter: `${ctx.iter}.${i}` });
    },
  },
};

export const NODE_GROUPS = ["Khởi đầu", "Nội dung", "Thời gian"];
export const nodeDef = (type) => NODES[type] || NODES.post;
export const withDefaults = (type, data) => ({ ...nodeDef(type).defaults(), ...(data || {}) });

/* ---------- helpers cho khối Nhiều bài ---------- */
export function photoGroups(d) {
  const k = Math.max(1, Number(d.perPost) || 1);
  const out = [];
  for (let i = 0; i < (d.photos || []).length; i += k) out.push(d.photos.slice(i, i + k));
  return out;
}
export function batchItems(d) {
  const paras = splitBy(d.text, d.sep);
  const groups = photoGroups(d);
  const n = Math.max(paras.length, groups.length);
  return Array.from({ length: n }, (_, i) => ({ message: paras[i] ?? d.caption ?? "", photos: groups[i] || [], link: "" }));
}
