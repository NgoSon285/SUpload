/** Tính toán ngày cho chế độ xem Lịch (tuần bắt đầu từ Thứ Hai). */
import dayjs from "dayjs";

export const startOfWeek = (d) => {
  const x = dayjs(d).startOf("day");
  return x.subtract((x.day() + 6) % 7, "day"); // Thứ Hai
};

/** 42 ngày (6 tuần) hiển thị cho tháng chứa `d`. */
export const monthGrid = (d) => {
  const first = startOfWeek(dayjs(d).startOf("month"));
  return Array.from({ length: 42 }, (_, i) => first.add(i, "day").toDate());
};

/** 7 ngày của tuần chứa `d`. */
export const weekGrid = (d) => {
  const first = startOfWeek(d);
  return Array.from({ length: 7 }, (_, i) => first.add(i, "day").toDate());
};

export const sameDay = (a, b) => dayjs(a).isSame(b, "day");

/** Dời sang ngày `day` nhưng giữ nguyên giờ:phút của `time`. */
export const moveKeepingTime = (time, day) => {
  const t = dayjs(time);
  return dayjs(day).hour(t.hour()).minute(t.minute()).second(0).millisecond(0).toDate();
};

/** Thời điểm hiển thị bài trên lịch (khớp trạng thái máy chủ). */
export const eventTime = (p) => {
  if (p.status === "scheduled") return p.fb_scheduled_at;
  if (p.status === "done" || p.status === "error") return p.done_at || p.created_at;
  return p.effective_at || p.scheduled_at || p.created_at;
};

export const MOVABLE = new Set(["pending", "scheduled", "error"]);
