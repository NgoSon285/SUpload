import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, Handle, Position, addEdge, useEdgesState, useNodesState,
  useReactFlow, MarkerType,
} from "@xyflow/react";
import {
  ActionIcon, Alert, Badge, Button, Group, Menu, NumberInput, Paper, ScrollArea, SegmentedControl, Select, Stack, Tabs,
  Text, TextInput, Textarea, ThemeIcon, Timeline, Tooltip, Image,
} from "@mantine/core";
import { DateTimePicker, TimeInput } from "@mantine/dates";
import { useDebouncedCallback } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import {
  IconPlayerPlay, IconFlag, IconPencil, IconStack2, IconHourglass, IconPlus, IconTrash, IconCopy, IconDots,
  IconAlertTriangle, IconCalendarEvent, IconAdjustments, IconCheck, IconClock, IconTemplate, IconFile, IconPointer,
} from "@tabler/icons-react";

import { useApp } from "../App";
import { api, configured, imgUrl } from "../lib/api";
import { NODE_DEFAULTS, batchItems, computeSchedule, newId, sampleFlow, splitParagraphs } from "../lib/flow";
import { dayLabel, hm, toLocalIso, UNITS, unitLabel, when } from "../lib/time";
import { EmptyState, PhotoPicker, notifyErr } from "../components/common";

/* ------------------------------------------------------------------ node types */
const TYPES = {
  start: { label: "Bắt đầu", color: "teal", icon: IconFlag, desc: "Thời điểm flow bắt đầu chạy" },
  post: { label: "Bài viết", color: "indigo", icon: IconPencil, desc: "Một bài với nội dung, ảnh, link" },
  batch: { label: "Nhiều bài", color: "violet", icon: IconStack2, desc: "Dán nhiều đoạn / thả nhiều ảnh, mỗi cái một bài" },
  wait: { label: "Chờ", color: "orange", icon: IconHourglass, desc: "Nghỉ một khoảng hoặc đợi tới giờ cố định" },
};

const ScheduleCtx = createContext({ times: {}, issues: {}, perNode: {} });

function nodeSummary(type, d, perNode) {
  if (type === "start") return d.mode === "at" && d.at ? `Lúc ${when(d.at)}` : "Ngay khi bấm Chạy";
  if (type === "post") return d.message?.trim() || (d.link ? d.link : d.photos?.length ? "Bài chỉ có ảnh" : "Chưa có nội dung");
  if (type === "batch") {
    const n = perNode || batchItems(d).length;
    return n ? `${n} bài · cách nhau ${d.gap || 1} ${unitLabel(d.unit)}` : "Chưa có nội dung";
  }
  if (type === "wait") return d.mode === "until" ? `Đợi tới ${d.time || "08:00"} lần kế tiếp` : `Chờ ${d.value || 0} ${unitLabel(d.unit)}`;
  return "";
}

const FlowNode = memo(function FlowNode({ id, type, data, selected }) {
  const { times, issues, perNode } = useContext(ScheduleCtx);
  const T = TYPES[type];
  const Icon = T.icon;
  const issue = issues[id];
  const t = times[id];
  const photos = type === "post" || type === "batch" ? data.photos || [] : [];
  const timeText = t ? (type === "wait" ? `→ ${hm(t)} · ${dayLabel(t)}` : `${hm(t)} · ${dayLabel(t)}`) : null;
  return (
    <div className={`fnode ${selected ? "selected" : ""} ${issue ? "has-issue" : ""}`}>
      {type !== "start" && <Handle type="target" position={Position.Top} />}
      <div className="fnode-h">
        <ThemeIcon size={26} radius="md" color={T.color} variant="light"><Icon size={16} /></ThemeIcon>
        <Text fw={600} size="sm" style={{ flex: 1 }}>{T.label}</Text>
        {timeText && <Badge size="sm" variant="light" color={type === "wait" ? "orange" : "gray"} style={{ textTransform: "none" }}>{timeText}</Badge>}
      </div>
      <div className="fnode-b">
        <Text size="sm" lineClamp={3} c={/^Chưa/.test(nodeSummary(type, data)) ? "dimmed" : undefined} style={{ whiteSpace: "pre-wrap" }}>
          {nodeSummary(type, data, perNode[id])}
        </Text>
        {photos.length > 0 && (
          <div className="fnode-photos">
            {photos.slice(0, 5).map((p, i) => <img key={p + i} src={imgUrl(p)} alt="" />)}
            {photos.length > 5 && <Badge variant="light" color="gray" h={40} radius="sm">+{photos.length - 5}</Badge>}
          </div>
        )}
        {issue && <Group gap={4} mt={8} c="orange"><IconAlertTriangle size={14} /><Text size="xs" fw={500}>{issue}</Text></Group>}
      </div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
});
const nodeTypes = { start: FlowNode, post: FlowNode, batch: FlowNode, wait: FlowNode };
const edgeDefaults = { type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 } };

