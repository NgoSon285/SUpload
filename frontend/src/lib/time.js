import dayjs from "dayjs";
import "dayjs/locale/vi";

dayjs.locale("vi");

const DOW = ["Chủ nhật", "Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy"];

export const hm = (d) => dayjs(d).format("HH:mm");

export function dayLabel(d) {
  const x = dayjs(d);
  const today = dayjs();
  if (x.isSame(today, "day")) return "Hôm nay";
  if (x.isSame(today.add(1, "day"), "day")) return "Ngày mai";
  if (x.isSame(today.subtract(1, "day"), "day")) return "Hôm qua";
  return `${DOW[x.day()]}, ${x.format("D/M")}`;
}

export const when = (d) => `${hm(d)} · ${dayLabel(d)}`;

export function rel(d) {
  const m = Math.round((new Date(d) - Date.now()) / 60000);
  const a = Math.abs(m);
  let s;
  if (a < 1) s = "vài giây";
  else if (a < 60) s = `${a} phút`;
  else if (a < 1440) s = `${Math.floor(a / 60)} giờ${a % 60 ? ` ${a % 60} phút` : ""}`;
  else s = `${Math.round(a / 1440)} ngày`;
  return m >= 0 ? `sau ${s}` : `${s} trước`;
}

/** "YYYY-MM-DDTHH:mm" theo giờ máy, dùng để gửi lên server */
export const toLocalIso = (d) => dayjs(d).format("YYYY-MM-DDTHH:mm");

export function presetTimes() {
  const at = (offset, h) => dayjs().add(offset, "day").hour(h).minute(0).second(0).millisecond(0).toDate();
  const list = [
    ["Sau 1 giờ", dayjs().add(1, "hour").second(0).millisecond(0).toDate()],
    ["12:00 trưa nay", at(0, 12)],
    ["20:00 tối nay", at(0, 20)],
    ["8:00 sáng mai", at(1, 8)],
    ["20:00 tối mai", at(1, 20)],
  ];
  return list.filter(([, d]) => d - Date.now() > 60000);
}

export const UNITS = [
  { value: "m", label: "phút", ms: 60000 },
  { value: "h", label: "giờ", ms: 3600000 },
  { value: "d", label: "ngày", ms: 86400000 },
];
export const unitMs = (u) => (UNITS.find((x) => x.value === u) || UNITS[0]).ms;
export const unitLabel = (u) => (UNITS.find((x) => x.value === u) || UNITS[0]).label;
