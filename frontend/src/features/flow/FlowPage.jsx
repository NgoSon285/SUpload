import { useCallback, useEffect, useRef, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { Alert, Button, Group, Menu, Stack, Text, TextInput, ThemeIcon } from "@mantine/core";
import { useDebouncedCallback } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { IconArrowForward, IconArrowLeft, IconCheck, IconCopy, IconDots, IconDownload, IconPencil, IconTrash } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { flowsApi, stateApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";
import { configured } from "../../lib/page";
import { toLocalIso, when } from "../../lib/time";
import { FlowEditor } from "./editor/FlowEditor";
import { newId, newNode, sampleFlow } from "./engine/schedule";
import { DeleteFlowModal, FlowFormModal } from "./FlowDialogs";
import { FlowList } from "./FlowList";

/* ------------------------------------------------------------------ trang */
const blankGraph = () => ({ nodes: [newNode("start", { x: 0, y: 0 })], edges: [], seed: newId("s") });

function download(name, obj) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name.replace(/[\\/:*?"<>|]+/g, "_") || "flow"}.supload-flow.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function FlowPage() {
  const { state, refresh, setView } = useApp();
  const [flows, setFlows] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [saveState, setSaveState] = useState("saved");
  const [form, setForm] = useState(null); // {mode: 'create'|'edit', flow}
  const [toDelete, setToDelete] = useState(null);
  const current = flows?.find((f) => f.id === openId) || null;

  const reload = useCallback(async () => {
    try { setFlows(await flowsApi.list()); } catch (e) { notifyErr(e.message); }
  }, []);
  useEffect(() => { reload(); }, [reload]);

  /* ---- lưu tự động khi sửa trong trình dựng */
  const pending = useRef(null);
  const persist = useCallback(async (f) => {
    if (pending.current?.id === f.id) pending.current = null;
    setSaveState("saving");
    try {
      const { flow } = await flowsApi.save(f.id, { name: f.name, description: f.description, nodes: f.nodes, edges: f.edges, seed: f.seed });
      setFlows((fs) => fs?.map((x) => (x.id === flow.id ? { ...x, updated_at: flow.updated_at } : x)));
      setSaveState("saved");
    } catch (e) { setSaveState("error"); notifyErr(e.message, "Không lưu được flow"); }
  }, []);
  const persistLater = useDebouncedCallback(persist, 700);
  const flush = useCallback(async () => { if (pending.current) await persist(pending.current); }, [persist]);
  useEffect(() => () => { if (pending.current) persist(pending.current); }, [persist]); // rời trang -> lưu ngay

  const patchCurrent = (patch) => {
    setFlows((fs) => fs.map((f) => (f.id === openId ? { ...f, ...patch } : f)));
    setSaveState("dirty");
    pending.current = { ...current, ...pending.current, ...patch };
    persistLater(pending.current);
  };

  /* ---- quản lý flow */
  const open = (id) => { setSaveState("saved"); setOpenId(id); };
  const back = async () => { await flush(); setOpenId(null); reload(); };

  const submitForm = async ({ name, description, template }) => {
    if (form.mode === "create") {
      const id = newId("f");
      const graph = template === "blank" ? blankGraph() : sampleFlow();
      await flowsApi.save(id, { name, description, ...graph });
      await reload();
      notifyOk(`Đã tạo flow “${name}”`);
      open(id);
    } else {
      if (form.flow.id === openId) await flush();
      await flowsApi.save(form.flow.id, { name, description });
      setFlows((fs) => fs.map((f) => (f.id === form.flow.id ? { ...f, name, description } : f)));
      notifyOk("Đã lưu tên & mô tả");
    }
  };

  const duplicate = async (f) => {
    try {
      if (f.id === openId) await flush();
      const { flow } = await flowsApi.duplicate(f.id);
      await reload();
      notifyOk(`Đã tạo “${flow.name}”`);
      return flow;
    } catch (e) { notifyErr(e.message); return null; }
  };

  const exportFlow = (f) => {
    const src = f.id === openId ? { ...f, ...pending.current } : f;
    download(src.name, { format: "supload-flow", version: 1, name: src.name, description: src.description || "", nodes: src.nodes, edges: src.edges, seed: src.seed });
  };

  const importFlow = async (file) => {
    try {
      const json = JSON.parse(await file.text());
      const { flow } = await flowsApi.import(json);
      await reload();
      notifyOk(`Đã nhập flow “${flow.name}”`);
    } catch (e) { notifyErr(e instanceof SyntaxError ? "File không phải JSON hợp lệ" : e.message, "Không nhập được flow"); }
  };

  const remove = async (withPosts) => {
    const f = toDelete;
    if (f.id === openId) { pending.current = null; setOpenId(null); }
    const r = await flowsApi.remove(f.id, { withPosts });
    await reload();
    refresh();
    notifyOk(r.removed_posts ? `Đã xoá flow và ${r.removed_posts} bài chưa đăng` : "Đã xoá flow");
  };

  /* ---- chạy flow */
  const run = async (schedule) => {
    if (!configured(state.settings)) {
      modals.openConfirmModal({ title: "Chưa kết nối Page", children: <Text size="sm">Cần kết nối Page trước khi chạy flow.</Text>, labels: { confirm: "Mở Cài đặt", cancel: "Để sau" }, onConfirm: () => setView("settings") });
      return;
    }
    const soon = Date.now() + 60000;
    const items = schedule.posts.map((p) => ({ message: p.message, link: p.link, photos: p.photos, scheduled_at: +p.time > soon ? toLocalIso(p.time) : null }));
    let preview = null;
    try { preview = await stateApi.previewPlan(items); } catch (e) { notifyErr(e.message); return; }
    const last = preview.items.reduce((m, it) => (it.effective_at > m ? it.effective_at : m), preview.items[0].effective_at);
    const fbSchedules = state.settings.method === "api" && state.settings.fb_schedule;
    modals.openConfirmModal({
      title: "Chạy flow và lên lịch?",
      children: (
        <Stack gap="xs">
          <Text size="sm">Sẽ thêm <b>{items.length} bài</b> vào Lịch đăng, từ <b>{when(preview.items[0].effective_at)}</b> đến <b>{when(last)}</b>.</Text>
          {preview.shifted > 0 && (
            <Alert color="orange" variant="light" py="xs" icon={<IconArrowForward size={16} />} data-testid="run-shift-warning">
              {preview.shifted} bài được dời do giới hạn an toàn
              {preview.by_cap > 0 && ` (${preview.by_cap} bài vì tối đa ${preview.daily_max} bài/ngày`}
              {preview.by_cap > 0 && preview.by_gap > 0 && `, ${preview.by_gap} bài vì giãn cách ${Math.round(preview.min_gap / 60)} phút)`}
              {preview.by_cap > 0 && !preview.by_gap && ")"}
              {!preview.by_cap && preview.by_gap > 0 && ` (giãn cách ${Math.round(preview.min_gap / 60)} phút)`}.
            </Alert>
          )}
          <Text size="xs" c="dimmed">
            {fbSchedules
              ? "Bài hẹn từ 12 phút tới 30 ngày sẽ được gửi lên Facebook để Facebook tự đăng, kể cả khi tắt máy."
              : "Ứng dụng phải đang chạy vào các thời điểm này để đăng bài."}
            {" "}Các lựa chọn ngẫu nhiên được giữ đúng như trong Lịch dự kiến.
          </Text>
        </Stack>
      ),
      labels: { confirm: `Lên lịch ${items.length} bài`, cancel: "Huỷ" },
      onConfirm: async () => {
        try {
          await flush();
          const { count } = await flowsApi.run({ flow_id: current.id, name: current.name, posts: items });
          refresh();
          reload();
          modals.openConfirmModal({
            title: <Group gap="xs"><ThemeIcon color="teal" radius="xl" size="sm"><IconCheck size={14} /></ThemeIcon>Đã lên lịch {count} bài</Group>,
            children: <Text size="sm">Bạn có thể theo dõi và sửa từng bài trong Lịch đăng.</Text>,
            labels: { confirm: "Xem Lịch đăng", cancel: "Ở lại" }, onConfirm: () => setView("queue"),
          });
        } catch (e) { notifyErr(e.message); }
      },
    });
  };

  if (!flows) return null;

  const dialogs = (
    <>
      <FlowFormModal opened={!!form} mode={form?.mode} initial={form?.flow || null} onClose={() => setForm(null)} onSubmit={submitForm} />
      <DeleteFlowModal flow={toDelete} onClose={() => setToDelete(null)} onConfirm={remove} />
    </>
  );

  if (!current) {
    return (
      <div style={{ padding: "var(--mantine-spacing-lg)" }}>
        <FlowList
          flows={flows} onOpen={open} onCreate={() => setForm({ mode: "create", flow: { name: "", description: "" } })}
          onEdit={(f) => setForm({ mode: "edit", flow: f })} onDuplicate={duplicate} onExport={exportFlow}
          onDelete={setToDelete} onImport={importFlow}
        />
        {dialogs}
      </div>
    );
  }

  return (
    <div>
      <Group px="md" py="sm" gap="sm" wrap="wrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        <Button variant="subtle" color="gray" leftSection={<IconArrowLeft size={16} />} onClick={back}>Tất cả flow</Button>
        <TextInput w={260} value={current.name} onChange={(e) => patchCurrent({ name: e.currentTarget.value })} aria-label="Tên flow" placeholder="Tên flow" />
        <Text size="xs" c={saveState === "error" ? "red" : "dimmed"}>{saveState === "saving" || saveState === "dirty" ? "Đang lưu…" : saveState === "error" ? "Lưu thất bại" : "Đã lưu"}</Text>
        <Group gap="xs" ml="auto">
          <Menu position="bottom-end" withinPortal>
            <Menu.Target><Button variant="default" rightSection={<IconDots size={16} />}>Flow</Button></Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconPencil size={16} />} onClick={() => setForm({ mode: "edit", flow: current })}>Đổi tên & mô tả</Menu.Item>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={async () => { const f = await duplicate(current); if (f) open(f.id); }}>Nhân bản và mở bản sao</Menu.Item>
              <Menu.Item leftSection={<IconDownload size={16} />} onClick={() => exportFlow(current)}>Xuất file</Menu.Item>
              <Menu.Divider />
              <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={() => setToDelete(flows.find((f) => f.id === current.id))}>Xoá flow</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
      <ReactFlowProvider key={current.id}>
        <FlowEditor flow={current} onChange={patchCurrent} onRun={run} onReseed={() => patchCurrent({ seed: newId("s") })} />
      </ReactFlowProvider>
      {dialogs}
    </div>
  );
}