/* ------------------------------------------------------------------ inspector */
function Inspector({ node, update, remove, duplicate }) {
  if (!node) {
    return <EmptyState icon={IconPointer} title="Chưa chọn khối nào" desc="Bấm vào một khối trên bảng vẽ để chỉnh nội dung, hoặc kéo khối mới từ bên trái vào." />;
  }
  const d = node.data;
  const T = TYPES[node.type];
  const set = (k) => (v) => update(node.id, { [k]: v?.currentTarget ? v.currentTarget.value : v });

  return (
    <Stack gap="md" p="md">
      <Group justify="space-between">
        <Group gap="sm">
          <ThemeIcon size={30} radius="md" color={T.color} variant="light"><T.icon size={18} /></ThemeIcon>
          <div><Text fw={600}>{T.label}</Text><Text size="xs" c="dimmed">{T.desc}</Text></div>
        </Group>
        {node.type !== "start" && (
          <Group gap={2}>
            <Tooltip label="Nhân bản"><ActionIcon variant="subtle" color="gray" onClick={() => duplicate(node.id)}><IconCopy size={18} /></ActionIcon></Tooltip>
            <Tooltip label="Xoá khối"><ActionIcon variant="subtle" color="red" onClick={() => remove(node.id)}><IconTrash size={18} /></ActionIcon></Tooltip>
          </Group>
        )}
      </Group>

      {node.type === "start" && (
        <>
          <SegmentedControl fullWidth value={d.mode} onChange={set("mode")} data={[{ value: "now", label: "Khi bấm Chạy" }, { value: "at", label: "Vào lúc…" }]} />
          {d.mode === "at" && (
            <DateTimePicker label="Thời điểm bắt đầu" valueFormat="HH:mm, DD/MM/YYYY" value={d.at ? new Date(d.at) : null}
              onChange={(v) => update(node.id, { at: v ? toLocalIso(v) : null })} minDate={new Date()} leftSection={<IconClock size={16} />} />
          )}
          <Text size="xs" c="dimmed">Các khối nối phía sau sẽ lần lượt tính giờ đăng từ thời điểm này.</Text>
        </>
      )}

      {node.type === "post" && (
        <>
          <Textarea label="Nội dung" autosize minRows={4} maxRows={12} value={d.message} onChange={set("message")} placeholder="Nội dung bài viết…" />
          <div><Text size="sm" fw={500} mb={6}>Ảnh</Text><PhotoPicker compact value={d.photos || []} onChange={set("photos")} /></div>
          <TextInput label="Link" placeholder="https://..." value={d.link} onChange={set("link")} />
        </>
      )}

      {node.type === "batch" && (
        <>
          <Textarea
            label="Nội dung các bài" autosize minRows={6} maxRows={16} value={d.text} onChange={set("text")}
            description={`Mỗi bài cách nhau bởi 1 dòng trống · ${splitParagraphs(d.text).length} đoạn`}
            placeholder={"Bài thứ nhất…\n\nBài thứ hai…\n\nBài thứ ba…"}
          />
          <div>
            <Text size="sm" fw={500} mb={2}>Ảnh</Text>
            <Text size="xs" c="dimmed" mb={6}>Ảnh thứ 1 đi với đoạn thứ 1, ảnh 2 với đoạn 2… Thả 10 ảnh mà không có chữ = 10 bài ảnh.</Text>
            <PhotoPicker compact value={d.photos || []} onChange={set("photos")} />
          </div>
          {(d.photos || []).length > splitParagraphs(d.text).length && (
            <TextInput label="Chú thích cho ảnh không có đoạn đi kèm" value={d.caption} onChange={set("caption")} placeholder="Có thể để trống" />
          )}
          <Group grow align="flex-end">
            <NumberInput label="Cách nhau" min={1} max={999} value={d.gap} onChange={(v) => update(node.id, { gap: Number(v) || 1 })} />
            <Select data={UNITS.map(({ value, label }) => ({ value, label }))} value={d.unit} onChange={set("unit")} allowDeselect={false} />
          </Group>
          <Alert variant="light" color="violet" py="xs">Khối này tạo <b>{batchItems(d).length}</b> bài.</Alert>
        </>
      )}

      {node.type === "wait" && (
        <>
          <SegmentedControl fullWidth value={d.mode} onChange={set("mode")} data={[{ value: "duration", label: "Chờ một khoảng" }, { value: "until", label: "Đợi tới giờ" }]} />
          {d.mode === "duration" ? (
            <Group grow align="flex-end">
              <NumberInput label="Thời gian chờ" min={0} max={999} value={d.value} onChange={(v) => update(node.id, { value: Number(v) || 0 })} />
              <Select data={UNITS.map(({ value, label }) => ({ value, label }))} value={d.unit} onChange={set("unit")} allowDeselect={false} />
            </Group>
          ) : (
            <TimeInput label="Giờ đăng tiếp theo" value={d.time} onChange={set("time")} description="Ví dụ 08:00: nếu đã qua 8h hôm nay thì chờ tới 8h hôm sau." />
          )}
        </>
      )}
    </Stack>
  );
}

