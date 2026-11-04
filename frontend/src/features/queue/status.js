/** Trạng thái bài viết & thời điểm đăng dự kiến (khớp supload/domain/posts.py). */
export const STATUS = {
  pending: { label: "Đang chờ", color: "indigo" },
  running: { label: "Đang đăng", color: "orange" },
  scheduled: { label: "Đã hẹn trên Facebook", color: "cyan" },
  done: { label: "Đã đăng", color: "teal" },
  error: { label: "Lỗi", color: "red" },
};

export const isUpcoming = (p) => p.status === "pending" || p.status === "running" || p.status === "scheduled";

/** Thời điểm bài sẽ thực sự lên (đã tính giới hạn an toàn), hoặc null nếu đăng ngay khi đến lượt. */
export function upcomingTime(p) {
  if (p.status === "scheduled") return p.fb_scheduled_at;
  if (p.status === "running") return null;
  const t = p.effective_at || p.scheduled_at;
  return t && new Date(t) > new Date(Date.now() + 30000) ? t : null;
}
