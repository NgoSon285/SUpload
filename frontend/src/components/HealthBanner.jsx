import { Alert, Button, Group, Stack, Text } from "@mantine/core";
import { IconPlugConnectedX } from "@tabler/icons-react";

/** Dải cảnh báo khi có Page mất kết nối (token hết hạn, thiếu quyền…). */
export function HealthBanner({ pages, onFix }) {
  const broken = pages.filter((p) => p.health && !p.health.ok);
  if (!broken.length) return null;
  return (
    <Alert color="red" variant="light" radius="md" mb="lg" icon={<IconPlugConnectedX />} data-testid="health-banner"
      title={broken.length === 1 ? `Page “${broken[0].name}” đang mất kết nối` : `${broken.length} Page đang mất kết nối`}>
      <Group justify="space-between" align="flex-end" wrap="wrap" gap="sm">
        <Stack gap={2} style={{ flex: 1, minWidth: 240 }}>
          {broken.map((p) => (
            <Text key={p.id} size="sm">{broken.length > 1 && <b>{p.name}: </b>}{p.health.error}</Text>
          ))}
          <Text size="xs" c="dimmed">Bài lên các Page này sẽ bị lỗi cho tới khi kết nối lại.</Text>
        </Stack>
        <Button size="xs" color="red" variant="light" onClick={onFix}>Mở Cài đặt</Button>
      </Group>
    </Alert>
  );
}