function SchedulePreview({ schedule, onPick }) {
  const { posts } = schedule;
  if (!posts.length) return <EmptyState icon={IconCalendarEvent} title="Chưa có bài nào" desc="Thêm khối Bài viết hoặc Nhiều bài và nối với khối Bắt đầu." />;
  const first = posts[0].time, last = posts[posts.length - 1].time;
  return (
    <Stack p="md" gap="md">
      <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default-hover)">
        <Text fw={600}>{posts.length} bài sẽ được lên lịch</Text>
        <Text size="sm" c="dimmed">Từ {when(first)} đến {when(last)}</Text>
      </Paper>
      <Timeline bulletSize={22} lineWidth={2}>
        {posts.slice(0, 200).map((p, i) => (
          <Timeline.Item key={i} bullet={<IconClock size={12} />} title={<Text size="sm" fw={600}>{hm(p.time)} · {dayLabel(p.time)}</Text>}>
            <Group gap="xs" wrap="nowrap" mt={4} style={{ cursor: "pointer" }} onClick={() => onPick(p.nodeId)}>
              {p.photos[0] && <Image src={imgUrl(p.photos[0])} w={36} h={36} radius="sm" />}
              <Text size="xs" c="dimmed" lineClamp={2}>{p.message || (p.photos.length ? "Bài chỉ có ảnh" : p.link)}</Text>
            </Group>
          </Timeline.Item>
        ))}
      </Timeline>
    </Stack>
  );
}

