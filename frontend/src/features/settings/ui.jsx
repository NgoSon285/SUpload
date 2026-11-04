import { Card, Group, Stack, Text, ThemeIcon } from "@mantine/core";

/** Một thẻ cài đặt có số thứ tự. */
export function Step({ n, title, right, children }) {
  return (
    <Card p={0}>
      <Group gap="sm" px="lg" py="md" justify="space-between" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        <Group gap="sm">
          <ThemeIcon radius="xl" size={26} variant="light"><Text fw={700} size="sm">{n}</Text></ThemeIcon>
          <Text fw={600}>{title}</Text>
        </Group>
        {right}
      </Group>
      <Stack p="lg" gap="md">{children}</Stack>
    </Card>
  );
}

export const GAPS = [
  { value: "0", label: "Không" },
  { value: "120", label: "2 phút" },
  { value: "300", label: "5 phút" },
  { value: "600", label: "10 phút" },
  { value: "1800", label: "30 phút" },
];
