import { useState } from "react";
import { ActionIcon, Alert, Avatar, Badge, Button, Group, Menu, Modal, Paper, Stack, Text, TextInput } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconDots, IconPencil, IconPlugConnected, IconStar, IconTrash } from "@tabler/icons-react";

import { pagesApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";
import { KIND_LABEL, pageInitial } from "../../lib/page";
import { when } from "../../lib/time";

function HealthLine({ page }) {
  const h = page.health;
  if (!h) {
    return <Text size="xs" c="dimmed">{page.kind === "api" ? "Chưa kiểm tra kết nối" : "Page qua trình duyệt: bấm Kiểm tra để thử đăng nhập"}</Text>;
  }
  return h.ok
    ? <Text size="xs" c="teal" data-testid="health-ok">● Kết nối tốt · kiểm tra lúc {when(h.checked_at)}</Text>
    : <Text size="xs" c="red" data-testid="health-bad">● {h.error}</Text>;
}

/** Danh sách Page đã kết nối và thao tác trên từng Page. */
export function PagesCard({ pages, perPageToday, dailyMax, onChanged }) {
  const [results, setResults] = useState({}); // {pageId: {color, text}}
  const [renaming, setRenaming] = useState(null);
  const [name, setName] = useState("");

  const test = async (p) => {
    setResults((r) => ({ ...r, [p.id]: { color: "orange", text: "Đang kiểm tra…" } }));
    try {
      const j = await pagesApi.test(p.id);
      setResults((r) => ({ ...r, [p.id]: { color: j.pending ? "orange" : "teal", text: j.text } }));
      onChanged();
    } catch (e) { setResults((r) => ({ ...r, [p.id]: { color: "red", text: e.message } })); }
  };
  const setDefault = async (p) => { await pagesApi.setDefault(p.id); notifyOk(`“${p.name}” là Page mặc định`); onChanged(); };
  const remove = (p) => modals.openConfirmModal({
    title: `Xoá Page “${p.name}”?`,
    children: <Text size="sm">Ứng dụng sẽ không đăng lên Page này nữa. Bài đã đăng trên Facebook không bị ảnh hưởng.</Text>,
    labels: { confirm: "Xoá Page", cancel: "Huỷ" }, confirmProps: { color: "red" },
    onConfirm: async () => {
      try { await pagesApi.remove(p.id); notifyOk("Đã xoá Page"); onChanged(); }
      catch (e) { notifyErr(e.message, "Chưa xoá được Page"); }
    },
  });
  const saveName = async () => {
    try { await pagesApi.edit(renaming.id, { name }); setRenaming(null); onChanged(); }
    catch (e) { notifyErr(e.message); }
  };

  if (!pages.length) {
    return <Alert color="indigo" variant="light" icon={<IconPlugConnected />}>Chưa kết nối Page nào. Thêm Page ở mục bên dưới để bắt đầu đăng bài.</Alert>;
  }
  return (
    <Stack gap="xs">
      {pages.map((p) => (
        <Paper key={p.id} withBorder p="sm" radius="md" data-testid="page-row">
          <Group justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap" style={{ minWidth: 0 }}>
              <Avatar radius="xl" variant="gradient" gradient={{ from: "indigo", to: "violet" }}>{pageInitial(p)}</Avatar>
              <div style={{ minWidth: 0 }}>
                <Group gap={6} wrap="nowrap">
                  <Text fw={600} size="sm" truncate>{p.name}</Text>
                  {p.default && <Badge size="xs" color="teal" variant="light">Mặc định</Badge>}
                </Group>
                <Text size="xs" c="dimmed" truncate>
                  {KIND_LABEL[p.kind]} · {p.kind === "api" ? `ID ${p.fb_page_id}` : p.url}
                  {" · "}hôm nay {perPageToday?.[p.id] ?? 0}{dailyMax ? `/${dailyMax}` : ""} bài
                </Text>
                <HealthLine page={p} />
              </div>
            </Group>
            <Group gap={4} wrap="nowrap">
              <Button size="xs" variant="default" leftSection={<IconPlugConnected size={14} />} onClick={() => test(p)}>Kiểm tra</Button>
              <Menu position="bottom-end" withinPortal>
                <Menu.Target><ActionIcon variant="subtle" color="gray" aria-label={`Thao tác với Page ${p.name}`}><IconDots size={18} /></ActionIcon></Menu.Target>
                <Menu.Dropdown>
                  {!p.default && <Menu.Item leftSection={<IconStar size={16} />} onClick={() => setDefault(p)}>Đặt làm mặc định</Menu.Item>}
                  <Menu.Item leftSection={<IconPencil size={16} />} onClick={() => { setRenaming(p); setName(p.name); }}>Đổi tên hiển thị</Menu.Item>
                  <Menu.Divider />
                  <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={() => remove(p)}>Xoá Page</Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
          {results[p.id] && <Alert mt="xs" py={6} variant="light" color={results[p.id].color}><Text size="sm">{results[p.id].text}</Text></Alert>}
        </Paper>
      ))}
      <Text size="xs" c="dimmed">Bài và flow không chọn Page riêng sẽ đăng lên Page mặc định.</Text>

      <Modal opened={!!renaming} onClose={() => setRenaming(null)} title={<Text fw={600}>Đổi tên hiển thị</Text>} centered radius="lg">
        <Stack>
          <TextInput label="Tên" value={name} onChange={(e) => setName(e.currentTarget.value)} data-autofocus maxLength={80} />
          <Group justify="flex-end"><Button variant="default" onClick={() => setRenaming(null)}>Huỷ</Button><Button onClick={saveName} disabled={!name.trim()}>Lưu</Button></Group>
        </Stack>
      </Modal>
    </Stack>
  );
}