/* ------------------------------------------------------------------ editor */
function Editor({ flow, onChange, onRun }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(flow.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flow.edges);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("props");
  const rf = useReactFlow();
  const wrap = useRef(null);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);

  // báo thay đổi lên trên để tự lưu (bỏ qua thay đổi chỉ do chọn/kích thước)
  const sig = JSON.stringify([nodes.map((n) => [n.id, n.type, n.data, Math.round(n.position.x), Math.round(n.position.y)]), edges.map((e) => [e.source, e.target])]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    onChange({ nodes: nodes.map(({ id, type, position, data, deletable }) => ({ id, type, position, data, ...(deletable === false ? { deletable } : {}) })), edges: edges.map(({ id, source, target }) => ({ id, source, target })) });
  }, [sig]); // eslint-disable-line

  const schedule = useMemo(() => computeSchedule(nodes, edges, now), [sig, now]); // eslint-disable-line
  const perNode = useMemo(() => { const m = {}; schedule.posts.forEach((p) => (m[p.nodeId] = (m[p.nodeId] || 0) + 1)); return m; }, [schedule]);
  const ctx = useMemo(() => ({ times: schedule.times, issues: schedule.issues, perNode }), [schedule, perNode]);

  const selectedNode = nodes.find((n) => n.id === selected) || null;

  const update = useCallback((id, patch) => setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))), [setNodes]);
  const remove = useCallback((id) => {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
    setSelected(null);
  }, [setNodes, setEdges]);
  const duplicate = useCallback((id) => {
    const n = nodes.find((x) => x.id === id);
    if (!n) return;
    const nid = newId();
    setNodes((ns) => [...ns.map((x) => ({ ...x, selected: false })), { ...n, id: nid, selected: true, position: { x: n.position.x + 300, y: n.position.y }, data: structuredClone(n.data), deletable: undefined }]);
    setSelected(nid);
  }, [nodes, setNodes]);

  const addNode = useCallback((type, position) => {
    const id = newId();
    let pos = position;
    let from = null;
    if (!pos) {
      // nối tiếp sau khối đang chọn, hoặc khối cuối cùng của chuỗi
      const hasOut = new Set(edges.map((e) => e.source));
      from = nodes.find((n) => n.id === selected) || [...nodes].reverse().find((n) => !hasOut.has(n.id)) || nodes[nodes.length - 1];
      pos = from ? { x: from.position.x, y: from.position.y + 170 } : { x: 0, y: 0 };
      if (from && hasOut.has(from.id)) pos = { x: from.position.x + 300, y: from.position.y + 170 };
    }
    setNodes((ns) => [...ns.map((n) => ({ ...n, selected: false })), { id, type, position: pos, data: NODE_DEFAULTS[type](), selected: true }]);
    if (from && type !== "start") setEdges((es) => addEdge({ id: `e_${from.id}_${id}`, source: from.id, target: id }, es));
    setSelected(id);
    setTab("props");
    if (!position) setTimeout(() => rf.fitView({ nodes: [{ id }], duration: 300, maxZoom: 1, padding: 1.2 }), 50);
  }, [nodes, edges, selected, setNodes, setEdges, rf]);

  const onConnect = useCallback((c) => setEdges((es) => addEdge({ ...c, id: `e_${c.source}_${c.target}` }, es.filter((e) => !(e.target === c.target && e.source === c.source)))), [setEdges]);
  const onDrop = (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("application/supload-node");
    if (!TYPES[type]) return;
    addNode(type, rf.screenToFlowPosition({ x: e.clientX - 130, y: e.clientY - 30 }));
  };

  return (
    <ScheduleCtx.Provider value={ctx}>
      <div className="flow-shell">
        {/* palette */}
        <div className="flow-panel" style={{ borderRight: "1px solid var(--mantine-color-default-border)" }}>
          <Stack gap="xs" p="md" className="palette">
            <Text size="xs" fw={700} c="dimmed" tt="uppercase" className="palette-help">Khối</Text>
            {Object.entries(TYPES).map(([type, T]) => (
              <Paper
                key={type} withBorder p="sm" radius="md" className="palette-item" draggable
                onDragStart={(e) => { e.dataTransfer.setData("application/supload-node", type); e.dataTransfer.effectAllowed = "move"; }}
                onClick={() => addNode(type)}
              >
                <Group gap="sm" wrap="nowrap" align="flex-start">
                  <ThemeIcon size={28} radius="md" color={T.color} variant="light"><T.icon size={16} /></ThemeIcon>
                  <div style={{ minWidth: 0 }}><Text size="sm" fw={600}>{T.label}</Text><Text size="xs" c="dimmed" lh={1.35} className="palette-desc">{T.desc}</Text></div>
                </Group>
              </Paper>
            ))}
            <Text size="xs" c="dimmed" mt="sm" className="palette-help">Kéo khối vào bảng vẽ, hoặc bấm để thêm nối tiếp khối đang chọn. Kéo từ chấm dưới khối này sang khối khác để nối. Chọn khối/đường nối và nhấn <b>Delete</b> để xoá.</Text>
          </Stack>
        </div>

        {/* canvas */}
        <div className="flow-canvas" ref={wrap} onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes} defaultEdgeOptions={edgeDefaults}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onSelectionChange={({ nodes: sel }) => { const id = sel[0]?.id || null; setSelected(id); if (id) setTab("props"); }}
            fitView fitViewOptions={{ maxZoom: 1, padding: 0.3 }} minZoom={0.2} maxZoom={1.6}
            deleteKeyCode={["Delete", "Backspace"]} proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} size={1.2} />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap className="flow-minimap" style={{ width: 150, height: 100 }} pannable zoomable position="bottom-right" nodeStrokeWidth={3} nodeColor={(n) => `var(--mantine-color-${TYPES[n.type]?.color || "gray"}-5)`} />
          </ReactFlow>
          <Paper withBorder shadow="sm" radius="md" p={6} pos="absolute" top={12} right={12} style={{ zIndex: 5 }}>
            <Group gap="xs">
              <Badge variant="light" size="lg" style={{ textTransform: "none" }}>{schedule.posts.length} bài</Badge>
              {Object.keys(schedule.issues).length > 0 && (
                <Tooltip label="Một số khối cần kiểm tra (viền cam)"><Badge color="orange" variant="light" size="lg" leftSection={<IconAlertTriangle size={14} />} style={{ textTransform: "none" }}>{Object.keys(schedule.issues).length} cảnh báo</Badge></Tooltip>
              )}
              <Button size="xs" leftSection={<IconPlayerPlay size={14} />} onClick={() => onRun(schedule)} disabled={!schedule.posts.length}>Chạy flow</Button>
            </Group>
          </Paper>
        </div>

        {/* inspector */}
        <div className="flow-panel" style={{ borderLeft: "1px solid var(--mantine-color-default-border)", display: "flex", flexDirection: "column" }}>
          <Tabs value={tab} onChange={setTab} style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
            <Tabs.List grow>
              <Tabs.Tab value="props" leftSection={<IconAdjustments size={16} />}>Thuộc tính</Tabs.Tab>
              <Tabs.Tab value="plan" leftSection={<IconCalendarEvent size={16} />}>Lịch dự kiến <Badge size="xs" variant="light" ml={4}>{schedule.posts.length}</Badge></Tabs.Tab>
            </Tabs.List>
            <ScrollArea style={{ flex: 1 }}>
              <Tabs.Panel value="props"><Inspector node={selectedNode} update={update} remove={remove} duplicate={duplicate} /></Tabs.Panel>
              <Tabs.Panel value="plan">
                <SchedulePreview schedule={schedule} onPick={(id) => { setNodes((ns) => ns.map((n) => ({ ...n, selected: n.id === id }))); setSelected(id); setTab("props"); rf.fitView({ nodes: [{ id }], duration: 300, maxZoom: 1, padding: 1.2 }); }} />
              </Tabs.Panel>
            </ScrollArea>
          </Tabs>
        </div>
      </div>
    </ScheduleCtx.Provider>
  );
}

