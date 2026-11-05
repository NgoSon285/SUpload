import { useState } from "react";
import { Alert, Anchor, Badge, Button, Group, Modal, ScrollArea, Stack, Table, Text } from "@mantine/core";
import { Dropzone } from "@mantine/dropzone";
import { IconAlertTriangle, IconCheck, IconDownload, IconFileSpreadsheet, IconUpload, IconX } from "@tabler/icons-react";

import { importApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";
import { when } from "../../lib/time";

const ACCEPT = {
  "text/csv": [".csv"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".csv"],
};

/** Nhập bài hàng loạt từ CSV / Excel: chọn file → xem trước từng dòng → nhập. */
export function ImportModal({ opened, onClose, pageName, onDone }) {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const reset = () => { setFile(null); setResult(null); };
  const close = () => { reset(); onClose(); };

  const pick = async ([f]) => {
    if (!f) return;
    setBusy(true);
    try { setResult(await importApi.preview(f)); setFile(f); }
    catch (e) { notifyErr(e.message, "Không đọc được file"); }
    setBusy(false);
  };
  const commit = async (skipErrors) => {
    setBusy(true);
    try {
      const r = await importApi.commit(result.rows, { skipErrors });
      notifyOk(`Đã nhập ${r.count} bài vào Lịch đăng` + (r.failed?.length ? ` (bỏ qua ${r.failed.length} dòng lỗi)` : ""));
      onDone();
      close();
    } catch (e) {
      if (e.data?.failed) {
        const byRow = Object.fromEntries(e.data.failed.map((f) => [f.row, f.errors]));
        setResult((r) => ({ ...r, rows: r.rows.map((row) => ({ ...row, errors: byRow[row.row] || row.errors })),
          bad: e.data.failed.length, ok: r.rows.length - e.data.failed.length }));
      }
      notifyErr(e.message);
    }
    setBusy(false);
  };

  return (
    <Modal opened={opened} onClose={close} size="xl" radius="lg" title={<Text fw={600}>Nhập bài từ Excel / CSV</Text>}>
      {!result ? (
        <Stack gap="md">
          <Text size="sm" c="dimmed">
            Mỗi dòng là một bài. Cột bắt buộc: <b>Nội dung</b>. Cột tuỳ chọn: <b>Link</b>, <b>Ảnh</b> (link ảnh hoặc tên ảnh trong thư viện,
            nhiều ảnh cách nhau bởi dấu phẩy), <b>Thời gian</b> (vd 01/12/2026 20:00, để trống = đăng ngay), <b>Page</b> (tên Page, để trống = mặc định).
          </Text>
          <Group gap="xs">
            <Button component="a" href={importApi.templateUrl("xlsx")} variant="default" size="xs" leftSection={<IconDownload size={14} />}>File mẫu Excel</Button>
            <Button component="a" href={importApi.templateUrl("csv")} variant="default" size="xs" leftSection={<IconDownload size={14} />}>File mẫu CSV</Button>
          </Group>
          <Dropzone onDrop={pick} accept={ACCEPT} multiple={false} loading={busy} radius="md" data-testid="import-drop">
            <Group justify="center" gap="md" mih={120} style={{ pointerEvents: "none" }}>
              <Dropzone.Accept><IconUpload size={36} /></Dropzone.Accept>
              <Dropzone.Reject><IconX size={36} /></Dropzone.Reject>
              <Dropzone.Idle><IconFileSpreadsheet size={36} stroke={1.5} color="var(--mantine-color-dimmed)" /></Dropzone.Idle>
              <div>
                <Text fw={500}>Kéo thả file .xlsx hoặc .csv vào đây</Text>
                <Text size="sm" c="dimmed">hoặc bấm để chọn file (tối đa 500 bài)</Text>
              </div>
            </Group>
          </Dropzone>
        </Stack>
      ) : (
        <Stack gap="md">
          <Group justify="space-between">
            <Group gap="xs">
              <Text size="sm" fw={500}>{file?.name}</Text>
              <Badge color="teal" variant="light" leftSection={<IconCheck size={12} />}>{result.ok} dòng hợp lệ</Badge>
              {result.bad > 0 && <Badge color="red" variant="light" leftSection={<IconAlertTriangle size={12} />}>{result.bad} dòng lỗi</Badge>}
            </Group>
            <Anchor size="sm" onClick={reset}>Chọn file khác</Anchor>
          </Group>
          <ScrollArea.Autosize mah={420}>
            <Table striped highlightOnHover verticalSpacing={6} fz="sm" data-testid="import-table">
              <Table.Thead>
                <Table.Tr><Table.Th w={50}>Dòng</Table.Th><Table.Th>Nội dung</Table.Th><Table.Th w={150}>Thời gian</Table.Th><Table.Th w={60}>Ảnh</Table.Th><Table.Th w={130}>Page</Table.Th></Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {result.rows.map((r) => (
                  <Table.Tr key={r.row} style={r.errors.length ? { background: "var(--mantine-color-red-light)" } : undefined}>
                    <Table.Td>{r.row}</Table.Td>
                    <Table.Td>
                      <Text size="sm" lineClamp={2}>{r.message || r.link || <i>(chỉ có ảnh)</i>}</Text>
                      {r.errors.map((e) => <Text key={e} size="xs" c="red">✕ {e}</Text>)}
                      {r.warnings.map((w) => <Text key={w} size="xs" c="orange">! {w}</Text>)}
                    </Table.Td>
                    <Table.Td>{r.scheduled_at ? when(r.scheduled_at) : "Đăng ngay"}</Table.Td>
                    <Table.Td>{r.photos.length || ""}</Table.Td>
                    <Table.Td>{pageName(r.page)}</Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea.Autosize>
          <Alert variant="light" color="gray" py="xs"><Text size="xs">Bài nhập vào vẫn tuân theo giới hạn an toàn (số bài/ngày, giãn cách) của từng Page.</Text></Alert>
          <Group justify="flex-end">
            <Button variant="default" onClick={close}>Huỷ</Button>
            {result.bad > 0 && result.ok > 0 && (
              <Button color="orange" variant="light" loading={busy} onClick={() => commit(true)}>Nhập {result.ok} bài hợp lệ, bỏ qua {result.bad} dòng lỗi</Button>
            )}
            <Button loading={busy} disabled={result.bad > 0 || !result.ok} onClick={() => commit(false)}>Nhập {result.ok} bài</Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
