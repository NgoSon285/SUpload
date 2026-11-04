import { Card, Text, Timeline, ThemeIcon } from "@mantine/core";
import { IconAlertTriangle, IconCheck, IconInfoCircle, IconListDetails } from "@tabler/icons-react";

import { useApp } from "../App";
import { when } from "../lib/time";
import { EmptyState, PageHeader } from "../components/common";

const LV = {
  ok: { color: "teal", icon: IconCheck },
  error: { color: "red", icon: IconAlertTriangle },
  info: { color: "gray", icon: IconInfoCircle },
};

export default function Log() {
  const { state } = useApp();
  const log = state.log;
  return (
    <>
      <PageHeader title="Nhật ký" desc="Mọi hoạt động của ứng dụng, mới nhất ở trên." />
      <Card p="lg" maw={900}>
        {!log.length ? (
          <EmptyState icon={IconListDetails} title="Chưa có hoạt động" desc="Nhật ký sẽ ghi lại mọi lần đăng bài và thay đổi cài đặt." />
        ) : (
          <Timeline bulletSize={26} lineWidth={2}>
            {log.map((l, i) => {
              const { color, icon: Icon } = LV[l.level] || LV.info;
              return (
                <Timeline.Item key={i} bullet={<ThemeIcon size={26} radius="xl" color={color} variant="light"><Icon size={14} /></ThemeIcon>}>
                  <Text size="sm" c={l.level === "error" ? "red" : undefined}>{l.text}</Text>
                  <Text size="xs" c="dimmed" mt={2}>{when(l.at)}</Text>
                </Timeline.Item>
              );
            })}
          </Timeline>
        )}
      </Card>
    </>
  );
}
