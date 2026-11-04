import { createContext, memo, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow, ReactFlowProvider, Background, Controls, MiniMap, Handle, Position, NodeToolbar, addEdge, useEdgesState,
  useNodesState, useReactFlow, MarkerType,
} from "@xyflow/react";
import {
  Accordion, ActionIcon, Alert, Badge, Button, Group, Menu, Paper, ScrollArea, Select, Stack, Switch, Tabs, Text, TextInput,
  Textarea, ThemeIcon, Timeline, Tooltip, Image,
} from "@mantine/core";
import { useDebouncedCallback } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import {
  IconPlayerPlay, IconPlus, IconTrash, IconCopy, IconDots, IconAlertTriangle, IconCalendarEvent, IconAdjustments, IconCheck,
  IconClock, IconTemplate, IconFile, IconPointer, IconEye, IconEyeOff, IconDice5, IconNote,
} from "@tabler/icons-react";

import { useApp } from "../App";
import { api, configured, imgUrl } from "../lib/api";
import { computeSchedule, newId, newNode, sampleFlow } from "../lib/flow";
import { NODES, NODE_GROUPS, nodeDef, withDefaults } from "../lib/nodes";
import { dayLabel, hm, toLocalIso, when } from "../lib/time";
import { EmptyState, notifyErr } from "../components/common";
import { NodeFields } from "../components/NodeFields";

const FlowCtx = createContext(null);

/* ------------------------------------------------------------------ node trên bảng vẽ */
const FlowNode = memo(function FlowNode({ id, type, data, selected }) {
  const { schedule, actions } = useContext(FlowCtx);
  const def = nodeDef(type);
  const d = withDefaults(type, data);
  const Icon = def.icon;
  const issue = !d.disabled && schedule.issues[id];
  const t = schedule.times[id];
  const nPosts = schedule.perNode[id] || 0;
  const nRuns = schedule.runs[id] || 0;
  const summary = def.summary(d) ?? (type === "start" && t ? `Lúc ${when(t)}` : "Chưa cấu hình");
  const photos = (d.photos || []).slice(0, 5);
  const timeBadge = t && !d.disabled ? `${["wait", "window"].includes(type) ? "→ " : ""}${hm(t)} · ${dayLabel(t)}` : null;

  return (
    <div className={`fnode ${selected ? "selected" : ""} ${issue ? "has-issue" : ""} ${d.disabled ? "disabled" : ""}`}>
      <NodeToolbar isVisible={selected} position={Position.Top} offset={8}>
        <Paper withBorder shadow="sm" radius="md" p={2}>
          <Group gap={2}>
            <Tooltip label={d.disabled ? "Bật khối" : "Tắt khối (bỏ qua)"}><ActionIcon variant="subtle" color="gray" onClick={() => actions.update(id, { disabled: !d.disabled })}>{d.disabled ? <IconEye size={16} /> : <IconEyeOff size={16} />}</ActionIcon></Tooltip>
            {def.deletable !== false && <Tooltip label="Nhân bản"><ActionIcon variant="subtle" color="gray" onClick={() => actions.duplicate(id)}><IconCopy size={16} /></ActionIcon></Tooltip>}
            {def.deletable !== false && <Tooltip label="Xoá"><ActionIcon variant="subtle" color="red" onClick={() => actions.remove(id)}><IconTrash size={16} /></ActionIcon></Tooltip>}
          </Group>
        </Paper>
      </NodeToolbar>
      {def.target !== false && <Handle type="target" position={Position.Top} />}
      <div className="fnode-h">
        <ThemeIcon size={26} radius="md" color={def.color} variant="light"><Icon size={16} /></ThemeIcon>
        <Text fw={600} size="sm" style={{ flex: 1, minWidth: 0 }} truncate>{d.title?.trim() || def.label}</Text>
        {d.disabled ? <Badge size="sm" color="gray" variant="outline">Đang tắt</Badge>
          : timeBadge && <Badge size="sm" variant="light" color={["wait", "window"].includes(type) ? def.color : "gray"} style={{ textTransform: "none" }}>{timeBadge}</Badge>}
      </div>
      <div className="fnode-b">
        {d.title?.trim() && <Text size="xs" c="dimmed" mb={2}>{def.label}</Text>}
        <Text size="sm" lineClamp={3} c={summary === "Chưa cấu hình" ? "dimmed" : undefined} style={{ whiteSpace: "pre-wrap" }}>{summary}</Text>
        {photos.length > 0 && (
          <div className="fnode-photos">
            {photos.map((p, i) => <img key={p + i} src={imgUrl(p)} alt="" />)}
            {(d.photos || []).length > 5 && <Badge variant="light" color="gray" h={40} radius="sm">+{d.photos.length - 5}</Badge>}
          </div>
        )}
        {!d.disabled && (nPosts > 0 || nRuns > 1) && (
          <Group gap={6} mt={8}>
            {nPosts > 0 && <Badge size="xs" variant="dot" color={def.color} style={{ textTransform: "none" }}>{nPosts} bài</Badge>}
            {nRuns > 1 && <Badge size="xs" variant="dot" color="grape" style={{ textTransform: "none" }}>chạy {nRuns} lần</Badge>}
          </Group>
        )}
        {d.note?.trim() && <Group gap={4} mt={8} c="dimmed" wrap="nowrap" align="flex-start"><IconNote size={13} style={{ flex: "none", marginTop: 2 }} /><Text size="xs" lineClamp={2}>{d.note}</Text></Group>}
        {issue && <Group gap={4} mt={8} c="orange"><IconAlertTriangle size={14} /><Text size="xs" fw={500}>{issue}</Text></Group>}
      </div>
      {def.source !== false && <Handle type="source" position={Position.Bottom} />}
    </div>
  );
});
const nodeTypes = Object.fromEntries(Object.keys(NODES).map((k) => [k, FlowNode]));
const edgeDefaults = { type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 } };

