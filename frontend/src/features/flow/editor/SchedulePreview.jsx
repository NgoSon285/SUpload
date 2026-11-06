import { Alert, Badge, Group, Image, Paper, Stack, Text, Timeline } from "@mantine/core";
import { IconCalendarEvent, IconClock } from "@tabler/icons-react";

import { imgUrl } from "../../../api/client";
import { EmptyState } from "../../../components";
import { dayLabel, hm, when } from "../../../lib/time";

/** Thẻ "Lịch dự kiến": danh sách bài flow sẽ tạo, theo thời gian. */
export function SchedulePreview({ schedule, onPick }) {
  const { posts, truncated } = schedule;
  if (!posts.length) return <EmptyState icon={IconCalendarEvent} title="Chưa có bài nào" desc="Thêm khối Bài viết hoặc Nhiều bài và nối với khối Bắt đầu." />;
  const first = posts[0].time, last = posts[posts.length - 1].time;
  return (
    <Stack p="md" gap="md">
      <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default-hover)">
        <Text fw={600}>{posts.length} bài sẽ được lên lịch</Text>
        <Text size="sm" c="dimmed">Từ {when(first)} đến {when(last)}</Text>
      </Paper>
      {truncated && <Alert color="orange" variant="light" py="xs">Flow tạo quá nhiều bài, chỉ hiển thị 1.000 bài đầu.</Alert>}
      <Timeline bulletSize={22} lineWidth={2}>
        {posts.slice(0, 200).map((p, i) => (
          <Timeline.Item key={i} bullet={<IconClock size={12} />} title={<Text size="sm" fw={600}>{hm(p.time)} · {dayLabel(p.time)}</Text>}>
            <Group gap="xs" wrap="nowrap" mt={4} style={{ cursor: "pointer" }} onClick={() => onPick(p.nodeId)}>
              {p.photos[0] && <Image src={imgUrl(p.photos[0])} w={36} h={36} radius="sm" />}
              {p.video && <Badge size="xs" variant="light" color={p.video_kind === "reel" ? "violet" : "blue"} style={{ flex: "none" }}>{p.video_kind === "reel" ? "Reels" : "Video"}</Badge>}
              <Text size="xs" c="dimmed" lineClamp={3} style={{ whiteSpace: "pre-wrap" }}>{p.message || (p.video ? "Chỉ có video" : p.photos.length ? "Bài chỉ có ảnh" : p.link)}</Text>
            </Group>
          </Timeline.Item>
        ))}
      </Timeline>
      {posts.length > 200 && <Text size="xs" c="dimmed">… và {posts.length - 200} bài nữa</Text>}
    </Stack>
  );
}
