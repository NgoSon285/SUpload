import { notifications } from "@mantine/notifications";

export const notifyOk = (message, title) => notifications.show({ color: "teal", title, message });
export const notifyErr = (message, title = "Có lỗi xảy ra") => notifications.show({ color: "red", title, message });
