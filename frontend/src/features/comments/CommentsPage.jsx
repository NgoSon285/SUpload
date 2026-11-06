import { useEffect, useRef, useState } from "react";
import {
  ActionIcon, Alert, Anchor, Avatar, Badge, Button, Card, Checkbox, Collapse, Group, Loader, Paper, SegmentedControl, Select, Stack,
  Switch, Text, TextInput, Textarea, Tooltip,
} from "@mantine/core";
import {
  IconAlertTriangle, IconEye, IconEyeOff, IconMessageCircle, IconPlus, IconRefresh, IconRobot, IconSearch, IconSend, IconSparkles, IconTrash,
} from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { aiApi, commentsApi } from "../../api/endpoints";
import { EmptyState, PageHeader, notifyErr, notifyOk } from "../../components";
import { eventValue } from "../../lib/forms";
import { pagesOf } from "../../lib/page";
import { rel, when } from "../../lib/time";

const UNHIDE = [{ value: "0", label: "Ẩn luôn" }, { value: "1", label: "Hiện lại sau 1 giờ" }, { value: "6", label: "Sau 6 giờ" },
  { value: "24", label: "Sau 1 ngày" }, { value: "72", label: "Sau 3 ngày" }, { value: "168", label: "Sau 7 ngày" }];

/** Cấu hình tự động: ẩn SĐT / từ cấm, trả lời theo từ khoá. */
function AutoRules({ config, onSaved }) {
  const [f, setF] = useState(config);
  const [dirty, setDirty] = useState(false);
  useEffect(() => { if (!dirty) setF(config); }, [config]); // eslint-disable-line
  const set = (k) => (v) => { const val = eventValue(v); setF((x) => ({ ...x, [k]: val })); setDirty(true); };
  const setRule = (i, k, v) => { setF((x) => ({ ...x, rules: x.rules.map((r, j) => (j === i ? { ...r, [k]: v } : r)) })); setDirty(true); };
  const save = async () => {
    try { const r = await commentsApi.saveConfig({ ...f, unhide_after_h: Number(f.unhide_after_h) }); setDirty(false); onSaved(r.config); notifyOk("Đã lưu quy tắc bình luận"); }
    catch (e) { notifyErr(e.message); }
  };
  return (
    <Stack gap="md" data-testid="comment-rules">
      <Switch checked={f.enabled} onChange={set("enabled")} label="Bật tự động xử lý bình luận mới"
        description="Chỉ áp dụng cho bình luận đến SAU khi bật. Bình luận cũ không bị trả lời hay ẩn." />
      <Group align="flex-end" gap="md">
        <Switch checked={f.hide_phone} onChange={set("hide_phone")} label="Ẩn bình luận có số điện thoại" description="Tránh đối thủ thấy SĐT khách." />
        <Select w={190} data={UNHIDE} value={String(f.unhide_after_h)} onChange={set("unhide_after_h")} allowDeselect={false} comboboxProps={{ withinPortal: true }} aria-label="Hiện lại sau" />
      </Group>
      <TextInput label="Ẩn bình luận chứa các từ" placeholder="lừa đảo, rẻ hơn, shop khác…" value={f.hide_words} onChange={set("hide_words")}
        description="Cách nhau bởi dấu phẩy. Không phân biệt hoa thường, có dấu hay không dấu." />
      <div>
        <Text size="sm" fw={500}>Trả lời theo từ khoá</Text>
        <Text size="xs" c="dimmed" mb="xs">Bình luận chứa từ khoá → trả lời công khai và/hoặc nhắn riêng (Facebook cho nhắn riêng 1 lần, trong 7 ngày). Dùng {"{ten}"} để gọi tên khách, {"{a|b}"} để chọn ngẫu nhiên.</Text>
        <Stack gap="sm">
          {f.rules.map((r, i) => (
            <Paper key={i} withBorder p="sm" radius="md">
              <Group justify="space-between" mb={6}>
                <Switch size="xs" checked={r.enabled !== false} onChange={(e) => setRule(i, "enabled", e.currentTarget.checked)} label={`Quy tắc ${i + 1}`} />
                <ActionIcon variant="subtle" color="red" aria-label="Xoá quy tắc" onClick={() => { setF((x) => ({ ...x, rules: x.rules.filter((_, j) => j !== i) })); setDirty(true); }}><IconTrash size={16} /></ActionIcon>
              </Group>
              <Stack gap={6}>
                <TextInput size="xs" label="Khi bình luận có từ" placeholder="giá, ib, bao nhiêu" value={r.keywords} onChange={(e) => setRule(i, "keywords", e.currentTarget.value)} />
                <Textarea size="xs" label="Trả lời công khai" autosize minRows={1} placeholder="Dạ {ten} ơi, shop đã nhắn tin cho bạn ạ ❤️" value={r.reply} onChange={(e) => setRule(i, "reply", e.currentTarget.value)} />
                <Textarea size="xs" label="Nhắn riêng (Messenger)" autosize minRows={1} placeholder="Chào {ten}, giá sản phẩm là…" value={r.private} onChange={(e) => setRule(i, "private", e.currentTarget.value)} />
              </Stack>
            </Paper>
          ))}
          <Button variant="light" size="xs" leftSection={<IconPlus size={14} />} w="fit-content"
            onClick={() => { setF((x) => ({ ...x, rules: [...x.rules, { keywords: "giá, ib, bao nhiêu", reply: "Dạ {ten} ơi, shop đã nhắn tin cho bạn rồi ạ ❤️", private: "", enabled: true }] })); setDirty(true); }}>
            Thêm quy tắc
          </Button>
        </Stack>
      </div>
      <Group justify="space-between">
        <Switch size="xs" checked={f.inbox} onChange={set("inbox")} label={`Đồng bộ bình luận mỗi ${f.poll_minutes} phút`} />
        <Group gap="xs">
          {dirty && <Button variant="default" onClick={() => { setF(config); setDirty(false); }}>Huỷ</Button>}
          <Button onClick={save} disabled={!dirty}>Lưu quy tắc</Button>
        </Group>
      </Group>
    </Stack>
  );
}

