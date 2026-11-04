/** localStorage an toàn (trình duyệt chặn lưu trữ thì trả giá trị mặc định). */
export const storage = {
  get(k, fallback = null) {
    try {
      const v = localStorage.getItem(k);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* trình duyệt chặn lưu trữ */
    }
  },
};
