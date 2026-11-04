import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addEdge, Background, Controls, MiniMap, ReactFlow, useEdgesState, useNodesState, useReactFlow,
} from "@xyflow/react";
import { ActionIcon, Badge, Button, Group, Paper, ScrollArea, Stack, Tabs, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { IconAdjustments, IconAlertTriangle, IconCalendarEvent, IconDice5, IconPlayerPlay } from "@tabler/icons-react";

import { NODE_GROUPS, NODES, nodeDef } from "../engine/nodes";
import { computeSchedule, newNode } from "../engine/schedule";
import { FlowCtx } from "./context";
import { edgeDefaults, nodeTypes } from "./FlowNode";
import { Inspector } from "./Inspector";
import { SchedulePreview } from "./SchedulePreview";

/** Trình dựng flow: bảng khối (trái), bảng vẽ React Flow (giữa), thuộc tính / lịch dự kiến (phải). */
export function FlowEditor({ flow, onChange, onRun, onReseed }) {
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
              <Badge data-testid="flow-count" variant="light" size="lg" style={{ textTransform: "none" }}>{schedule.posts.length} bài</Badge>
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