/* ------------------------------------------------------------------ bảng thuộc tính */
function Inspector({ node, update, remove, duplicate }) {
  if (!node) return <EmptyState icon={IconPointer} title="Chưa chọn khối nào" desc="Bấm vào một khối trên bảng vẽ để chỉnh cấu hình, hoặc kéo khối mới từ bên trái vào." />;
  const def = nodeDef(node.type);
  const d = withDefaults(node.type, node.data);
  const patch = (p) => update(node.id, p);
  return (
    <Stack gap="md" p="md">
      <Group justify="space-between" wrap="nowrap">
        <Group gap="sm" wrap="nowrap">
          <ThemeIcon size={32} radius="md" color={def.color} variant="light"><def.icon size={18} /></ThemeIcon>
          <div><Text fw={600}>{def.label}</Text><Text size="xs" c="dimmed">{def.desc}</Text></div>
        </Group>
        {def.deletable !== false && (
          <Group gap={2} wrap="nowrap">
            <Tooltip label="Nhân bản"><ActionIcon variant="subtle" color="gray" onClick={() => duplicate(node.id)}><IconCopy size={18} /></ActionIcon></Tooltip>
            <Tooltip label="Xoá khối"><ActionIcon variant="subtle" color="red" onClick={() => remove(node.id)}><IconTrash size={18} /></ActionIcon></Tooltip>
          </Group>
        )}
      </Group>

      {d.disabled && <Alert color="gray" variant="light" py="xs" icon={<IconEyeOff size={16} />}>Khối đang tắt: bị bỏ qua khi chạy, các khối phía sau vẫn chạy bình thường.</Alert>}

      <NodeFields fields={def.fields} data={d} onChange={patch} />

      <Accordion variant="contained" radius="md">
        <Accordion.Item value="common">
          <Accordion.Control icon={<IconAdjustments size={16} />}><Text size="sm" fw={500}>Tuỳ chỉnh khối</Text></Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              <TextInput label="Tên hiển thị" placeholder={def.label} value={d.title || ""} onChange={(e) => patch({ title: e.currentTarget.value })} />
              <Textarea label="Ghi chú" placeholder="Ghi chú cho bản thân, không được đăng" autosize minRows={2} value={d.note || ""} onChange={(e) => patch({ note: e.currentTarget.value })} />
              {node.type !== "start" && <Switch label="Tắt khối này" description="Bỏ qua khi chạy nhưng vẫn giữ các khối nối phía sau" checked={!!d.disabled} onChange={(e) => patch({ disabled: e.currentTarget.checked })} />}
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

function SchedulePreview({ schedule, onPick }) {
  const { posts, truncated } = schedule;
  if (!posts.length) return <EmptyState icon={IconCalendarEvent} title="Chưa có bài nào" desc="Thêm khối Bài viết hoặc Nhiều bài và nối với khối Bắt đầu." />;
  const first = posts[0].time, last = posts[posts.length - 1].time;
  return (
    <Stack p="md" gap="md">
      <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default-hover)">
        <Text fw={600}>{posts.length} bài sẽ được lên lịch</Text>
        <Text size="sm" c="dimmed">Từ {when(first)} đến {when(last)}</Text>
      </Paper>
      {truncated && <Alert color="orange" variant="light" py="xs">Flow tạo quá nhiều bài, chỉ hiển thị 1.000 bài đầu.</Alert>}
      <Timeline bulletSize={22} lineWidth={2}>
        {posts.slice(0, 200).map((p, i) => (
          <Timeline.Item key={i} bullet={<IconClock size={12} />} title={<Text size="sm" fw={600}>{hm(p.time)} · {dayLabel(p.time)}</Text>}>
            <Group gap="xs" wrap="nowrap" mt={4} style={{ cursor: "pointer" }} onClick={() => onPick(p.nodeId)}>
              {p.photos[0] && <Image src={imgUrl(p.photos[0])} w={36} h={36} radius="sm" />}
              <Text size="xs" c="dimmed" lineClamp={3} style={{ whiteSpace: "pre-wrap" }}>{p.message || (p.photos.length ? "Bài chỉ có ảnh" : p.link)}</Text>
            </Group>
          </Timeline.Item>
        ))}
      </Timeline>
      {posts.length > 200 && <Text size="xs" c="dimmed">… và {posts.length - 200} bài nữa</Text>}
    </Stack>
  );
}

/* ------------------------------------------------------------------ editor */
function Editor({ flow, onChange, onRun, onReseed }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(flow.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flow.edges);
  const [selected, setSelected] = useState(null);
  const [tab, setTab] = useState("props");
  const rf = useReactFlow();
  const [now, setNow] = useState(() => new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);

  const sig = JSON.stringify([nodes.map((n) => [n.id, n.type, n.data, Math.round(n.position.x), Math.round(n.position.y)]), edges.map((e) => [e.source, e.target])]);
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    onChange({
      nodes: nodes.map(({ id, type, position, data, deletable }) => ({ id, type, position, data, ...(deletable === false ? { deletable } : {}) })),
      edges: edges.map(({ id, source, target }) => ({ id, source, target })),
    });
  }, [sig]); // eslint-disable-line

  const schedule = useMemo(() => computeSchedule(nodes, edges, now, flow.seed || flow.id), [sig, now, flow.seed]); // eslint-disable-line
  const selectedNode = nodes.find((n) => n.id === selected) || null;

  const update = useCallback((id, patch) => setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n))), [setNodes]);
  const remove = useCallback((id) => {
    setNodes((ns) => ns.filter((n) => n.id !== id));
    setEdges((es) => es.filter((e) => e.source !== id && e.target !== id));
    setSelected(null);
  }, [setNodes, setEdges]);
  const duplicate = useCallback((id) => {
    setNodes((ns) => {
      const n = ns.find((x) => x.id === id);
      if (!n) return ns;
      const copy = { ...newNode(n.type, { x: n.position.x + 300, y: n.position.y }, structuredClone(n.data)), selected: true };
      setTimeout(() => setSelected(copy.id));
      return [...ns.map((x) => ({ ...x, selected: false })), copy];
    });
  }, [setNodes]);

  const addNode = useCallback((type, position) => {
    let pos = position;
    let from = null;
    if (!pos) {
      const hasOut = new Set(edges.map((e) => e.source));
      from = nodes.find((n) => n.id === selected) || [...nodes].reverse().find((n) => !hasOut.has(n.id) && nodeDef(n.type).source !== false) || nodes[nodes.length - 1];
      pos = from ? { x: from.position.x + (hasOut.has(from.id) ? 300 : 0), y: from.position.y + 170 } : { x: 0, y: 0 };
    }
    const n = { ...newNode(type, pos), selected: true };
    setNodes((ns) => [...ns.map((x) => ({ ...x, selected: false })), n]);
    if (from && nodeDef(type).target !== false && nodeDef(from.type).source !== false) setEdges((es) => addEdge({ id: `e_${from.id}_${n.id}`, source: from.id, target: n.id }, es));
    setSelected(n.id);
    setTab("props");
    if (!position) setTimeout(() => rf.fitView({ nodes: [{ id: n.id }], duration: 300, maxZoom: 1, padding: 1.2 }), 50);
  }, [nodes, edges, selected, setNodes, setEdges, rf]);

  const onConnect = useCallback((c) => setEdges((es) => addEdge({ ...c, id: `e_${c.source}_${c.target}` }, es)), [setEdges]);
  const onDrop = (e) => {
    e.preventDefault();
    const type = e.dataTransfer.getData("application/supload-node");
    if (!NODES[type]) return;
    addNode(type, rf.screenToFlowPosition({ x: e.clientX - 130, y: e.clientY - 30 }));
  };
  const focusNode = (id) => {
    setNodes((ns) => ns.map((n) => ({ ...n, selected: n.id === id })));
    setSelected(id);
    setTab("props");
    rf.fitView({ nodes: [{ id }], duration: 300, maxZoom: 1, padding: 1.2 });
  };

  const ctx = useMemo(() => ({ schedule, actions: { update, remove, duplicate } }), [schedule, update, remove, duplicate]);
  const nIssues = Object.keys(schedule.issues).filter((id) => !nodes.find((n) => n.id === id)?.data?.disabled).length;

  return (
    <FlowCtx.Provider value={ctx}>
      <div className="flow-shell">
        <div className="flow-panel" style={{ borderRight: "1px solid var(--mantine-color-default-border)" }}>
          <Stack gap="xs" p="md" className="palette">
            {NODE_GROUPS.map((g) => (
              <Stack key={g} gap="xs" className="palette-group">
                <Text size="xs" fw={700} c="dimmed" tt="uppercase" mt={g === NODE_GROUPS[0] ? 0 : "xs"} className="palette-help">{g}</Text>
                {Object.entries(NODES).filter(([, def]) => def.group === g).map(([type, def]) => (
                  <Paper key={type} withBorder p="sm" radius="md" className="palette-item" draggable
                    onDragStart={(e) => { e.dataTransfer.setData("application/supload-node", type); e.dataTransfer.effectAllowed = "move"; }}
                    onClick={() => addNode(type)}>
                    <Group gap="sm" wrap="nowrap" align="flex-start">
                      <ThemeIcon size={28} radius="md" color={def.color} variant="light"><def.icon size={16} /></ThemeIcon>
                      <div style={{ minWidth: 0 }}><Text size="sm" fw={600}>{def.label}</Text><Text size="xs" c="dimmed" lh={1.35} className="palette-desc">{def.desc}</Text></div>
                    </Group>
                  </Paper>
                ))}
              </Stack>
            ))}
            <Text size="xs" c="dimmed" mt="sm" className="palette-help">Kéo khối vào bảng vẽ, hoặc bấm để thêm nối tiếp khối đang chọn. Kéo từ chấm dưới khối sang khối khác để nối; một khối có thể rẽ nhiều nhánh. Chọn khối/đường nối và nhấn <b>Delete</b> để xoá.</Text>
          </Stack>
        </div>

        <div className="flow-canvas" onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes} edges={edges} nodeTypes={nodeTypes} defaultEdgeOptions={edgeDefaults}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect}
            onSelectionChange={({ nodes: sel }) => { const id = sel[0]?.id || null; setSelected(id); if (id) setTab("props"); }}
            fitView fitViewOptions={{ maxZoom: 1, padding: 0.3 }} minZoom={0.2} maxZoom={1.6}
            deleteKeyCode={["Delete", "Backspace"]} proOptions={{ hideAttribution: true }}
          >
            <Background gap={20} size={1.2} />
            <Controls showInteractive={false} position="bottom-left" />
            <MiniMap className="flow-minimap" style={{ width: 150, height: 100 }} pannable zoomable position="bottom-right" nodeStrokeWidth={3} nodeColor={(n) => `var(--mantine-color-${nodeDef(n.type).color}-5)`} />
          </ReactFlow>
          <Paper withBorder shadow="sm" radius="md" p={6} pos="absolute" top={12} right={12} style={{ zIndex: 5 }}>
            <Group gap="xs">
              <Badge variant="light" size="lg" style={{ textTransform: "none" }}>{schedule.posts.length} bài</Badge>
              {nIssues > 0 && <Tooltip label="Một số khối cần kiểm tra (viền cam)"><Badge color="orange" variant="light" size="lg" leftSection={<IconAlertTriangle size={14} />} style={{ textTransform: "none" }}>{nIssues} cảnh báo</Badge></Tooltip>}
              <Tooltip label="Xáo lại các lựa chọn ngẫu nhiên ({a|b}, phiên bản, thứ tự, thời gian chờ)"><ActionIcon variant="default" size="lg" onClick={onReseed} aria-label="Xáo lại"><IconDice5 size={18} /></ActionIcon></Tooltip>
              <Button size="xs" leftSection={<IconPlayerPlay size={14} />} onClick={() => onRun(schedule)} disabled={!schedule.posts.length}>Chạy flow</Button>
            </Group>
          </Paper>
        </div>

        <div className="flow-panel" style={{ borderLeft: "1px solid var(--mantine-color-default-border)", display: "flex", flexDirection: "column" }}>
          <Tabs value={tab} onChange={setTab} style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
            <Tabs.List grow>
              <Tabs.Tab value="props" leftSection={<IconAdjustments size={16} />}>Thuộc tính</Tabs.Tab>
              <Tabs.Tab value="plan" leftSection={<IconCalendarEvent size={16} />}>Lịch dự kiến <Badge size="xs" variant="light" ml={4}>{schedule.posts.length}</Badge></Tabs.Tab>
            </Tabs.List>
            <ScrollArea style={{ flex: 1 }}>
              <Tabs.Panel value="props"><Inspector node={selectedNode} update={update} remove={remove} duplicate={duplicate} /></Tabs.Panel>
              <Tabs.Panel value="plan"><SchedulePreview schedule={schedule} onPick={focusNode} /></Tabs.Panel>
            </ScrollArea>
          </Tabs>
        </div>
      </div>
    </FlowCtx.Provider>
  );
}

