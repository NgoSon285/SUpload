import { describe, expect, it } from "vitest";
import { computeSchedule, newNode, seededRandom, spin } from "./flow";
import { batchItems, fitWindow, splitBy, NODES, withDefaults } from "./nodes";

// Thứ Sáu 06/11/2026 22:30 (giờ máy)
const NOW = new Date(2026, 10, 6, 22, 30);
const at = (d, h, m = 0) => new Date(2026, 10, d, h, m);
const n = (type, data) => newNode(type, { x: 0, y: 0 }, data);
const chain = (...nodes) => ({ nodes, edges: nodes.slice(1).map((x, i) => ({ id: `e${i}`, source: nodes[i].id, target: x.id })) });
const run = (f, seed = "s") => computeSchedule(f.nodes, f.edges, NOW, seed);
const plan = (r) => r.posts.map((p) => [p.message, p.time.getTime()]);

describe("Bắt đầu", () => {
  it("chạy ngay hoặc từ thời điểm cụ thể", () => {
    expect(run(chain(n("start"), n("post", { message: "A" }))).posts[0].time).toEqual(NOW);
    const r = run(chain(n("start", { mode: "at", at: "2026-11-10T09:15" }), n("post", { message: "A" })));
    expect(r.posts[0].time).toEqual(at(10, 9, 15));
  });
  it("cảnh báo khi chọn 'Vào lúc' mà chưa có giờ", () => {
    const s = n("start", { mode: "at", at: null });
    expect(run(chain(s)).issues[s.id]).toMatch(/Chưa chọn/);
  });
});

describe("Bài viết", () => {
  it("bỏ qua bài trống và báo cảnh báo, nhưng vẫn chạy tiếp", () => {
    const empty = n("post");
    const r = run(chain(n("start"), empty, n("post", { message: "B" })));
    expect(r.issues[empty.id]).toBe("Bài viết đang trống");
    expect(r.posts.map((p) => p.message)).toEqual(["B"]);
  });
  it("chọn một trong các phiên bản (---)", () => {
    const r = run(chain(n("start"), n("post", { message: "V1\n---\nV2\n---\nV3", variants: true })));
    expect(["V1", "V2", "V3"]).toContain(r.posts[0].message);
  });
  it("spintax {a|b}, kể cả lồng nhau", () => {
    const out = spin("{A|{B|C}} x", seededRandom("k"));
    expect(["A x", "B x", "C x"]).toContain(out);
    expect(spin("không có", seededRandom("k"))).toBe("không có");
  });
});

describe("Nhiều bài", () => {
  it("tách theo dòng trống / --- / mỗi dòng", () => {
    expect(splitBy("a\n\nb\n\n\nc")).toEqual(["a", "b", "c"]);
    expect(splitBy("a\nvẫn a\n---\nb", "dashes")).toEqual(["a\nvẫn a", "b"]);
    expect(splitBy("a\nb\n\nc", "line")).toEqual(["a", "b", "c"]);
  });
  it("ghép ảnh theo số ảnh mỗi bài, dùng chú thích khi thiếu đoạn", () => {
    const items = batchItems(withDefaults("batch", { text: "một", photos: ["1", "2", "3", "4", "5"], perPost: 2, caption: "cap" }));
    expect(items).toEqual([
      { message: "một", photos: ["1", "2"], link: "" },
      { message: "cap", photos: ["3", "4"], link: "" },
      { message: "cap", photos: ["5"], link: "" },
    ]);
  });
  it("giãn cách, giới hạn số bài, và khối sau nối tiếp từ bài cuối", () => {
    const r = run(chain(n("start"), n("batch", { text: "1\n\n2\n\n3\n\n4", gap: 2, unit: "h", limit: 3 }), n("post", { message: "sau" })));
    expect(plan(r)).toEqual([["1", +NOW], ["2", +NOW + 2 * 3600e3], ["3", +NOW + 4 * 3600e3], ["sau", +NOW + 4 * 3600e3]]);
  });
  it("xáo trộn giữ đủ phần tử", () => {
    const r = run(chain(n("start"), n("batch", { text: "1\n\n2\n\n3\n\n4\n\n5", order: "shuffle" })));
    expect(r.posts.map((p) => p.message).sort()).toEqual(["1", "2", "3", "4", "5"]);
  });
});

