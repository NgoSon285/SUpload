import { useMemo, useState } from "react";
import {
  ActionIcon, Badge, Button, Card, Checkbox, FileButton, Group, Menu, Modal, Paper, SegmentedControl, SimpleGrid, Stack,
  Text, TextInput, Textarea, ThemeIcon, Tooltip, UnstyledButton,
} from "@mantine/core";
import {
  IconCopy, IconDots, IconDownload, IconFile, IconPencil, IconPlayerPlay, IconPlus, IconSearch, IconSitemap, IconTemplate,
  IconTrash, IconUpload, IconCalendarEvent, IconClock,
} from "@tabler/icons-react";

import { computeSchedule } from "../lib/flow";
import { nodeDef } from "../lib/nodes";
import { rel, when } from "../lib/time";
import { EmptyState, PageHeader } from "./common";

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

function FlowCard({ flow, onOpen, onEdit, onDuplicate, onExport, onDelete }) {
  const planned = useMemo(() => computeSchedule(flow.nodes || [], flow.edges || [], new Date(), flow.seed || flow.id).posts.length, [flow]);
  const st = flow.stats || {};
  const types = (flow.nodes || []).map((n) => n.type);
  const [menu, setMenu] = useState(false);
  const act = (fn) => () => { setMenu(false); fn(); }; // đóng menu trước khi thao tác
  return (
    <Card p="md" className="flow-card" data-testid="flow-card">
      <Stack gap="sm" h="100%">
        <Group justify="space-between" wrap="nowrap" align="flex-start">
          <UnstyledButton onClick={onOpen} style={{ minWidth: 0, flex: 1 }}>
            <Group gap="sm" wrap="nowrap">
              <ThemeIcon size={36} radius="md" variant="light"><IconSitemap size={19} /></ThemeIcon>
              <div style={{ minWidth: 0 }}>
                <Text fw={600} truncate>{flow.name}</Text>
                <Text size="xs" c="dimmed">Sửa {rel(flow.updated_at)}</Text>
              </div>
            </Group>
          </UnstyledButton>
          <Menu position="bottom-end" withinPortal opened={menu} onChange={setMenu}>
            <Menu.Target><ActionIcon variant="subtle" color="gray" aria-label={`Thao tác với ${flow.name}`}><IconDots size={18} /></ActionIcon></Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconSitemap size={16} />} onClick={act(onOpen)}>Mở trình dựng</Menu.Item>
              <Menu.Item leftSection={<IconPencil size={16} />} onClick={act(onEdit)}>Đổi tên & mô tả</Menu.Item>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={act(onDuplicate)}>Nhân bản</Menu.Item>
              <Menu.Item leftSection={<IconDownload size={16} />} onClick={act(onExport)}>Xuất file</Menu.Item>
              <Menu.Divider />
              <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={act(onDelete)}>Xoá</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>

        <Text size="sm" c={flow.description ? undefined : "dimmed"} lineClamp={2} mih={40}>{flow.description || "Chưa có mô tả"}</Text>

        <Group gap={4}>
          {types.slice(0, 10).map((t, i) => {
            const d = nodeDef(t);
            return <Tooltip key={i} label={d.label}><ThemeIcon size={22} radius="sm" variant="light" color={d.color}><d.icon size={13} /></ThemeIcon></Tooltip>;
          })}
          {types.length > 10 && <Text size="xs" c="dimmed">+{types.length - 10}</Text>}
        </Group>

        <Group gap={6}>
          <Badge variant="light" color="gray" style={{ textTransform: "none" }}>{types.length} khối</Badge>
          <Badge variant="light" style={{ textTransform: "none" }}>{planned} bài dự kiến</Badge>
          {st.pending > 0 && <Badge variant="light" color="indigo" leftSection={<IconClock size={11} />} style={{ textTransform: "none" }}>{st.pending} đang chờ</Badge>}
          {st.done > 0 && <Badge variant="light" color="teal" style={{ textTransform: "none" }}>{st.done} đã đăng</Badge>}
          {st.error > 0 && <Badge variant="light" color="red" style={{ textTransform: "none" }}>{st.error} lỗi</Badge>}
        </Group>

        <Group justify="space-between" mt="auto" pt="xs" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
          <Group gap={4} c="dimmed">
            <IconPlayerPlay size={13} />
            <Text size="xs">{flow.last_run_at ? `Chạy ${when(flow.last_run_at)} · ${flow.last_run_count} bài` : "Chưa chạy lần nào"}</Text>
          </Group>
          <Button size="compact-sm" variant="light" onClick={onOpen}>Mở</Button>
        </Group>
      </Stack>
    </Card>
  );
}

export function FlowList({ flows, onOpen, onCreate, onEdit, onDuplicate, onExport, onDelete, onImport }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("updated");
  const list = useMemo(() => {
    const k = q.trim().toLowerCase();
    const out = flows.filter((f) => !k || f.name.toLowerCase().includes(k) || (f.description || "").toLowerCase().includes(k));
    const by = {
      updated: (a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""),
      name: (a, b) => a.name.localeCompare(b.name, "vi"),
      run: (a, b) => (b.last_run_at || "").localeCompare(a.last_run_at || ""),
    }[sort];
    return [...out].sort(by);
  }, [flows, q, sort]);

  return (
    <>
      <PageHeader
        title="Flow chiến dịch"
        desc="Mỗi flow là một kịch bản đăng bài có thể dùng lại. Tạo bao nhiêu flow tuỳ ý."
        right={
          <Group gap="xs">
            <FileButton onChange={(f) => f && onImport(f)} accept="application/json,.json">
              {(props) => <Button variant="default" leftSection={<IconUpload size={16} />} {...props}>Nhập file</Button>}
            </FileButton>
            <Button leftSection={<IconPlus size={16} />} onClick={onCreate}>Tạo flow</Button>
          </Group>
        }
      />

      {flows.length === 0 ? (
        <Card>
          <EmptyState icon={IconSitemap} title="Chưa có flow nào"
            desc="Flow giúp lên lịch hàng loạt bài bằng cách kéo thả các khối: bài viết, thời gian chờ, khung giờ, lặp lại…"
            action={<Button leftSection={<IconPlus size={16} />} onClick={onCreate}>Tạo flow đầu tiên</Button>} />
        </Card>
      ) : (
        <>
          <Group mb="md" gap="sm" wrap="wrap">
            <TextInput placeholder="Tìm theo tên hoặc mô tả…" leftSection={<IconSearch size={16} />} value={q}
              onChange={(e) => setQ(e.currentTarget.value)} w={{ base: "100%", sm: 300 }} aria-label="Tìm flow" />
            <SegmentedControl value={sort} onChange={setSort}
              data={[{ value: "updated", label: "Mới sửa" }, { value: "name", label: "Tên A–Z" }, { value: "run", label: "Mới chạy" }]} />
            <Text size="sm" c="dimmed" ml="auto">{list.length} / {flows.length} flow</Text>
          </Group>
          {list.length === 0 ? (
            <Card><EmptyState icon={IconSearch} title="Không tìm thấy flow" desc={`Không có flow nào khớp “${q}”.`} /></Card>
          ) : (
            <SimpleGrid cols={{ base: 1, sm: 2, xl: 3 }} spacing="md">
              {list.map((f) => (
                <FlowCard key={f.id} flow={f} onOpen={() => onOpen(f.id)} onEdit={() => onEdit(f)} onDuplicate={() => onDuplicate(f)}
                  onExport={() => onExport(f)} onDelete={() => onDelete(f)} />
              ))}
            </SimpleGrid>
          )}
        </>
      )}
    </>
  );
}