/* ------------------------------------------------------------------ trang */
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
    const body = base
      ? structuredClone({ nodes: base.nodes, edges: base.edges, seed: newId("s") })
      : kind === "blank" ? { nodes: [newNode("start", { x: 0, y: 0 })], edges: [], seed: newId("s") } : sampleFlow();
    const f = { id: newId("f"), name: base?.name ? `${base.name} (bản sao)` : kind === "blank" ? "Flow mới" : "Chiến dịch mẫu", ...body };
    await persist(f);
    setFlows((fs) => [...(fs || []), f]);
    setCurrentId(f.id);
  }, [persist]);

  useEffect(() => {
    api("/api/flows").then(({ flows: fs }) => {
      setFlows(fs);
      if (fs.length) setCurrentId([...fs].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""))[0].id);
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
    const { posts } = schedule;
    modals.openConfirmModal({
      title: "Chạy flow và lên lịch?",
      children: (
        <Stack gap="xs">
          <Text size="sm">Sẽ thêm <b>{posts.length} bài</b> vào Lịch đăng, từ <b>{when(posts[0].time)}</b> đến <b>{when(posts[posts.length - 1].time)}</b>.</Text>
          <Text size="xs" c="dimmed">Các lựa chọn ngẫu nhiên được giữ đúng như trong Lịch dự kiến. Ứng dụng phải đang chạy vào các thời điểm này để đăng bài.</Text>
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
        <Select w={220} value={currentId} onChange={(v) => v && setCurrentId(v)} allowDeselect={false} leftSection={<IconFile size={16} />}
          data={flows.map((f) => ({ value: f.id, label: f.name }))} aria-label="Chọn flow" comboboxProps={{ withinPortal: true }} />
        <TextInput w={240} value={current.name} onChange={(e) => patchCurrent({ name: e.currentTarget.value })} aria-label="Tên flow" placeholder="Tên flow" />
        <Text size="xs" c={saveState === "error" ? "red" : "dimmed"}>{saveState === "saving" || saveState === "dirty" ? "Đang lưu…" : saveState === "error" ? "Lưu thất bại" : "Đã lưu"}</Text>
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
        <Editor flow={current} onChange={patchCurrent} onRun={run} onReseed={() => patchCurrent({ seed: newId("s") })} />
      </ReactFlowProvider>
    </div>
  );
}
