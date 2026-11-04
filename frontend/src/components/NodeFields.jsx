import { Alert, Chip, Group, NumberInput, Select, SegmentedControl, Stack, Switch, Text, TextInput, Textarea } from "@mantine/core";
import { DateTimePicker, TimeInput } from "@mantine/dates";
import { IconClock } from "@tabler/icons-react";

import { UNITS } from "../lib/time";
import { toLocalIso } from "../lib/time";
import { PhotoPicker } from "./common";
import { eventValue } from "../lib/api";

const unitData = UNITS.map(({ value, label }) => ({ value, label }));
const val = (x, d) => (typeof x === "function" ? x(d) : x);

/** Vẽ các trường cấu hình của khối dựa trên khai báo `fields` trong lib/nodes.jsx */
export function NodeFields({ fields, data, onChange }) {
  const set = (k) => (v) => onChange({ [k]: eventValue(v) });
  return (
    <Stack gap="md">
      {fields.filter((f) => !f.show || f.show(data)).map((f, i) => {
        const label = val(f.label, data);
        const desc = val(f.desc, data);
        const key = f.key || `${f.kind}-${i}`;
        switch (f.kind) {
          case "text":
            return <TextInput key={key} label={label} description={desc} placeholder={val(f.placeholder, data)} value={data[f.key] ?? ""} onChange={set(f.key)} />;
          case "textarea":
            return (
              <Textarea key={key} label={label} description={desc} placeholder={val(f.placeholder, data)} autosize minRows={f.minRows || 3} maxRows={16}
                value={data[f.key] ?? ""} onChange={set(f.key)} inputWrapperOrder={["label", "input", "description"]} />
            );
          case "number":
            return <NumberInput key={key} label={label} description={desc} min={f.min} max={f.max} value={data[f.key]} onChange={(v) => onChange({ [f.key]: Number(v) || 0 })} />;
          case "switch":
            return <Switch key={key} label={label} description={desc} checked={!!data[f.key]} onChange={set(f.key)} />;
          case "select":
            return <Select key={key} label={label} description={desc} data={f.options} value={data[f.key]} onChange={set(f.key)} allowDeselect={false} comboboxProps={{ withinPortal: true }} />;
          case "segmented":
            return (
              <div key={key}>
                {label && <Text size="sm" fw={500} mb={4}>{label}</Text>}
                <SegmentedControl fullWidth data={f.options} value={data[f.key]} onChange={set(f.key)} />
                {desc && <Text size="xs" c="dimmed" mt={4}>{desc}</Text>}
              </div>
            );
          case "chips":
            return (
              <div key={key}>
                {label && <Text size="sm" fw={500} mb={6}>{label}</Text>}
                <Chip.Group multiple={!!f.multiple} value={data[f.key]} onChange={set(f.key)}>
                  <Group gap={6}>{f.options.map((o) => <Chip key={o.value} value={o.value} size="sm">{o.label}</Chip>)}</Group>
                </Chip.Group>
                {desc && <Text size="xs" c="dimmed" mt={4}>{desc}</Text>}
              </div>
            );
          case "datetime":
            return (
              <DateTimePicker key={key} label={label} description={desc} valueFormat="HH:mm, DD/MM/YYYY" minDate={new Date()} leftSection={<IconClock size={16} />}
                value={data[f.key] ? new Date(data[f.key]) : null} onChange={(v) => onChange({ [f.key]: v ? toLocalIso(v) : null })} />
            );
          case "time":
            return <TimeInput key={key} label={label} description={desc} value={data[f.key] ?? ""} onChange={set(f.key)} />;
          case "timerange":
            return (
              <div key={key}>
                <Text size="sm" fw={500} mb={4}>{label}</Text>
                <Group grow gap="xs">
                  <TimeInput aria-label="Từ" leftSection={<Text size="xs" c="dimmed">Từ</Text>} value={data[f.fromKey] ?? ""} onChange={set(f.fromKey)} />
                  <TimeInput aria-label="Đến" leftSection={<Text size="xs" c="dimmed">Đến</Text>} value={data[f.toKey] ?? ""} onChange={set(f.toKey)} />
                </Group>
              </div>
            );
          case "duration":
            return (
              <div key={key}>
                <Text size="sm" fw={500} mb={4}>{label}</Text>
                <Group grow gap="xs">
                  <NumberInput aria-label={label} min={f.min ?? 0} max={999} value={data[f.valueKey]} onChange={(v) => onChange({ [f.valueKey]: Number(v) || 0 })} />
                  <Select aria-label="Đơn vị" data={unitData} value={data[f.unitKey]} onChange={set(f.unitKey)} allowDeselect={false} comboboxProps={{ withinPortal: true }} />
                </Group>
                {desc && <Text size="xs" c="dimmed" mt={4}>{desc}</Text>}
              </div>
            );
          case "range":
            return (
              <div key={key}>
                <Text size="sm" fw={500} mb={4}>{label}</Text>
                <Group grow gap="xs">
                  <NumberInput aria-label="Từ" min={0} max={999} value={data[f.minKey]} onChange={(v) => onChange({ [f.minKey]: Number(v) || 0 })} />
                  <NumberInput aria-label="Đến" min={0} max={999} value={data[f.maxKey]} onChange={(v) => onChange({ [f.maxKey]: Number(v) || 0 })} />
                  <Select aria-label="Đơn vị" data={unitData} value={data[f.unitKey]} onChange={set(f.unitKey)} allowDeselect={false} comboboxProps={{ withinPortal: true }} />
                </Group>
                {desc && <Text size="xs" c="dimmed" mt={4}>{desc}</Text>}
              </div>
            );
          case "photos":
            return (
              <div key={key}>
                <Text size="sm" fw={500} mb={desc ? 2 : 6}>{label}</Text>
                {desc && <Text size="xs" c="dimmed" mb={6}>{desc}</Text>}
                <PhotoPicker compact value={data[f.key] || []} onChange={set(f.key)} />
              </div>
            );
          case "note":
            return <Alert key={key} variant="light" color={f.color || "gray"} py="xs"><Text size="sm">{val(f.text, data)}</Text></Alert>;
          default:
            return null;
        }
      })}
    </Stack>
  );
}
