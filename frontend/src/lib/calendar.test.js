import { describe, expect, it } from "vitest";
import { eventTime, monthGrid, moveKeepingTime, startOfWeek, weekGrid } from "./calendar";

describe("lịch", () => {
  it("tuần bắt đầu từ Thứ Hai, kể cả khi hôm nay là Chủ nhật", () => {
    expect(startOfWeek(new Date(2026, 10, 8)).toDate()).toEqual(new Date(2026, 10, 2)); // CN 8/11 -> T2 2/11
    expect(startOfWeek(new Date(2026, 10, 2, 15)).toDate()).toEqual(new Date(2026, 10, 2));
  });
  it("lưới tháng 42 ô, chứa trọn tháng", () => {
    const g = monthGrid(new Date(2026, 10, 15)); // tháng 11/2026 bắt đầu Chủ nhật
    expect(g).toHaveLength(42);
    expect(g[0]).toEqual(new Date(2026, 9, 26));     // T2 26/10
    expect(g.some((d) => +d === +new Date(2026, 10, 30))).toBe(true);
  });
  it("lưới tuần 7 ngày", () => {
    const w = weekGrid(new Date(2026, 10, 4));
    expect(w.map((d) => d.getDate())).toEqual([2, 3, 4, 5, 6, 7, 8]);
  });
  it("dời ngày giữ nguyên giờ", () => {
    expect(moveKeepingTime(new Date(2026, 10, 4, 20, 30), new Date(2026, 10, 9))).toEqual(new Date(2026, 10, 9, 20, 30));
  });
  it("giờ hiển thị theo trạng thái", () => {
    expect(eventTime({ status: "scheduled", fb_scheduled_at: "A", effective_at: "B" })).toBe("A");
    expect(eventTime({ status: "pending", effective_at: "B", scheduled_at: "C" })).toBe("B");
    expect(eventTime({ status: "done", done_at: "D" })).toBe("D");
  });
});
