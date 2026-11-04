import { describe, expect, it } from "vitest";

import { rel } from "./time";
describe("rel()", () => {
  it("không nói 'sau' cho mốc vừa qua", () => {
    expect(rel(new Date(Date.now() - 500))).toBe("vừa xong");
    expect(rel(new Date(Date.now() + 20000))).toBe("sau vài giây");
    expect(rel(new Date(Date.now() + 5 * 60000))).toBe("sau 5 phút");
    expect(rel(new Date(Date.now() - 90 * 60000))).toBe("1 giờ 30 phút trước");
  });
});

import { eventValue } from "./forms";
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
