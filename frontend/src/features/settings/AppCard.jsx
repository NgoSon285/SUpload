import { useEffect, useState } from "react";
import { Button, Code, Group, Stack, Switch, Text } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconPower } from "@tabler/icons-react";

import { systemApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";

/** Phiên bản, nơi lưu dữ liệu, tự khởi động cùng Windows, tắt ứng dụng. */
export function AppCard() {
  const [info, setInfo] = useState(null);
  const load = () => systemApi.info().then(setInfo, () => {});
  useEffect(() => { load(); }, []);

  const toggle = async (on) => {
    try {
      await systemApi.setAutostart(on);
      notifyOk(on ? "SUpload sẽ tự chạy ẩn mỗi khi bạn đăng nhập Windows" : "Đã tắt tự khởi động");
      load();
    } catch (e) { notifyErr(e.message); }
  };
  const shutdown = () => modals.openConfirmModal({
    title: "Tắt SUpload?",
    children: <Text size="sm">Ứng dụng sẽ dừng hẳn: bài hẹn giờ chưa giao cho Facebook sẽ không được đăng cho tới khi bạn mở lại.</Text>,
    labels: { confirm: "Tắt ứng dụng", cancel: "Huỷ" }, confirmProps: { color: "red" },
    onConfirm: async () => { await systemApi.shutdown(); notifyOk("Đã tắt SUpload. Có thể đóng tab này."); },
  });

  if (!info) return null;
  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">
        Phiên bản {info.version}{info.frozen ? " (bản đóng gói)" : ""} · dữ liệu lưu tại <Code>{info.data_dir}</Code>
      </Text>
      <Switch
        label="Khởi động cùng Windows" data-testid="autostart"
        description={info.autostart.supported
          ? "Tự chạy ẩn (không cửa sổ, không mở trình duyệt) mỗi khi đăng nhập Windows, để bài hẹn giờ luôn được đăng. Mở giao diện tại http://127.0.0.1:5000."
          : "Chỉ hỗ trợ trên Windows."}
        checked={info.autostart.enabled} disabled={!info.autostart.supported} onChange={(e) => toggle(e.currentTarget.checked)}
      />
      <Group>
        <Button variant="default" color="red" leftSection={<IconPower size={16} />} onClick={shutdown}>Tắt ứng dụng</Button>
        <Text size="xs" c="dimmed">Dùng khi SUpload đang chạy ẩn (không có cửa sổ để nhấn Ctrl+C).</Text>
      </Group>
    </Stack>
  );
}
