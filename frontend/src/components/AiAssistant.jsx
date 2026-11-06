import { useState } from "react";
import { Alert, Button, Card, Chip, Group, Loader, Menu, Modal, SegmentedControl, Stack, Text } from "@mantine/core";
import { IconBulb, IconCopy, IconHash, IconPencil, IconSparkles } from "@tabler/icons-react";

import { aiApi } from "../api/endpoints";

const ACTIONS = {
  improve: { label: "Viết lại hay hơn", icon: IconPencil, desc: "3 cách viết lại, giữ nguyên thông tin" },
  variants: { label: "Tạo phiên bản khác", icon: IconCopy, desc: "3 cách diễn đạt khác để đăng luân phiên" },
  hashtags: { label: "Gợi ý hashtag", icon: IconHash, desc: "Hashtag phù hợp với nội dung" },
  idea: { label: "Viết bài từ ý tưởng", icon: IconBulb, desc: "Viết 3 bài hoàn chỉnh từ vài dòng ý tưởng" },
};
const TONES = [{ value: "", label: "Tự nhiên" }, { value: "friendly", label: "Thân thiện" }, { value: "pro", label: "Chuyên nghiệp" },
  { value: "fun", label: "Vui nhộn" }, { value: "short", label: "Ngắn gọn" }];

/** Nút "Trợ lý AI" trong Soạn bài: gợi ý nội dung bằng OpenAI. onApply(newText) thay nội dung bài. */
export function AiAssistant({ text, page, onApply, onOpenSettings }) {
  const [action, setAction] = useState(null);
  const [tone, setTone] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // {suggestions} | {error, needKey}
  const [tags, setTags] = useState([]);

  const run = async (a = action, t = tone) => {
    setBusy(true);
    setResult(null);
    try {
      const r = await aiApi.suggest({ action: a, text, tone: t, page });
      setResult(r);
      setTags(a === "hashtags" ? r.suggestions : []);
    } catch (e) {
      setResult({ error: e.message, needKey: !!e.data?.need_key });
    }
    setBusy(false);
  };
  const open = (a) => { setAction(a); setResult(null); run(a, tone); };
  const close = () => { setAction(null); setResult(null); };
  const apply = (value) => { onApply(value); close(); };

  return (
    <>
      <Menu position="bottom-start" withinPortal width={300}>
        <Menu.Target>
          <Button variant="light" color="violet" size="compact-sm" leftSection={<IconSparkles size={16} />}>Trợ lý AI</Button>
        </Menu.Target>
        <Menu.Dropdown>
          {Object.entries(ACTIONS).map(([k, a]) => (
            <Menu.Item key={k} leftSection={<a.icon size={16} />} onClick={() => open(k)} disabled={!text.trim()}>
              <Text size="sm">{a.label}</Text>
              <Text size="xs" c="dimmed">{a.desc}</Text>
            </Menu.Item>
          ))}
          {!text.trim() && <Menu.Label>Viết vài dòng nội dung hoặc ý tưởng trước</Menu.Label>}
        </Menu.Dropdown>
      </Menu>

      <Modal opened={!!action} onClose={close} size="lg" radius="lg"
        title={<Group gap="xs"><IconSparkles size={18} color="var(--mantine-color-violet-6)" /><Text fw={600}>{action && ACTIONS[action].label}</Text></Group>}>
        <Stack gap="md">
          {action !== "hashtags" && (
            <Group gap="xs">
              <Text size="sm">Giọng văn</Text>
              <SegmentedControl size="xs" value={tone} onChange={(t) => { setTone(t); run(action, t); }} data={TONES} disabled={busy} />
            </Group>
          )}
          {busy && <Group gap="sm" py="lg" justify="center"><Loader size="sm" color="violet" /><Text size="sm" c="dimmed">AI đang viết…</Text></Group>}
          {result?.error && (
            <Alert color={result.needKey ? "violet" : "red"} variant="light">
              <Text size="sm">{result.error}</Text>
              {result.needKey && <Button mt="sm" size="xs" variant="light" color="violet" onClick={() => { close(); onOpenSettings(); }}>Mở Cài đặt</Button>}
            </Alert>
          )}
          {result?.suggestions && action === "hashtags" && (
            <>
              <Chip.Group multiple value={tags} onChange={setTags}>
                <Group gap={6}>{result.suggestions.map((h) => <Chip key={h} value={h} size="sm" color="violet">{h}</Chip>)}</Group>
              </Chip.Group>
              <Group justify="flex-end">
                <Button variant="default" onClick={() => run()}>Gợi ý lại</Button>
                <Button color="violet" disabled={!tags.length} onClick={() => apply(`${text.trimEnd()}\n\n${tags.join(" ")}`)}>Thêm {tags.length} hashtag vào bài</Button>
              </Group>
            </>
          )}
          {result?.suggestions && action !== "hashtags" && (
            <>
              {result.suggestions.map((s, i) => (
                <Card key={i} p="sm" data-testid="ai-suggestion">
                  <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>{s}</Text>
                  <Group justify="flex-end" mt="xs"><Button size="xs" variant="light" color="violet" onClick={() => apply(s)}>Dùng bản này</Button></Group>
                </Card>
              ))}
              {action === "variants" && (
                <Button variant="subtle" color="violet" onClick={() => apply([text.trim(), ...result.suggestions].join("\n---\n"))}>
                  Dùng tất cả làm “nhiều phiên bản” (cho khối Bài viết trong Flow)
                </Button>
              )}
              <Group justify="space-between">
                <Text size="xs" c="dimmed">Kiểm tra lại thông tin trước khi đăng.</Text>
                <Button variant="default" size="xs" onClick={() => run()}>Viết lại lần nữa</Button>
              </Group>
            </>
          )}
        </Stack>
      </Modal>
    </>
  );
}
