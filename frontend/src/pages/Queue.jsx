import { useMemo, useState } from "react";
import {
  ActionIcon, Alert, Badge, Button, Card, Group, Image, Paper, SegmentedControl, SimpleGrid, Stack, Text, ThemeIcon, Tooltip,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import {
  IconAlertTriangle, IconCheck, IconClock, IconCopy, IconInbox, IconLink, IconPencil, IconPhoto, IconPlus, IconRefresh,
  IconSend, IconSitemap, IconTrash,
} from "@tabler/icons-react";
import dayjs from "dayjs";

import { useApp } from "../App";
import { api, imgUrl } from "../lib/api";
import { dayLabel, hm, rel, when } from "../lib/time";
import { EmptyState, PageHeader, notifyErr, notifyOk } from "../components/common";

const STATUS = {
  pending: { label: "Đang chờ", color: "indigo" },
  running: { label: "Đang đăng", color: "orange" },
  done: { label: "Đã đăng", color: "teal" },
  error: { label: "Lỗi", color: "red" },
};

function Stat({ icon: Icon, color, value, label }) {
  return (
    <Paper withBorder p="md" shadow="xs">
      <Group gap="md" wrap="nowrap">
        <ThemeIcon size={42} radius="md" variant="light" color={color}><Icon size={22} /></ThemeIcon>
        <div>
          <Text fz={24} fw={700} lh={1.1}>{value}</Text>
          <Text size="sm" c="dimmed">{label}</Text>
        </div>
      </Group>
    </Paper>
  );
}

function PostRow({ p, onAction }) {
  const st = STATUS[p.status];
  let time;
  if (p.status === "done") time = <><IconCheck size={14} />Đã đăng {p.done_at ? when(p.done_at) : ""}</>;
  else if (p.status === "running") time = <><IconSend size={14} />Đang đăng…</>;
  else if (p.scheduled_at) {
    const d = new Date(p.scheduled_at);
    time = <><IconClock size={14} />{hm(d)} · {d <= new Date() ? "đang chờ đến lượt" : rel(d)}</>;
  } else time = <><IconSend size={14} />Đăng ngay khi đến lượt</>;

  const act = (a, Icon, label, color = "gray") => (
    <Tooltip label={label} withArrow>
      <ActionIcon variant="subtle" color={color} onClick={() => onAction(a, p)} aria-label={label}><Icon size={18} /></ActionIcon>
    </Tooltip>
  );

  return (
    <Card p="sm" shadow="none">
      <Group align="flex-start" wrap="nowrap" gap="md">
        {p.photos.length ? (
          <div style={{ position: "relative", flex: "none" }}>
            <Image src={imgUrl(p.photos[0])} w={64} h={64} radius="md" fit="cover" />
            {p.photos.length > 1 && <Badge size="xs" color="dark" style={{ position: "absolute", right: 4, bottom: 4 }}>+{p.photos.length - 1}</Badge>}
          </div>
        ) : (
          <ThemeIcon size={64} radius="md" variant="light" color="gray">{p.link ? <IconLink size={24} /> : <IconPencil size={24} />}</ThemeIcon>
        )}
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Group gap={6}>
            <Badge variant="light" color={st.color} size="sm">{st.label}</Badge>
            {p.flow && <Badge variant="outline" color="gray" size="sm" leftSection={<IconSitemap size={11} />} style={{ textTransform: "none" }}>{p.flow}</Badge>}
          </Group>
          <Text lineClamp={2} size="sm" c={p.message ? undefined : "dimmed"} fs={p.message ? undefined : "italic"}>
            {p.message || p.link || "Bài chỉ có ảnh"}
          </Text>
          <Group gap="md" c="dimmed">
            <Group gap={4} fz="xs">{time}</Group>
            {p.photos.length > 0 && <Group gap={4} fz="xs"><IconPhoto size={14} />{p.photos.length} ảnh</Group>}
            {p.link && p.message && <Group gap={4} fz="xs"><IconLink size={14} />có link</Group>}
          </Group>
          {p.error && <Alert color="red" variant="light" p="xs" mt={4} icon={<IconAlertTriangle size={16} />}><Text size="xs">{p.error}</Text></Alert>}
        </Stack>
        {p.status !== "running" && (
          <Group gap={2} wrap="nowrap">
            {p.status === "error" && act("retry", IconRefresh, "Đăng lại ngay", "indigo")}
            {(p.status === "pending" || p.status === "error") && act("edit", IconPencil, "Sửa")}
            {act("dup", IconCopy, "Dùng lại nội dung")}
            {act("del", IconTrash, "Xoá", "red")}
          </Group>
        )}
      </Group>
    </Card>
  );
}

export default function Queue() {
  const { state, refresh, setView, setDraftPost } = useApp();
  const [filter, setFilter] = useState("pending");
  const posts = state.posts;
  const isP = (p) => p.status === "pending" || p.status === "running";
  const counts = {
    pending: posts.filter(isP).length,
    done: posts.filter((p) => p.status === "done").length,
    error: posts.filter((p) => p.status === "error").length,
  };
  const today = posts.filter((p) => p.status === "done" && p.done_at && dayjs(p.done_at).isSame(dayjs(), "day")).length;

  const groups = useMemo(() => {
    const list = posts.filter((p) => (filter === "pending" ? isP(p) : p.status === filter));
    const key = (p) => (filter === "pending" ? (p.status === "running" ? 0 : p.scheduled_at ? +new Date(p.scheduled_at) : 1) : -new Date(p.done_at || p.created_at));
    list.sort((a, b) => key(a) - key(b));
    const out = [];
    for (const p of list) {
      const ref = filter === "pending" ? (p.status === "running" || !p.scheduled_at ? null : p.scheduled_at) : p.done_at || p.created_at;
      const g = ref ? dayLabel(ref) : "Đăng ngay";
      if (!out.length || out[out.length - 1].label !== g) out.push({ label: g, items: [] });
      out[out.length - 1].items.push(p);
    }
    return out;
  }, [posts, filter]);

  const onAction = (a, p) => {
    if (a === "del") {
      modals.openConfirmModal({
        title: "Xoá bài này?",
        children: <Text size="sm">Bài sẽ bị xoá khỏi lịch đăng. Bài đã đăng trên Facebook không bị ảnh hưởng.</Text>,
        labels: { confirm: "Xoá", cancel: "Huỷ" }, confirmProps: { color: "red" },
        onConfirm: async () => { try { await api(`/api/posts/${p.id}`, { method: "DELETE" }); notifyOk("Đã xoá bài"); refresh(); } catch (e) { notifyErr(e.message); } },
      });
    } else if (a === "retry") {
      api(`/api/posts/${p.id}/retry`, { method: "POST" }).then(() => { notifyOk("Đang đăng lại…"); refresh(); }, (e) => notifyErr(e.message));
    } else {
      setDraftPost({ post: p, mode: a === "edit" ? "edit" : "dup" });
      setView("compose");
    }
  };

  const clearDone = () =>
    modals.openConfirmModal({
      title: "Dọn bài đã đăng?",
      children: <Text size="sm">Các bài đã đăng sẽ bị xoá khỏi danh sách (không ảnh hưởng tới Facebook).</Text>,
      labels: { confirm: "Dọn dẹp", cancel: "Huỷ" },
      onConfirm: async () => { await api("/api/clear-done", { method: "POST" }); refresh(); },
    });

  const EMPTY = {
    pending: [IconInbox, "Chưa có bài nào sắp đăng", "Soạn bài mới hoặc dựng một flow chiến dịch để lên lịch nhiều bài."],
    done: [IconCheck, "Chưa có bài nào được đăng", "Các bài đăng thành công sẽ xuất hiện ở đây."],
    error: [IconCheck, "Không có lỗi nào", "Mọi bài đều đăng suôn sẻ."],
  }[filter];

  return (
    <>
      <PageHeader
        title="Lịch đăng" desc="Theo dõi các bài đang chờ, đã đăng và bị lỗi."
        right={<Group gap="xs"><Button variant="default" leftSection={<IconSitemap size={16} />} onClick={() => setView("flow")}>Flow</Button><Button leftSection={<IconPlus size={16} />} onClick={() => setView("compose")}>Bài mới</Button></Group>}
      />
      <SimpleGrid cols={{ base: 1, xs: 3 }} mb="lg">
        <Stat icon={IconClock} color="indigo" value={counts.pending} label="Đang chờ" />
        <Stat icon={IconCheck} color="teal" value={today} label="Đã đăng hôm nay" />
        <Stat icon={IconAlertTriangle} color="red" value={counts.error} label="Bị lỗi" />
      </SimpleGrid>

      <Group justify="space-between" mb="md">
        <SegmentedControl
          value={filter} onChange={setFilter}
          data={[
            { value: "pending", label: `Sắp đăng (${counts.pending})` },
            { value: "done", label: `Đã đăng (${counts.done})` },
            { value: "error", label: `Lỗi (${counts.error})` },
          ]}
        />
        {filter === "done" && counts.done > 0 && <Button variant="subtle" color="gray" leftSection={<IconTrash size={16} />} onClick={clearDone}>Dọn bài đã đăng</Button>}
      </Group>

      {groups.length === 0 ? (
        <Card><EmptyState icon={EMPTY[0]} title={EMPTY[1]} desc={EMPTY[2]}
          action={filter === "pending" && <Button leftSection={<IconPlus size={16} />} onClick={() => setView("compose")}>Soạn bài mới</Button>} /></Card>
      ) : (
        <Stack gap="lg">
          {groups.map((g) => (
            <div key={g.label}>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={8} ml={4}>{g.label} · {g.items.length}</Text>
              <Stack gap={8}>{g.items.map((p) => <PostRow key={p.id} p={p} onAction={onAction} />)}</Stack>
            </div>
          ))}
        </Stack>
      )}
    </>
  );
}
