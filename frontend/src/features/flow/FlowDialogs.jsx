import { useState } from "react";
import { Button, Checkbox, Group, Modal, Paper, SimpleGrid, Stack, Text, TextInput, Textarea, ThemeIcon, UnstyledButton } from "@mantine/core";
import { IconFile, IconTemplate } from "@tabler/icons-react";

const TEMPLATES = [
  { value: "blank", icon: IconFile, title: "Flow trống", desc: "Chỉ có khối Bắt đầu, tự dựng từ đầu." },
  { value: "sample", icon: IconTemplate, title: "Mẫu chiến dịch", desc: "Khung giờ → Định dạng → Bài viết → Chờ → Nhiều bài." },
];

/** Hộp thoại tạo flow mới / đổi tên & mô tả. */
export function FlowFormModal({ opened, mode, initial, onClose, onSubmit }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState("sample");
  const [busy, setBusy] = useState(false);
  const [seen, setSeen] = useState(null);
  if (opened && seen !== initial) {
    // nạp lại giá trị mỗi khi mở hộp thoại
    setSeen(initial);
    setName(initial?.name || "");
    setDescription(initial?.description || "");
    setTemplate("sample");
  }
  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    try { await onSubmit({ name: name.trim(), description: description.trim(), template }); onClose(); }
    finally { setBusy(false); }
  };
  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={600}>{mode === "create" ? "Tạo flow mới" : "Đổi tên & mô tả"}</Text>} centered radius="lg">
      <form onSubmit={submit}>
        <Stack gap="md">
          <TextInput label="Tên flow" placeholder="Ví dụ: Khuyến mãi tháng 12" required data-autofocus maxLength={80}
            value={name} onChange={(e) => setName(e.currentTarget.value)} />
          <Textarea label="Mô tả" placeholder="Mục đích, đối tượng, ghi chú… (không bắt buộc)" autosize minRows={2} maxLength={300}
            value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
          {mode === "create" && (
            <div>
              <Text size="sm" fw={500} mb={6}>Bắt đầu từ</Text>
              <SimpleGrid cols={2} spacing="sm">
                {TEMPLATES.map((t) => (
                  <UnstyledButton key={t.value} onClick={() => setTemplate(t.value)}>
                    <Paper withBorder p="sm" radius="md" className="method-card" data-checked={template === t.value || undefined} h="100%">
                      <ThemeIcon variant={template === t.value ? "filled" : "light"} color={template === t.value ? undefined : "gray"} radius="md" mb={6}><t.icon size={18} /></ThemeIcon>
                      <Text fw={600} size="sm">{t.title}</Text>
                      <Text size="xs" c="dimmed">{t.desc}</Text>
                    </Paper>
                  </UnstyledButton>
                ))}
              </SimpleGrid>
            </div>
          )}
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={onClose}>Huỷ</Button>
            <Button type="submit" loading={busy} disabled={!name.trim()}>{mode === "create" ? "Tạo và mở" : "Lưu"}</Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

/** Hộp thoại xoá flow, hỏi có xoá luôn bài chưa đăng không. */
export function DeleteFlowModal({ flow, onClose, onConfirm }) {
  const [withPosts, setWithPosts] = useState(true);
  const [busy, setBusy] = useState(false);
  const waiting = flow ? (flow.stats?.pending || 0) + (flow.stats?.error || 0) : 0;
  return (
    <Modal opened={!!flow} onClose={onClose} title={<Text fw={600}>Xoá flow “{flow?.name}”?</Text>} centered radius="lg">
      <Stack gap="md">
        <Text size="sm">Flow sẽ bị xoá vĩnh viễn. Các bài đã đăng lên Facebook không bị ảnh hưởng.</Text>
        {waiting > 0 && (
          <Checkbox checked={withPosts} onChange={(e) => setWithPosts(e.currentTarget.checked)}
            label={`Xoá luôn ${waiting} bài chưa đăng do flow này tạo trong Lịch đăng`} />
        )}
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>Huỷ</Button>
          <Button color="red" loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(waiting > 0 && withPosts); onClose(); } finally { setBusy(false); } }}>Xoá flow</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