function CommentCard({ c, pageName, onChanged }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [priv, setPriv] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ideas, setIdeas] = useState(null);
  const send = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try { await commentsApi.reply(c.id, text, priv); notifyOk(priv ? "Đã nhắn riêng" : "Đã trả lời"); setText(""); setOpen(false); setIdeas(null); onChanged(); }
    catch (e) { notifyErr(e.message); }
    setBusy(false);
  };
  const hide = async () => {
    try { await commentsApi.hide(c.id, !c.hidden); onChanged(); } catch (e) { notifyErr(e.message); }
  };
  const suggest = async () => {
    setIdeas("loading");
    try {
      const r = await aiApi.suggest({ action: "reply", text: `Bài viết: ${c.post_text || "(không rõ)"}\nBình luận của ${c.from_name}: ${c.message}`, page: c.page });
      setIdeas(r.suggestions);
    } catch (e) { setIdeas(null); notifyErr(e.message); }
  };
  return (
    <Card p="md" data-testid="comment" style={c.seen ? undefined : { borderLeft: "3px solid var(--mantine-primary-color-filled)" }}>
      <Group align="flex-start" wrap="nowrap" gap="sm">
        <Avatar radius="xl" color="indigo">{c.from_name.slice(0, 1)}</Avatar>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Group gap={6} wrap="wrap">
            <Text fw={600} size="sm">{c.from_name}</Text>
            <Text size="xs" c="dimmed">{c.created_time ? rel(c.created_time) : ""}{pageName ? ` · ${pageName}` : ""}</Text>
            {c.hidden && <Badge size="xs" color="gray" variant="light" leftSection={<IconEyeOff size={10} />}>Đã ẩn{c.hide_reason ? `: ${c.hide_reason}` : ""}</Badge>}
            {c.unhide_at && <Badge size="xs" color="gray" variant="outline">hiện lại {when(c.unhide_at)}</Badge>}
            {c.replies.some((r) => r.auto) && <Badge size="xs" color="violet" variant="light" leftSection={<IconRobot size={10} />}>Tự động</Badge>}
            {c.private_sent && <Badge size="xs" color="teal" variant="light">Đã nhắn riêng</Badge>}
          </Group>
          <Text size="sm" mt={4} style={{ whiteSpace: "pre-wrap", opacity: c.hidden ? 0.6 : 1 }}>{c.message}</Text>
          {c.post_text && <Text size="xs" c="dimmed" mt={4} lineClamp={1}>Trên bài: {c.post_text}</Text>}
          {c.replies.map((r, i) => (
            <Paper key={i} mt={6} p={6} px="sm" radius="md" bg="var(--mantine-color-default-hover)">
              <Text size="xs" c="dimmed">{r.private ? "Nhắn riêng" : "Page trả lời"}{r.auto ? " (tự động)" : ""} · {when(r.at)}</Text>
              <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{r.text}</Text>
            </Paper>
          ))}
          {c.errors?.map((e) => <Text key={e} size="xs" c="red" mt={4}>✕ {e}</Text>)}
          <Group gap="xs" mt={8}>
            <Button size="compact-xs" variant="light" leftSection={<IconMessageCircle size={14} />} onClick={() => setOpen((o) => !o)}>Trả lời</Button>
            {c.can_hide && <Button size="compact-xs" variant="subtle" color="gray" leftSection={c.hidden ? <IconEye size={14} /> : <IconEyeOff size={14} />} onClick={hide}>{c.hidden ? "Hiện lại" : "Ẩn"}</Button>}
            {c.url && <Anchor href={c.url} target="_blank" size="xs" c="dimmed">Mở trên Facebook</Anchor>}
          </Group>
          <Collapse in={open}>
            <Stack gap={6} mt="sm">
              <Textarea autosize minRows={2} placeholder={`Trả lời ${c.from_name}…`} value={text} onChange={(e) => setText(e.currentTarget.value)} aria-label="Nội dung trả lời" />
              {ideas === "loading" && <Group gap={6}><Loader size="xs" /><Text size="xs" c="dimmed">AI đang gợi ý…</Text></Group>}
              {Array.isArray(ideas) && ideas.map((s) => (
                <Paper key={s} withBorder p={6} px="sm" radius="md" style={{ cursor: "pointer" }} onClick={() => setText(s)} data-testid="reply-idea">
                  <Text size="sm">{s}</Text>
                </Paper>
              ))}
              <Group justify="space-between">
                <Group gap="sm">
                  <Checkbox size="xs" label="Nhắn riêng qua Messenger" checked={priv} onChange={(e) => setPriv(e.currentTarget.checked)}
                    disabled={c.private_sent || !c.can_reply_privately} />
                  <Button size="compact-xs" variant="subtle" color="violet" leftSection={<IconSparkles size={14} />} onClick={suggest}>AI gợi ý</Button>
                </Group>
                <Button size="xs" leftSection={<IconSend size={14} />} loading={busy} onClick={send}>Gửi</Button>
              </Group>
            </Stack>
          </Collapse>
        </div>
      </Group>
    </Card>
  );
}

