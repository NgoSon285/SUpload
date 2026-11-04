import { Group, Text, Title } from "@mantine/core";

export function PageHeader({ title, desc, right }) {
  return (
    <Group justify="space-between" align="flex-end" mb="lg" wrap="wrap">
      <div>
        <Title order={2} fz={24} lh={1.25}>{title}</Title>
        {desc && <Text c="dimmed" mt={4}>{desc}</Text>}
      </div>
      {right}
    </Group>
  );
}
