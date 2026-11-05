import { useEffect, useState } from "react";
import { Badge, Button, Group, Modal, SimpleGrid, Text, UnstyledButton } from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

import { imgUrl } from "../api/client";
import { mediaApi } from "../api/endpoints";
import { EmptyState } from "./EmptyState";

/** Chọn lại ảnh đã tải lên trước đây (thư viện ảnh). */
export function MediaPicker({ opened, onClose, onPick, exclude = [] }) {
  const [media, setMedia] = useState(null);
  const [picked, setPicked] = useState([]);
  useEffect(() => {
    if (!opened) return;
    setPicked([]);
    mediaApi.list().then((m) => setMedia(m.filter((x) => x.kind === "image" && !exclude.includes(x.name))), () => setMedia([]));
  }, [opened]); // eslint-disable-line
  const toggle = (name) => setPicked((p) => (p.includes(name) ? p.filter((x) => x !== name) : [...p, name]));
  return (
    <Modal opened={opened} onClose={onClose} size="lg" radius="lg" title={<Text fw={600}>Chọn ảnh đã tải lên</Text>}>
      {media && !media.length ? (
        <EmptyState title="Chưa có ảnh nào" desc="Ảnh bạn tải lên khi soạn bài sẽ được lưu ở đây để dùng lại." />
      ) : (
        <SimpleGrid cols={{ base: 3, sm: 5 }} spacing="xs" data-testid="media-picker">
          {(media || []).map((m) => (
            <UnstyledButton key={m.name} onClick={() => toggle(m.name)} className="thumb" style={{ outline: picked.includes(m.name) ? "3px solid var(--mantine-primary-color-filled)" : undefined }} aria-label={m.name}>
              <img src={imgUrl(m.name)} alt="" />
              {picked.includes(m.name) && <span className="thumb-i"><IconCheck size={10} /> {picked.indexOf(m.name) + 1}</span>}
              {m.used > 0 && <Badge size="xs" pos="absolute" top={4} right={4} variant="filled" color="dark">dùng {m.used}</Badge>}
            </UnstyledButton>
          ))}
        </SimpleGrid>
      )}
      <Group justify="flex-end" mt="md">
        <Button variant="default" onClick={onClose}>Huỷ</Button>
        <Button disabled={!picked.length} onClick={() => { onPick(picked); onClose(); }}>Thêm {picked.length || ""} ảnh</Button>
      </Group>
    </Modal>
  );
}