describe("Chờ", () => {
  it("cố định", () => {
    const r = run(chain(n("start"), n("wait", { mode: "duration", value: 90, unit: "m" }), n("post", { message: "A" })));
    expect(r.posts[0].time).toEqual(new Date(+NOW + 90 * 60e3));
  });
  it("đợi tới giờ cố định: đã qua thì sang hôm sau", () => {
    const r = run(chain(n("start"), n("wait", { mode: "until", time: "08:00" }), n("post", { message: "A" })));
    expect(r.posts[0].time).toEqual(at(7, 8));
  });
  it("đợi tới thứ trong tuần", () => {
    const r = run(chain(n("start"), n("wait", { mode: "weekday", dow: "1", time: "09:30" }), n("post", { message: "A" })));
    expect(r.posts[0].time).toEqual(at(9, 9, 30)); // Thứ Hai 09/11
  });
  it("ngẫu nhiên nằm trong khoảng", () => {
    for (const seed of ["a", "b", "c", "d", "e"]) {
      const r = run(chain(n("start"), n("wait", { mode: "random", min: 30, max: 90, runit: "m" }), n("post", { message: "A" })), seed);
      const mins = (r.posts[0].time - NOW) / 60e3;
      expect(mins).toBeGreaterThanOrEqual(30);
      expect(mins).toBeLessThanOrEqual(90);
    }
  });
  it("cảnh báo khoảng ngược", () => {
    const w = n("wait", { mode: "random", min: 90, max: 30 });
    expect(run(chain(n("start"), w)).issues[w.id]).toMatch(/lớn hơn/);
  });
});

describe("Khung giờ", () => {
  const weekdays = { days: ["1", "2", "3", "4", "5"], from: "08:00", to: "21:00" };
  it("fitWindow: trong khung giữ nguyên, trước khung lùi tới đầu khung, sau khung sang ngày hợp lệ kế tiếp", () => {
    expect(fitWindow(at(9, 10), weekdays)).toEqual(at(9, 10));
    expect(fitWindow(at(9, 6), weekdays)).toEqual(at(9, 8));
    expect(fitWindow(NOW, weekdays)).toEqual(at(9, 8)); // tối Thứ Sáu -> sáng Thứ Hai
    expect(fitWindow(at(7, 12), weekdays)).toEqual(at(9, 8)); // Thứ Bảy -> Thứ Hai
  });
  it("áp cho mọi bài phía sau, kể cả bài trong khối Nhiều bài", () => {
    const r = run(chain(n("start"), n("window", weekdays), n("batch", { text: "1\n\n2\n\n3", gap: 6, unit: "h" })));
    expect(plan(r)).toEqual([["1", +at(9, 8)], ["2", +at(9, 14)], ["3", +at(9, 20)]]);
  });
  it("bài vượt khung thì sang ngày kế", () => {
    const r = run(chain(n("start"), n("window", weekdays), n("batch", { text: "1\n\n2\n\n3", gap: 8, unit: "h" })));
    expect(plan(r).map(([, t]) => t)).toEqual([+at(9, 8), +at(9, 16), +at(10, 8)]);
  });
  it("cảnh báo cấu hình sai", () => {
    const a = n("window", { days: [], from: "08:00", to: "21:00" });
    const b = n("window", { from: "21:00", to: "08:00" });
    const s = n("start");
    const r = run({ nodes: [s, a, b], edges: [{ source: s.id, target: a.id }, { source: s.id, target: b.id }] });
    expect(r.issues[a.id]).toMatch(/Chưa chọn ngày/);
    expect(r.issues[b.id]).toMatch(/kết thúc/);
  });
});

describe("Định dạng & Lặp lại", () => {
  it("thêm phần đầu/cuối, xếp chồng nhiều khối", () => {
    const r = run(chain(n("start"), n("format", { prefix: "ĐẦU", suffix: "#a" }), n("format", { suffix: "#b" }), n("post", { message: "thân" })));
    expect(r.posts[0].message).toBe("ĐẦU\n\nthân\n\n#b\n\n#a");
  });
  it("lặp N lần, mỗi lần cách nhau X", () => {
    const rep = n("repeat", { times: 3, every: 1, unit: "d" });
    const p = n("post", { message: "A" });
    const r = run(chain(n("start"), rep, p));
    expect(r.posts.map((x) => +x.time)).toEqual([+NOW, +NOW + 864e5, +NOW + 2 * 864e5]);
    expect(r.runs[p.id]).toBe(3);
  });
  it("mỗi lần lặp xáo trộn khác nhau nhưng cùng hạt thì giống hệt", () => {
    const f = chain(n("start"), n("repeat", { times: 4, every: 1, unit: "d" }), n("batch", { text: "1\n\n2\n\n3\n\n4\n\n5", order: "shuffle" }));
    const a = run(f, "x"), b = run(f, "x"), c = run(f, "y");
    expect(plan(a)).toEqual(plan(b));
    expect(plan(a)).not.toEqual(plan(c));
    const orders = new Set([0, 1, 2, 3].map((i) => a.posts.filter((p) => +p.time >= +NOW + i * 864e5 && +p.time < +NOW + (i + 1) * 864e5).map((p) => p.message).join("")));
    expect(orders.size).toBeGreaterThan(1);
  });
});

