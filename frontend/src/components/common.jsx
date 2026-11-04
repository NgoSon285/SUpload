import { useState } from "react";
import { ActionIcon, Avatar, Box, Card, Group, Loader, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { notifications } from "@mantine/notifications";
import { IconPhoto, IconPhotoPlus, IconUpload, IconX, IconLink, IconWorld, IconClock } from "@tabler/icons-react";

import { imgUrl, uploadImages } from "../lib/api";

export function PageHeader({ title, desc, right }) {
  return (
    <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap">
      <div>
        <Title order={2} fz={24} lh={1.25}>{title}</Title>
        {desc && <Text c="dimmed" mt={4}>{desc}</Text>}
      </div>
      {right}
    </Group>
  );
}

export const notifyOk = (message, title) => notifications.show({ color: "teal", title, message });
export const notifyErr = (message, title = "Có lỗi xảy ra") => notifications.show({ color: "red", title, message });

const IMAGE_MIME = ["image/jpeg", "image/png", "image/gif", "image/webp"];

/** Chọn / kéo thả / dán ảnh, kéo để sắp xếp thứ tự. */
export function PhotoPicker({ value, onChange, compact = false }) {
  const [busy, setBusy] = useState(false);
  const [dragFrom, setDragFrom] = useState(null);

  const add = async (files) => {
    if (!files.length) return;
    setBusy(true);
    try {
      const names = await uploadImages(files);
      onChange([...value, ...names]);
    } catch (e) {
      notifyErr(e.message);
    }
    setBusy(false);
  };

  const move = (from, to) => {
    if (from === to || from === null) return;
    const next = [...value];
    next.splice(to, 0, next.splice(from, 1)[0]);
    onChange(next);
  };

  return (
    <Stack gap="sm">
      <Dropzone
        onDrop={add}
        onReject={() => notifyErr("Chỉ hỗ trợ ảnh JPG, PNG, GIF, WEBP dưới 20 MB")}
        accept={IMAGE_MIME}
        maxSize={20 * 1024 * 1024}
        loading={busy}
        radius="md"
        p={compact ? "sm" : "md"}
      >
        <Group justify="center" gap="sm" mih={compact ? 40 : 64} style={{ pointerEvents: "none" }}>
          <Dropzone.Accept><IconUpload size={26} color="var(--mantine-primary-color-filled)" /></Dropzone.Accept>
          <Dropzone.Reject><IconX size={26} color="var(--mantine-color-red-6)" /></Dropzone.Reject>
          <Dropzone.Idle><IconPhotoPlus size={26} color="var(--mantine-color-dimmed)" stroke={1.6} /></Dropzone.Idle>
          <div>
            <Text size="sm" fw={500}>Kéo thả ảnh vào đây hoặc bấm để chọn</Text>
            {!compact && <Text size="xs" c="dimmed">JPG, PNG, GIF, WEBP · chọn được nhiều ảnh · kéo ảnh bên dưới để đổi thứ tự</Text>}
          </div>
        </Group>
      </Dropzone>

      {value.length > 0 && (
        <SimpleGrid cols={compact ? 4 : { base: 4, xs: 5, md: 6 }} spacing="xs">
          {value.map((p, i) => (
            <div
              key={p + i}
              className={`thumb ${dragFrom === i ? "dragging" : ""}`}
              draggable
              onDragStart={(e) => { setDragFrom(i); e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(i)); }}
              onDragEnd={() => setDragFrom(null)}
              onDragOver={(e) => dragFrom !== null && e.preventDefault()}
              onDrop={(e) => { e.preventDefault(); e.stopPropagation(); move(dragFrom, i); setDragFrom(null); }}
            >
              <img src={imgUrl(p)} alt="" />
              <span className="thumb-i">{i + 1}</span>
              <ActionIcon className="thumb-x" size="sm" radius="xl" color="dark" variant="filled" aria-label="Bỏ ảnh"
                onClick={() => onChange(value.filter((_, j) => j !== i))}>
                <IconX size={12} />
              </ActionIcon>
            </div>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}

export function usePasteImages(onFiles, enabled = true) {
  return (e) => {
    if (!enabled) return;
    const files = [...(e.clipboardData?.files || [])].filter((f) => IMAGE_MIME.includes(f.type));
    if (files.length) {
      e.preventDefault();
      onFiles(files);
    }
  };
}

/** Bản xem trước bài viết (minh hoạ, không mô phỏng giao diện Facebook). */
export function PostPreview({ name, message, link, photos, timeLabel, scheduled }) {
  const n = photos.length;
  const shown = photos.slice(0, Math.min(n, 4));
  const layout = { 1: ["1fr", "auto"], 2: ["1fr 1fr", "220px"], 3: ["2fr 1fr", "140px 140px"], 4: ["1fr 1fr", "140px 140px"] }[shown.length];
  const empty = !message.trim() && !n && !link.trim();
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

export function EmptyState({ icon: Icon = IconPhoto, title, desc, action }) {
  return (
    <Stack align="center" gap={6} py={48} px="md" ta="center">
      <Box p="md" style={{ borderRadius: 16, background: "var(--mantine-color-default-hover)" }}><Icon size={26} stroke={1.6} color="var(--mantine-color-dimmed)" /></Box>
      <Text fw={600} mt="xs">{title}</Text>
      {desc && <Text c="dimmed" size="sm" maw={360}>{desc}</Text>}
      {action && <Box mt="sm">{action}</Box>}
    </Stack>
  );
}

export const Spinner = () => <Group justify="center" py="xl"><Loader /></Group>;
