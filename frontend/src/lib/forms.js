/**
 * Lấy giá trị từ sự kiện onChange (ô nhập, checkbox) hoặc giá trị thô (Select, DatePicker…).
 * Phải gọi NGAY trong handler: React có thể chạy hàm cập nhật state muộn hơn,
 * lúc đó event.currentTarget đã thành null.
 */
export const eventValue = (v) => {
  const t = v?.currentTarget;
  if (!t) return v;
  return t.type === "checkbox" ? t.checked : t.value;
};
