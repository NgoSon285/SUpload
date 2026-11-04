import { useState } from "react";
import { ActionIcon, Group, SimpleGrid, Stack, Text } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconPhotoPlus, IconUpload, IconX } from "@tabler/icons-react";

import { imgUrl } from "../api/client";
import { mediaApi } from "../api/endpoints";
import { notifyErr } from "./notify";

const IMAGE_MIME = ["image/jpeg", "image/png", "image/gif", "image/webp"];

/** Chọn / kéo thả / dán ảnh, kéo để sắp xếp thứ tự. */
export function PhotoPicker({ value, onChange, compact = false }) {
  const [busy, setBusy] = useState(false);
  const [dragFrom, setDragFrom] = useState(null);

  const add = async (files) => {
    if (!files.length) return;
    setBusy(true);
    try {
      const names = await mediaApi.upload(files);
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
