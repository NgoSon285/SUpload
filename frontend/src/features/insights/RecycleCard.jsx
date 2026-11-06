import { useEffect, useState } from "react";
import { Badge, Button, Card, Group, Image, Paper, Select, Stack, Switch, Text } from "@mantine/core";
import { IconRecycle } from "@tabler/icons-react";

import { imgUrl } from "../../api/client";
import { recycleApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";
import { when } from "../../lib/time";

const AFTER = [{ value: "14", label: "Sau 14 ngày" }, { value: "30", label: "Sau 30 ngày" }, { value: "60", label: "Sau 60 ngày" }, { value: "90", label: "Sau 90 ngày" }];
const PER_WEEK = [{ value: "1", label: "1 bài/tuần" }, { value: "2", label: "2 bài/tuần" }, { value: "3", label: "3 bài/tuần" }, { value: "7", label: "Mỗi ngày" }];

/** Tự đăng lại bài hiệu quả: cấu hình + bài sẽ được đăng lại kế tiếp của từng Page. */
export function RecycleCard({ onPosted }) {
  const [data, setData] = useState(null);
  const load = () => recycleApi.get().then(setData, (e) => notifyErr(e.message));
  useEffect(() => { load(); }, []);
  if (!data) return null;
  const cfg = data.config;
  const save = async (patch) => {
    try { const r = await recycleApi.saveConfig({ ...cfg, ...patch }); setData((d) => ({ ...d, config: r.config })); load(); }
    catch (e) { notifyErr(e.message); }
  };
  const runNow = async (page) => {
    try { const r = await recycleApi.run(page); notifyOk(`Đã đưa vào lịch đăng lúc ${when(r.post.scheduled_at)}`); load(); onPosted?.(); }
    catch (e) { notifyErr(e.message); }
  };
  return (
    <Card p="lg" data-testid="recycle-card">
      <Group justify="space-between" align="flex-start" mb="sm" wrap="wrap">
        <div>
          <Group gap={8}><IconRecycle size={18} /><Text fw={600}>Tự đăng lại bài hiệu quả</Text>
            <Badge size="sm" color={cfg.enabled ? "teal" : "gray"} variant="light">{cfg.enabled ? "Đang bật" : "Đang tắt"}</Badge></Group>
          <Text size="sm" c="dimmed" maw={620}>Chọn bài có tương tác từ mức trung bình trở lên, đã đăng đủ lâu, rồi đưa lại vào lịch vào giờ hiệu quả nhất của Page. Bài đăng lại vẫn theo giới hạn an toàn.</Text>
        </div>
        <Switch checked={cfg.enabled} onChange={(e) => save({ enabled: e.currentTarget.checked })} label="Bật" aria-label="Bật tự đăng lại" />
      </Group>
      <Group gap="sm" mb="md" wrap="wrap">
        <Select w={150} data={AFTER} value={String(cfg.after_days)} onChange={(v) => save({ after_days: Number(v) })} allowDeselect={false} comboboxProps={{ withinPortal: true }} aria-label="Đăng lại sau" />
        <Select w={150} data={PER_WEEK} value={String(cfg.per_week)} onChange={(v) => save({ per_week: Number(v) })} allowDeselect={false} comboboxProps={{ withinPortal: true }} aria-label="Số bài mỗi tuần" />
        <Switch checked={cfg.rewrite} onChange={(e) => save({ rewrite: e.currentTarget.checked })} label="Nhờ AI viết lại cho đỡ trùng" />
      </Group>
      <Stack gap="xs">
        {data.pages.map((pg) => (
          <Paper key={pg.page} withBorder p="sm" radius="md">
            <Group justify="space-between" wrap="nowrap" gap="sm">
              <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
                {pg.next?.photos?.[0] && <Image src={imgUrl(pg.next.photos[0])} w={40} h={40} radius="sm" />}
                <div style={{ minWidth: 0 }}>
                  <Text size="xs" c="dimmed">{pg.name}{pg.last_at ? ` · lần gần nhất ${when(pg.last_at)}` : ""}</Text>
                  <Text size="sm" lineClamp={1}>{pg.next ? `Bài kế tiếp: ${pg.next.message || (pg.next.video ? "Video" : "Bài có ảnh")}` : "Chưa có bài đủ điều kiện"}</Text>
                  {pg.next && <Text size="xs" c="dimmed">{pg.next.engagement} tương tác · đăng {when(pg.next.done_at)}</Text>}
                </div>
              </Group>
              <Button size="xs" variant="light" disabled={!pg.next} onClick={() => runNow(pg.page)}>Đăng lại ngay</Button>
            </Group>
          </Paper>
        ))}
      </Stack>
    </Card>
  );
}
