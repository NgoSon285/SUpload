import { useMemo, useState } from "react";
import { Button, Card, Group, Paper, SegmentedControl, Select, SimpleGrid, Stack, Text, ThemeIcon } from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconAlertTriangle, IconCalendarMonth, IconCheck, IconClock, IconGauge, IconInbox, IconList, IconPlus, IconSitemap, IconTrash } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { postsApi } from "../../api/endpoints";
import { moveKeepingTime } from "../../lib/calendar";
import { storage } from "../../lib/storage";
import { toLocalIso, when } from "../../lib/time";
import { CalendarView } from "./CalendarView";
import { EmptyState, PageHeader, notifyErr, notifyOk } from "../../components";
import { defaultPage, pagesOf } from "../../lib/page";
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
  const [pageFilter, setPageFilter] = useState("all");
  const [layout, setLayoutRaw] = useState(() => storage.get("queue-layout", "list"));
  const setLayout = (v) => { setLayoutRaw(v); storage.set("queue-layout", v); };
  const pages = pagesOf(state);
  const multi = pages.length > 1;
  const def = defaultPage(state);
  const pageOfPost = (p) => p.page || def?.id;
  const pageName = (p) => (multi ? pages.find((x) => x.id === pageOfPost(p))?.name || "Page đã xoá" : null);
  const posts = pageFilter === "all" ? state.posts : state.posts.filter((p) => pageOfPost(p) === pageFilter);
  const limits = state.limits || {};
  const todayCount = pageFilter === "all" ? limits.today : limits.per_page?.[pageFilter] ?? 0;
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

  const move = async (p, day) => {
    const target = moveKeepingTime(p.status === "pending" ? p.effective_at || p.scheduled_at || new Date() : p.fb_scheduled_at || p.scheduled_at || p.done_at, day);
    if (target <= new Date()) return notifyErr("Không thể dời bài về thời điểm đã qua");
    try {
      await postsApi.edit(p.id, { message: p.message, link: p.link, photos: p.photos, page: p.page, scheduled_at: toLocalIso(target) });
      notifyOk(`Đã dời sang ${when(target)}${p.status === "scheduled" ? " (đã huỷ và hẹn lại trên Facebook)" : ""}`);
    } catch (e) { notifyErr(e.message); }
    refresh();
  };
  const createAt = (day) => {
    const at = moveKeepingTime(new Date(new Date().setHours(9, 0, 0, 0)), day);
    setDraftPost({ post: { message: "", link: "", photos: [], page: pageFilter === "all" ? "" : pageFilter, scheduled_at: toLocalIso(at > new Date() ? at : new Date(Date.now() + 3600000)) }, mode: "schedule" });
    setView("compose");
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
        <Stat icon={IconGauge} color="teal" value={limits.daily_max ? `${todayCount ?? 0}/${limits.daily_max}` : todayCount ?? 0}
          label={(limits.daily_max ? "Bài hôm nay / giới hạn" : "Bài hôm nay") + (multi && pageFilter === "all" ? " (Page mặc định)" : "")} />
        <Stat icon={IconAlertTriangle} color="red" value={counts.error} label="Bị lỗi" />
      </SimpleGrid>

      <Group justify="space-between" mb="md">
        <Group gap="xs">
          <SegmentedControl
            value={layout} onChange={setLayout} data-testid="queue-layout"
            data={[
              { value: "list", label: <Group gap={6} wrap="nowrap"><IconList size={16} />Danh sách</Group> },
              { value: "calendar", label: <Group gap={6} wrap="nowrap"><IconCalendarMonth size={16} />Lịch</Group> },
            ]}
          />
          {layout === "list" && (
            <SegmentedControl
              value={filter} onChange={setFilter}
              data={[
                { value: "pending", label: `Sắp đăng (${counts.pending})` },
                { value: "done", label: `Đã đăng (${counts.done})` },
                { value: "error", label: `Lỗi (${counts.error})` },
              ]}
            />
          )}
        </Group>
        {multi && (
          <Select
            w={220} value={pageFilter} onChange={(v) => setPageFilter(v || "all")} allowDeselect={false} aria-label="Lọc theo Page" data-testid="queue-page-filter"
            comboboxProps={{ withinPortal: true }} data={[{ value: "all", label: "Tất cả Page" }, ...pages.map((p) => ({ value: p.id, label: p.name }))]}
          />
        )}
        {layout === "list" && filter === "done" && counts.done > 0 && <Button variant="subtle" color="gray" leftSection={<IconTrash size={16} />} onClick={clearDone}>Dọn bài đã đăng</Button>}
      </Group>

      {layout === "calendar" ? (
        <CalendarView
          posts={posts} pageName={pageName} onMove={move} onCreateAt={createAt}
          onOpen={(p) => { setDraftPost({ post: p, mode: p.status === "done" ? "dup" : "edit" }); setView("compose"); }}
        />
      ) : groups.length === 0 ? (
        <Card><EmptyState icon={EMPTY[0]} title={EMPTY[1]} desc={EMPTY[2]}
          action={filter === "pending" && <Button leftSection={<IconPlus size={16} />} onClick={() => setView("compose")}>Soạn bài mới</Button>} /></Card>
      ) : (
        <Stack gap="lg">
          {groups.map((g) => (
            <div key={g.label}>
              <Text size="xs" fw={700} c="dimmed" tt="uppercase" mb={8} ml={4}>{g.label} · {g.items.length}</Text>
              <Stack gap={8}>{g.items.map((p) => <PostRow key={p.id} p={p} pageName={pageName(p)} onAction={onAction} />)}</Stack>
            </div>
          ))}
        </Stack>
      )}
    </>
  );
}
