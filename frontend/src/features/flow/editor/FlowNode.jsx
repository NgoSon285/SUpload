import { memo, useContext } from "react";
import { Handle, MarkerType, NodeToolbar, Position } from "@xyflow/react";
import { ActionIcon, Badge, Group, Paper, Text, ThemeIcon, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconCopy, IconEye, IconEyeOff, IconNote, IconTrash } from "@tabler/icons-react";

import { imgUrl } from "../../../api/client";
import { dayLabel, hm, when } from "../../../lib/time";
import { NODES, nodeDef, withDefaults } from "../engine/nodes";
import { FlowCtx } from "./context";

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
  const hasVideo = type === "post" && d.media && d.media !== "photo";
  const photos = hasVideo ? [] : (d.photos || []).slice(0, 5);
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
        {hasVideo && <Badge mt={8} size="sm" variant="light" color={d.media === "reel" ? "violet" : "blue"}>{d.media === "reel" ? "Reels" : "Video"}{d.video ? "" : " · chưa chọn video"}</Badge>}
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

export const nodeTypes = Object.fromEntries(Object.keys(NODES).map((k) => [k, FlowNode]));
export const edgeDefaults = { type: "smoothstep", markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18 } };
