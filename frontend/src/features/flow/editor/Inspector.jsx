import { Accordion, ActionIcon, Alert, Group, Stack, Switch, Text, TextInput, Textarea, ThemeIcon, Tooltip } from "@mantine/core";
import { IconAdjustments, IconCopy, IconEyeOff, IconPointer, IconTrash } from "@tabler/icons-react";

import { EmptyState } from "../../../components";
import { nodeDef, withDefaults } from "../engine/nodes";
import { NodeFields } from "./NodeFields";

/** Bảng Thuộc tính: tự sinh từ khai báo `fields` của loại khối (engine/nodes.jsx). */
export function Inspector({ node, update, remove, duplicate }) {
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