/* ------------------------------------------------------------------ page */
export default function Flow() {
  const { state, refresh, setView } = useApp();
  const [flows, setFlows] = useState(null);
  const [currentId, setCurrentId] = useState(null);
  const [saveState, setSaveState] = useState("saved");
  const current = flows?.find((f) => f.id === currentId) || null;

  const persist = useCallback(async (f) => {
    setSaveState("saving");
    try { await api(`/api/flows/${f.id}`, { method: "PUT", body: f }); setSaveState("saved"); }
    catch (e) { setSaveState("error"); notifyErr(e.message, "Không lưu được flow"); }
  }, []);
  const persistLater = useDebouncedCallback(persist, 700);

  const createFlow = useCallback(async (kind = "sample", base) => {
    const f = { id: newId("f"), name: base?.name ? `${base.name} (bản sao)` : kind === "blank" ? "Flow mới" : "Chiến dịch mẫu",
      ...(base ? structuredClone({ nodes: base.nodes, edges: base.edges }) : kind === "blank"
        ? { nodes: [{ id: newId(), type: "start", position: { x: 0, y: 0 }, data: NODE_DEFAULTS.start(), deletable: false }], edges: [] }
        : sampleFlow()) };
    await persist(f);
    setFlows((fs) => [...(fs || []), f]);
    setCurrentId(f.id);
  }, [persist]);

  useEffect(() => {
    api("/api/flows").then(({ flows: fs }) => {
      setFlows(fs);
      if (fs.length) setCurrentId(fs.sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""))[0].id);
      else createFlow("sample");
    }, (e) => notifyErr(e.message));
  }, []); // eslint-disable-line

  const patchCurrent = (patch) => {
    setFlows((fs) => fs.map((f) => (f.id === currentId ? { ...f, ...patch } : f)));
    setSaveState("dirty");
    persistLater({ ...current, ...patch });
  };

  const deleteFlow = () => modals.openConfirmModal({
    title: `Xoá flow “${current.name}”?`, children: <Text size="sm">Flow sẽ bị xoá. Các bài đã đưa vào lịch đăng không bị ảnh hưởng.</Text>,
    labels: { confirm: "Xoá", cancel: "Huỷ" }, confirmProps: { color: "red" },
    onConfirm: async () => {
      await api(`/api/flows/${current.id}`, { method: "DELETE" });
      const rest = flows.filter((f) => f.id !== current.id);
      setFlows(rest);
      if (rest.length) setCurrentId(rest[0].id); else createFlow("blank");
    },
  });

  const run = (schedule) => {
    if (!configured(state.settings)) {
      modals.openConfirmModal({ title: "Chưa kết nối Page", children: <Text size="sm">Cần kết nối Page trước khi chạy flow.</Text>, labels: { confirm: "Mở Cài đặt", cancel: "Để sau" }, onConfirm: () => setView("settings") });
      return;
    }
    const { posts, issues } = schedule;
    const nIssues = Object.keys(issues).length;
    modals.openConfirmModal({
      title: "Chạy flow và lên lịch?",
      children: (
        <Stack gap="xs">
          <Text size="sm">Sẽ thêm <b>{posts.length} bài</b> vào Lịch đăng, từ <b>{when(posts[0].time)}</b> đến <b>{when(posts[posts.length - 1].time)}</b>.</Text>
          {nIssues > 0 && <Alert color="orange" variant="light" py="xs" icon={<IconAlertTriangle size={16} />}>{nIssues} khối có cảnh báo sẽ bị bỏ qua.</Alert>}
          <Text size="xs" c="dimmed">Ứng dụng phải đang chạy vào các thời điểm này để đăng bài.</Text>
        </Stack>
      ),
      labels: { confirm: `Lên lịch ${posts.length} bài`, cancel: "Huỷ" },
      onConfirm: async () => {
        try {
          const soon = Date.now() + 60000;
          const body = { name: current.name, posts: posts.map((p) => ({ message: p.message, link: p.link, photos: p.photos, scheduled_at: +p.time > soon ? toLocalIso(p.time) : null })) };
          const { count } = await api("/api/flows/run", { method: "POST", body });
          refresh();
          modals.openConfirmModal({
            title: <Group gap="xs"><ThemeIcon color="teal" radius="xl" size="sm"><IconCheck size={14} /></ThemeIcon>Đã lên lịch {count} bài</Group>,
            children: <Text size="sm">Bạn có thể theo dõi và sửa từng bài trong Lịch đăng.</Text>,
            labels: { confirm: "Xem Lịch đăng", cancel: "Ở lại" }, onConfirm: () => setView("queue"),
          });
        } catch (e) { notifyErr(e.message); }
      },
    });
  };

  if (!flows || !current) return null;

  return (
    <div>
      <Group px="md" py="sm" gap="sm" wrap="wrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        <Select
          w={220} value={currentId} onChange={(v) => v && setCurrentId(v)} allowDeselect={false} leftSection={<IconFile size={16} />}
          data={flows.map((f) => ({ value: f.id, label: f.name }))} aria-label="Chọn flow" comboboxProps={{ withinPortal: true }}
        />
        <TextInput w={240} value={current.name} onChange={(e) => patchCurrent({ name: e.currentTarget.value })} aria-label="Tên flow" placeholder="Tên flow" />
        <Text size="xs" c={saveState === "error" ? "red" : "dimmed"}>
          {saveState === "saving" || saveState === "dirty" ? "Đang lưu…" : saveState === "error" ? "Lưu thất bại" : "Đã lưu"}
        </Text>
        <Group gap="xs" ml="auto">
          <Menu position="bottom-end" withinPortal>
            <Menu.Target><Button variant="default" leftSection={<IconPlus size={16} />}>Flow mới</Button></Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconFile size={16} />} onClick={() => createFlow("blank")}>Flow trống</Menu.Item>
              <Menu.Item leftSection={<IconTemplate size={16} />} onClick={() => createFlow("sample")}>Từ mẫu có sẵn</Menu.Item>
            </Menu.Dropdown>
          </Menu>
          <Menu position="bottom-end" withinPortal>
            <Menu.Target><ActionIcon variant="default" size="lg" aria-label="Thêm"><IconDots size={18} /></ActionIcon></Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={() => createFlow("copy", current)}>Nhân bản flow</Menu.Item>
              <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={deleteFlow}>Xoá flow</Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
      <ReactFlowProvider key={current.id}>
        <Editor flow={current} onChange={patchCurrent} onRun={run} />
      </ReactFlowProvider>
    </div>
  );
}
