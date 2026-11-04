import { Box, Stack, Text } from "@mantine/core";
import { IconPhoto } from "@tabler/icons-react";

export function EmptyState({ icon: Icon = IconPhoto, title, desc, action }) {
  return (
    <Stack align="center" gap={6} py={48} px="md" ta="center">
      <Box p="md" style={{ borderRadius: 16, background: "var(--mantine-color-default-hover)" }}><Icon size={26} stroke={1.6} color="var(--mantine-color-dimmed)" /></Box>
      <Text fw={600} mt="xs">{title}</Text>
      {desc && <Text c="dimmed" size="sm" maw={360}>{desc}</Text>}
      {action && <Box mt="sm">{action}</Box>}
    </Stack>
  );
}
