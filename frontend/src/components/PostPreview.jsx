import { Avatar, Card, Group, Text } from "@mantine/core";
import { IconClock, IconLink, IconWorld } from "@tabler/icons-react";

import { imgUrl } from "../api/client";

/** Bản xem trước bài viết (minh hoạ, không mô phỏng giao diện Facebook). */
export function PostPreview({ name, message, link, photos, timeLabel, scheduled, video, video_kind: videoKind }) {
  const n = photos.length;
  const shown = photos.slice(0, Math.min(n, 4));
  const layout = { 1: ["1fr", "auto"], 2: ["1fr 1fr", "220px"], 3: ["2fr 1fr", "140px 140px"], 4: ["1fr 1fr", "140px 140px"] }[shown.length];
  const empty = !message.trim() && !n && !link.trim() && !video;
  return (
    <Card p={0}>
      <Group p="md" gap="sm">
        <Avatar radius="xl" variant="gradient" gradient={{ from: "indigo", to: "violet" }}>{(name || "P")[0].toUpperCase()}</Avatar>
        <div>
          <Text fw={600} size="sm">{name || "Page của bạn"}</Text>
          <Group gap={4} c="dimmed">
            {scheduled ? <IconClock size={12} /> : <IconWorld size={12} />}
            <Text size="xs">{timeLabel}</Text>
          </Group>
        </div>
      </Group>
      {(message.trim() || empty) && (
        <Text px="md" pb="md" style={{ whiteSpace: "pre-wrap" }} c={empty ? "dimmed" : undefined} fz="sm">
          {empty ? "Nội dung bài viết sẽ hiển thị ở đây…" : message}
        </Text>
      )}
      {link.trim() && (
        <Group mx="md" mb="md" p="xs" gap="xs" wrap="nowrap" style={{ border: "1px solid var(--mantine-color-default-border)", borderRadius: 8 }}>
          <IconLink size={16} />
          <Text size="sm" c="dimmed" truncate>{link.replace(/^https?:\/\//, "")}</Text>
        </Group>
      )}
      {video && (
        <div style={{ background: "#000", display: "flex", justifyContent: "center" }}>
          <video src={imgUrl(video)} controls style={{ maxHeight: 420, width: videoKind === "reel" ? "auto" : "100%", aspectRatio: videoKind === "reel" ? "9 / 16" : undefined }} />
        </div>
      )}
      {shown.length > 0 && (
        <div className="pv-grid" style={{ gridTemplateColumns: layout[0], gridTemplateRows: layout[1] }}>
          {shown.map((p, i) => (
            <div key={p + i} style={shown.length === 3 && i === 0 ? { gridRow: "span 2" } : undefined}>
              <img src={imgUrl(p)} alt="" style={shown.length === 1 ? { maxHeight: 420 } : undefined} />
              {i === 3 && n > 4 && <span className="pv-more">+{n - 4}</span>}
            </div>
          ))}
        </div>
      )}
      <Group justify="space-around" py={6} c="dimmed" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
        {["Thích", "Bình luận", "Chia sẻ"].map((t) => <Text key={t} size="sm" fw={500} p={6}>{t}</Text>)}
      </Group>
    </Card>
  );
}