/** Hộp bình luận của mọi Page + quy tắc tự động. */
export default function CommentsPage() {
  const { state, refresh } = useApp();
  const pages = pagesOf(state).filter((p) => p.kind === "api");
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState("");
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [showRules, setShowRules] = useState(false);
  const marked = useRef(false);

  const load = () => commentsApi.list({ page, filter, q }).then(setData, (e) => notifyErr(e.message));
  useEffect(() => { load(); }, [page, filter, q, state]); // eslint-disable-line
  useEffect(() => {  // rời trang: đánh dấu đã xem
    return () => { if (marked.current) commentsApi.seen([]).then(refresh, () => {}); };
  }, []); // eslint-disable-line
  useEffect(() => { if (data?.unseen) marked.current = true; }, [data]);

  const syncNow = async () => { try { await commentsApi.sync(); notifyOk("Đang đọc bình luận mới…"); setTimeout(load, 3000); } catch (e) { notifyErr(e.message); } };
  const errors = data ? Object.entries(data.sync).filter(([, s]) => s.error) : [];
  const lastSync = data ? Object.values(data.sync).map((s) => s.last_at).filter(Boolean).sort().pop() : null;
  const pageName = (id) => (pages.length > 1 ? pages.find((p) => p.id === id)?.name : null);

  return (
    <>
      <PageHeader title="Bình luận" desc="Đọc và trả lời bình luận của các Page, tự ẩn SĐT và tự trả lời theo từ khoá."
        right={<Group gap="xs">
          <Button variant="default" leftSection={<IconRobot size={16} />} onClick={() => setShowRules((x) => !x)} data-testid="toggle-rules">
            Tự động {data?.config?.enabled ? <Badge ml={6} size="xs" color="teal">Bật</Badge> : <Badge ml={6} size="xs" color="gray">Tắt</Badge>}
          </Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={syncNow}>Đồng bộ ngay</Button>
        </Group>} />

      {!pages.length && <Alert mb="md" color="orange" variant="light">Bình luận chỉ dùng được với Page kết nối qua Graph API.</Alert>}
      {errors.map(([pid, s]) => (
        <Alert key={pid} mb="md" color="red" variant="light" icon={<IconAlertTriangle size={18} />} title={pages.find((p) => p.id === pid)?.name}>{s.error}</Alert>
      ))}
      <Collapse in={showRules}>
        <Card p="lg" mb="lg">{data && <AutoRules config={data.config} onSaved={() => { load(); refresh(); }} />}</Card>
      </Collapse>

      <Group justify="space-between" mb="md" gap="xs">
        <Group gap="xs">
          <SegmentedControl value={filter} onChange={setFilter} data={[
            { value: "all", label: `Tất cả (${data?.counts.all ?? 0})` }, { value: "unreplied", label: `Chưa trả lời (${data?.counts.unreplied ?? 0})` },
            { value: "hidden", label: `Đã ẩn (${data?.counts.hidden ?? 0})` }, { value: "auto", label: `Tự động (${data?.counts.auto ?? 0})` }]} />
          {pages.length > 1 && <Select w={200} value={page} onChange={(v) => setPage(v || "")} comboboxProps={{ withinPortal: true }} aria-label="Lọc theo Page"
            data={[{ value: "", label: "Tất cả Page" }, ...pages.map((p) => ({ value: p.id, label: p.name }))]} allowDeselect={false} />}
        </Group>
        <TextInput w={220} leftSection={<IconSearch size={14} />} placeholder="Tìm bình luận, tên…" value={q} onChange={(e) => setQ(e.currentTarget.value)} />
      </Group>
      {lastSync && <Text size="xs" c="dimmed" mb="sm">Đồng bộ lần cuối {rel(lastSync)}</Text>}

      {!data ? <Loader /> : data.items.length === 0 ? (
        <Card><EmptyState icon={IconMessageCircle} title="Chưa có bình luận nào"
          desc={data.config.inbox ? "Bình luận trên các bài trong 7 ngày gần đây sẽ hiện ở đây sau vài phút." : "Bật “Đồng bộ bình luận” trong phần Tự động."} /></Card>
      ) : (
        <Stack gap="sm">{data.items.map((c) => <CommentCard key={c.id} c={c} pageName={pageName(c.page)} onChanged={load} />)}</Stack>
      )}
    </>
  );
}
