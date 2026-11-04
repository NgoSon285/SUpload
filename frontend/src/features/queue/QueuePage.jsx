import { useMemo, useState } from "react";
import { Button, Card, Group, Paper, SegmentedControl, SimpleGrid, Stack, Text, ThemeIcon } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconAlertTriangle, IconCheck, IconClock, IconGauge, IconInbox, IconPlus, IconSitemap, IconTrash } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { postsApi } from "../../api/endpoints";
import { EmptyState, PageHeader, notifyErr, notifyOk } from "../../components";
import { dayLabel } from "../../lib/time";
import { PostRow } from "./PostRow";
import { isUpcoming, upcomingTime } from "./status";

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

const confirm = (opts) => new Promise((resolve) => modals.openConfirmModal({ ...opts, onConfirm: () => resolve(true), onCancel: () => resolve(false) }));

export default function QueuePage() {
  const { state, refresh, setView, setDraftPost } = useApp();
  const [filter, setFilter] = useState("pending");
  const posts = state.posts;
  const limits = state.limits || {};
  const counts = {
    pending: posts.filter(isUpcoming).length,
    done: posts.filter((p) => p.status === "done").length,
    error: posts.filter((p) => p.status === "error").length,
  };

  const groups = useMemo(() => {
    const list = posts.filter((p) => (filter === "pending" ? isUpcoming(p) : p.status === filter));
    const key = (p) => {
      if (filter !== "pending") return -new Date(p.done_at || p.created_at);
      const t = upcomingTime(p);
      return p.status === "running" ? 0 : t ? +new Date(t) : 1;
    };
    list.sort((a, b) => key(a) - key(b));
    const out = [];
    for (const p of list) {
      const ref = filter === "pending" ? upcomingTime(p) : p.done_at || p.created_at;
      const g = ref ? dayLabel(ref) : "Đăng ngay";
      if (!out.length || out[out.length - 1].label !== g) out.push({ label: g, items: [] });
      out[out.length - 1].items.push(p);
    }
    return out;
  }, [posts, filter]);

  const remove = async (p) => {
    const onFb = p.status === "scheduled";
    const ok = await confirm({
      title: "Xoá bài này?",
      children: <Text size="sm">{onFb ? "Bài đã hẹn trên Facebook sẽ được huỷ trên Facebook và xoá khỏi lịch đăng." : "Bài sẽ bị xoá khỏi lịch đăng. Bài đã đăng trên Facebook không bị ảnh hưởng."}</Text>,
      labels: { confirm: onFb ? "Huỷ & xoá" : "Xoá", cancel: "Không" }, confirmProps: { color: "red" },
    });
    if (!ok) return;
    try {
      await postsApi.remove(p.id);
      notifyOk(onFb ? "Đã huỷ bài hẹn trên Facebook" : "Đã xoá bài");
    } catch (e) {
      if (!e.data?.can_force) return notifyErr(e.message);
      const force = await confirm({
        title: "Không huỷ được trên Facebook",
        children: <Text size="sm">{e.message}. Vẫn xoá khỏi lịch đăng? Khi đó bạn cần tự xoá bài hẹn trong mục “Bài đã lên lịch” của Page, nếu không Facebook vẫn sẽ đăng.</Text>,
        labels: { confirm: "Vẫn xoá khỏi danh sách", cancel: "Để sau" }, confirmProps: { color: "red" },
      });
      if (force) { await postsApi.remove(p.id, { force: true }); notifyOk("Đã xoá khỏi lịch đăng"); }
    }
    refresh();
  };

  const onAction = (a, p) => {
    if (a === "del") remove(p);
    else if (a === "retry") postsApi.retry(p.id).then(() => { notifyOk("Đang đăng lại…"); refresh(); }, (e) => notifyErr(e.message));
    else { setDraftPost({ post: p, mode: a === "edit" ? "edit" : "dup" }); setView("compose"); }
  };

  const clearDone = () =>
    modals.openConfirmModal({
      title: "Dọn bài đã đăng?",
      children: <Text size="sm">Các bài đã đăng sẽ bị xoá khỏi danh sách (không ảnh hưởng tới Facebook).</Text>,
      labels: { confirm: "Dọn dẹp", cancel: "Huỷ" },
      onConfirm: async () => { await postsApi.clearDone(); refresh(); },
    });

  const EMPTY = {
    pending: [IconInbox, "Chưa có bài nào sắp đăng", "Soạn bài mới hoặc dựng một flow chiến dịch để lên lịch nhiều bài."],
    done: [IconCheck, "Chưa có bài nào được đăng", "Các bài đăng thành công sẽ xuất hiện ở đây."],
    error: [IconCheck, "Không có lỗi nào", "Mọi bài đều đăng suôn sẻ."],
  }[filter];

  return (
    <>
      <PageHeader
        title="Lịch đăng" desc="Theo dõi các bài đang chờ, đã hẹn trên Facebook, đã đăng và bị lỗi."
        right={<Group gap="xs"><Button variant="default" leftSection={<IconSitemap size={16} />} onClick={() => setView("flow")}>Flow</Button><Button leftSection={<IconPlus size={16} />} onClick={() => setView("compose")}>Bài mới</Button></Group>}
      />
      <SimpleGrid cols={{ base: 1, xs: 3 }} mb="lg">
        <Stat icon={IconClock} color="indigo" value={counts.pending} label="Sắp đăng" />
        <Stat icon={IconGauge} color="teal" value={limits.daily_max ? `${limits.today}/${limits.daily_max}` : limits.today ?? 0}
          label={limits.daily_max ? "Bài hôm nay / giới hạn" : "Bài hôm nay"} />
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