describe("Cấu trúc flow", () => {
  it("khối bị tắt được bỏ qua nhưng vẫn chạy khối phía sau", () => {
    const r = run(chain(n("start"), n("wait", { value: 5, unit: "d", disabled: true }), n("post", { message: "A", disabled: false }), n("post", { message: "B", disabled: true })));
    expect(plan(r)).toEqual([["A", +NOW]]);
  });
  it("rẽ nhánh: mỗi nhánh tự tính giờ", () => {
    const s = n("start"), w = n("wait", { value: 1, unit: "h" }), a = n("post", { message: "A" }), b = n("post", { message: "B" });
    const r = computeSchedule([s, w, a, b], [{ source: s.id, target: a.id }, { source: s.id, target: w.id }, { source: w.id, target: b.id }], NOW, "s");
    expect(plan(r)).toEqual([["A", +NOW], ["B", +NOW + 3600e3]]);
  });
  it("khối chưa nối được đánh dấu, không sinh bài", () => {
    const orphan = n("post", { message: "lạc" });
    const r = computeSchedule([n("start"), orphan], [], NOW, "s");
    expect(r.posts).toEqual([]);
    expect(r.issues[orphan.id]).toMatch(/Chưa nối/);
  });
  it("phát hiện vòng lặp mà không treo", () => {
    const s = n("start"), a = n("post", { message: "a" }), b = n("post", { message: "b" });
    const r = computeSchedule([s, a, b], [{ source: s.id, target: a.id }, { source: a.id, target: b.id }, { source: b.id, target: a.id }], NOW, "s");
    expect(r.posts.length).toBe(2);
    expect(Object.values(r.issues)).toContain("Flow bị lặp vòng tại đây");
  });
  it("giới hạn số bài để tránh flow bùng nổ", () => {
    const f = chain(n("start"), n("repeat", { times: 100, every: 1, unit: "m" }), n("repeat", { times: 100, every: 1, unit: "m" }), n("post", { message: "x" }));
    const r = run(f);
    expect(r.posts.length).toBe(1000);
    expect(r.truncated).toBe(true);
  });
  it("dữ liệu flow cũ (thiếu trường mới) vẫn chạy nhờ giá trị mặc định", () => {
    const old = [
      { id: "s", type: "start", position: { x: 0, y: 0 }, data: { mode: "now", at: null } },
      { id: "b", type: "batch", position: { x: 0, y: 0 }, data: { text: "1\n\n2", photos: [], caption: "", gap: 1, unit: "h" } },
    ];
    const r = computeSchedule(old, [{ source: "s", target: "b" }], NOW, "");
    expect(r.posts.map((p) => p.message)).toEqual(["1", "2"]);
  });
  it("mọi loại khối đều khai báo đủ thành phần", () => {
    for (const [type, def] of Object.entries(NODES)) {
      expect(def.label, type).toBeTruthy();
      expect(typeof def.defaults, type).toBe("function");
      expect(Array.isArray(def.fields), type).toBe(true);
      expect(typeof def.run, type).toBe("function");
      expect(typeof def.summary(def.defaults()) === "string" || def.summary(def.defaults()) === null, type).toBe(true);
    }
  });
});

import { rel } from "./time";
describe("rel()", () => {
  it("không nói 'sau' cho mốc vừa qua", () => {
    expect(rel(new Date(Date.now() - 500))).toBe("vừa xong");
    expect(rel(new Date(Date.now() + 20000))).toBe("sau vài giây");
    expect(rel(new Date(Date.now() + 5 * 60000))).toBe("sau 5 phút");
    expect(rel(new Date(Date.now() - 90 * 60000))).toBe("1 giờ 30 phút trước");
  });
});

import { eventValue } from "./api";
describe("eventValue()", () => {
  it("đọc giá trị ô nhập / checkbox ngay lập tức, giữ nguyên giá trị thô", () => {
    expect(eventValue({ currentTarget: { type: "text", value: "abc" } })).toBe("abc");
    expect(eventValue({ currentTarget: { type: "checkbox", checked: true, value: "on" } })).toBe(true);
    expect(eventValue("08:00")).toBe("08:00");
    expect(eventValue(["1", "2"])).toEqual(["1", "2"]);
    expect(eventValue(null)).toBe(null);
  });
  it("sự kiện đã bị React thu hồi (currentTarget = null) không được lưu nhầm cả object", () => {
    const ev = { currentTarget: { type: "text", value: "x" } };
    const val = eventValue(ev); // đọc ngay trong handler
    ev.currentTarget = null;     // React thu hồi sự kiện
    expect(val).toBe("x");
  });
});
