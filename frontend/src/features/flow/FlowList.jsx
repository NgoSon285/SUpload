import { useMemo, useState } from "react";
import {
  ActionIcon, Badge, Button, Card, FileButton, Group, Menu, SegmentedControl, SimpleGrid, Stack, Text, TextInput, ThemeIcon,
  Tooltip, UnstyledButton,
} from "@mantine/core";
import {
  IconClock, IconCopy, IconDots, IconDownload, IconPencil, IconPlayerPlay, IconPlus, IconSearch, IconSitemap, IconTrash,
  IconUpload,
} from "@tabler/icons-react";

import { EmptyState, PageHeader } from "../../components";
import { rel, when } from "../../lib/time";
import { computeSchedule } from "./engine/schedule";
import { nodeDef } from "./engine/nodes";


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
