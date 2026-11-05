import { Box, Text, Tooltip } from "@mantine/core";

/**
 * Biểu đồ cột một chuỗi (một màu, không cần chú giải: tiêu đề nói chuỗi là gì).
 * data: [{ key, label, value (null = không có dữ liệu), tip }]
 * Cột mảnh, bo 4px ở đầu, khe 2px, lưới nhạt; chỉ ghi số trên cột cao nhất; rê chuột để xem chi tiết.
 */
export function BarChart({ data, height = 160, labelEvery = 1, format = (v) => v, testId }) {
  const max = Math.max(1, ...data.map((d) => d.value || 0));
  const top = data.reduce((a, b) => ((b.value || 0) > (a?.value || 0) ? b : a), null);
  return (
    <Box data-testid={testId}>
      <div className="bar-plot" style={{ height, gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}>
        <span className="bar-grid" style={{ bottom: "100%" }} />
        <span className="bar-grid" style={{ bottom: "50%" }} />
        {data.map((d) => (
          <Tooltip key={d.key} label={d.tip} withArrow openDelay={0} transitionProps={{ duration: 0 }}>
            <div className="bar-col" aria-label={d.tip}>
              {d.value != null && top && d.key === top.key && d.value > 0 && (
                <Text size="xs" fw={600} className="bar-label" style={{ bottom: `${(d.value / max) * 100}%` }}>{format(d.value)}</Text>
              )}
              {d.value != null
                ? <div className="bar" style={{ height: `${Math.max(2, (d.value / max) * 100)}%` }} />
                : <div className="bar-empty" />}
            </div>
          </Tooltip>
        ))}
      </div>
      <div className="bar-axis" style={{ gridTemplateColumns: `repeat(${data.length}, minmax(0, 1fr))` }}>
        {data.map((d, i) => <Text key={d.key} size="xs" c="dimmed" ta="center">{i % labelEvery === 0 ? d.label : ""}</Text>)}
      </div>
    </Box>
  );
}
