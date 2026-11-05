import { useState } from "react";
import { ActionIcon, Group, Stack, Text } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconMovie, IconUpload, IconX } from "@tabler/icons-react";

import { imgUrl } from "../api/client";
import { mediaApi } from "../api/endpoints";
import { notifyErr } from "./notify";

const VIDEO_MIME = ["video/mp4", "video/quicktime", "video/webm", "video/x-m4v"];

/** Chọn / kéo thả MỘT video (video thường hoặc Reels). */
export function VideoPicker({ value, onChange, reel = false }) {
  const [busy, setBusy] = useState(false);
  const add = async ([f]) => {
    if (!f) return;
    setBusy(true);
    try { onChange((await mediaApi.upload([f]))[0]); } catch (e) { notifyErr(e.message); }
    setBusy(false);
  };
  if (value) {
    return (
      <div style={{ position: "relative", maxWidth: reel ? 260 : "100%" }} data-testid="video-preview">
        <video src={imgUrl(value)} controls style={{ width: "100%", maxHeight: 360, borderRadius: 10, background: "#000", aspectRatio: reel ? "9 / 16" : undefined }} />
        <ActionIcon pos="absolute" top={6} right={6} radius="xl" color="dark" variant="filled" onClick={() => onChange("")} aria-label="Bỏ video"><IconX size={14} /></ActionIcon>
      </div>
    );
  }
  return (
    <Stack gap={4}>
      <Dropzone onDrop={add} onReject={() => notifyErr("Chỉ hỗ trợ video MP4, MOV, WEBM dưới 1 GB")} accept={VIDEO_MIME} maxSize={1024 ** 3}
        multiple={false} loading={busy} radius="md" data-testid="video-drop">
        <Group justify="center" gap="sm" mih={64} style={{ pointerEvents: "none" }}>
          <Dropzone.Accept><IconUpload size={26} /></Dropzone.Accept>
          <Dropzone.Reject><IconX size={26} /></Dropzone.Reject>
          <Dropzone.Idle><IconMovie size={26} color="var(--mantine-color-dimmed)" stroke={1.6} /></Dropzone.Idle>
          <div>
            <Text size="sm" fw={500}>Kéo thả video vào đây hoặc bấm để chọn</Text>
            <Text size="xs" c="dimmed">MP4, MOV, WEBM · tối đa 1 GB</Text>
          </div>
        </Group>
      </Dropzone>
      {reel && <Text size="xs" c="dimmed">Reels: video dọc 9:16, dài 3–90 giây (Facebook sẽ từ chối nếu không đúng).</Text>}
    </Stack>
  );
}
