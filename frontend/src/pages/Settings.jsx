import { useEffect, useState } from "react";
import {
  Accordion, Alert, Anchor, Avatar, Badge, Button, Card, Code, Group, List, PasswordInput, SegmentedControl, SimpleGrid,
  Stack, Switch, Text, TextInput, ThemeIcon, UnstyledButton, Affix, Transition, Paper,
} from "@mantine/core";
import {
  IconAlertTriangle, IconBolt, IconCheck, IconClock, IconListDetails, IconPlugConnected, IconWorld,
} from "@tabler/icons-react";

import { useApp } from "../App";
import { api } from "../lib/api";
import { PageHeader, notifyErr, notifyOk } from "../components/common";

const GAPS = [
  { value: "0", label: "Không" },
  { value: "120", label: "2 phút" },
  { value: "300", label: "5 phút" },
  { value: "600", label: "10 phút" },
  { value: "1800", label: "30 phút" },
];

function Step({ n, title, children }) {
  return (
    <Card p={0}>
      <Group gap="sm" px="lg" py="md" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        <ThemeIcon radius="xl" size={26} variant="light"><Text fw={700} size="sm">{n}</Text></ThemeIcon>
        <Text fw={600}>{title}</Text>
      </Group>
      <Stack p="lg" gap="md">{children}</Stack>
    </Card>
  );
}

function MethodCard({ value, current, onChange, icon: Icon, title, desc, tag }) {
  return (
    <UnstyledButton onClick={() => onChange(value)} style={{ height: "100%" }}>
      <Paper withBorder p="md" radius="md" className="method-card" data-checked={current === value || undefined} h="100%" pos="relative">
        {tag && <Badge color="teal" size="xs" pos="absolute" top={-9} right={12}>{tag}</Badge>}
        <Group align="flex-start" wrap="nowrap">
          <ThemeIcon size={38} radius="md" variant={current === value ? "filled" : "light"} color={current === value ? undefined : "gray"}><Icon size={20} /></ThemeIcon>
          <div>
            <Text fw={600}>{title}</Text>
            <Text size="sm" c="dimmed" lh={1.45}>{desc}</Text>
          </div>
        </Group>
      </Paper>
    </UnstyledButton>
  );
}

const LOGIN = {
  waiting: ["orange", "Đang chờ bạn đăng nhập trong cửa sổ trình duyệt…", IconClock],
  checking: ["orange", "Đang kiểm tra phiên đăng nhập…", IconClock],
  yes: ["teal", "Đã đăng nhập Facebook", IconCheck],
  no: ["red", "Chưa đăng nhập: bấm “Mở trình duyệt để đăng nhập”", IconAlertTriangle],
  busy: ["orange", "Trình duyệt đang bận đăng bài, thử lại sau ít phút", IconClock],
};

export default function Settings() {
  const { state, refresh } = useApp();
  const s = state.settings;
  const initial = () => ({
    method: s.method, app_id: s.app_id || "", app_secret: "", page_id: s.page_id || "", page_token: "",
    page_url: s.page_url || "", min_gap: String(s.min_gap ?? 300), headless: !!s.headless,
  });
  const [f, setF] = useState(initial);
  const [dirty, setDirty] = useState(false);
  const [userToken, setUserToken] = useState("");
  const [pages, setPages] = useState(null);
  const [busy, setBusy] = useState("");
  const [test, setTest] = useState(null);

  useEffect(() => { if (!dirty) setF(initial()); }, [state]); // eslint-disable-line

  const set = (k) => (v) => { setF((x) => ({ ...x, [k]: v?.currentTarget ? (v.currentTarget.type === "checkbox" ? v.currentTarget.checked : v.currentTarget.value) : v })); setDirty(true); };
  const gaps = GAPS.some((g) => g.value === f.min_gap) ? GAPS : [...GAPS, { value: f.min_gap, label: `${Math.round(f.min_gap / 60)} phút` }];

  const save = async (silent) => {
    if (f.method === "browser" && f.page_url && !/facebook\.com\//.test(f.page_url)) { notifyErr("Địa chỉ Page phải là link facebook.com/…"); return false; }
    try {
      await api("/api/settings", { method: "POST", body: { ...f, min_gap: Number(f.min_gap) } });
      setDirty(false);
      await refresh();
      if (!silent) notifyOk("Đã lưu cài đặt");
      return true;
    } catch (e) { notifyErr(e.message); return false; }
  };

  const fetchPages = async () => {
    setBusy("pages");
    try {
      const j = await api("/api/fb/pages", { method: "POST", body: { app_id: f.app_id.trim(), app_secret: f.app_secret.trim(), user_token: userToken.trim() } });
      setPages(j.pages);
    } catch (e) { notifyErr(e.message); }
    setBusy("");
  };
  const choosePage = async (id) => {
    try {
      await api("/api/fb/select-page", { method: "POST", body: { id } });
      if (f.method !== "api" || dirty) await api("/api/settings", { method: "POST", body: { method: "api" } });
      setPages(null); setUserToken(""); setDirty(false);
      await refresh();
      notifyOk("Đã kết nối Page");
    } catch (e) { notifyErr(e.message); }
  };
  const testApi = async () => {
    setTest({ color: "orange", text: "Đang kiểm tra…" });
    try { const j = await api("/api/test-connection", { method: "POST" }); setTest({ color: "teal", text: j.text }); refresh(); }
    catch (e) { setTest({ color: "red", text: e.message }); }
  };
  const browserAction = async (a) => {
    if (dirty && !(await save(true))) return;
    await api(`/api/browser/${a}`, { method: "POST" });
    setTimeout(refresh, 600);
  };

  const hasApi = s.page_id && s.page_token_set;
  const login = LOGIN[state.login] || (state.login?.startsWith("error") ? ["red", state.login.replace(/^error: /, "Lỗi: "), IconAlertTriangle] : null);

  return (
    <>
      <PageHeader title="Cài đặt" desc="Kết nối Page và tuỳ chỉnh cách đăng bài." />
      <Stack maw={800} gap="lg" pb={80}>
        <Step n={1} title="Chọn cách đăng">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <MethodCard value="api" current={f.method} onChange={set("method")} icon={IconBolt} tag="Khuyên dùng" title="Graph API"
              desc="Kênh chính thức Facebook cấp cho chủ Page. Nhanh, ổn định, không cần mở trình duyệt." />
            <MethodCard value="browser" current={f.method} onChange={set("method")} icon={IconWorld} title="Trình duyệt"
              desc="Tự thao tác trên facebook.com như người dùng. Chậm hơn và có thể hỏng khi Facebook đổi giao diện." />
          </SimpleGrid>
        </Step>

        {f.method === "api" ? (
          <Step n={2} title="Kết nối Page qua API">
            {hasApi && (
              <Paper withBorder p="sm" radius="md" bg="var(--mantine-color-default-hover)">
                <Group justify="space-between">
                  <Group gap="sm">
                    <Avatar radius="xl" variant="gradient" gradient={{ from: "indigo", to: "violet" }}>{(s.page_name || "P")[0].toUpperCase()}</Avatar>
                    <div><Text fw={600} size="sm">{s.page_name || "Page đã kết nối"}</Text><Text size="xs" c="dimmed">ID {s.page_id}</Text></div>
                  </Group>
                  <Button variant="default" leftSection={<IconPlugConnected size={16} />} onClick={testApi}>Kiểm tra kết nối</Button>
                </Group>
              </Paper>
            )}
            {test && <Alert color={test.color} variant="light" py="xs">{test.text}</Alert>}

            <List type="ordered" size="sm" spacing={4} c="dimmed">
              <List.Item>Tạo App loại <b>Business</b> tại <Anchor href="https://developers.facebook.com/apps" target="_blank">developers.facebook.com/apps</Anchor>, chép <b>App ID</b> và <b>App Secret</b> (Settings → Basic).</List.Item>
              <List.Item>Mở <Anchor href="https://developers.facebook.com/tools/explorer" target="_blank">Graph API Explorer</Anchor>, chọn App, cấp quyền <Code>pages_show_list</Code> <Code>pages_read_engagement</Code> <Code>pages_manage_posts</Code> rồi bấm <b>Generate Access Token</b>.</List.Item>
              <List.Item>Dán token vào dưới đây và bấm <b>Lấy danh sách Page</b>.</List.Item>
            </List>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <TextInput label="App ID" value={f.app_id} onChange={set("app_id")} autoComplete="off" />
              <PasswordInput label="App Secret" description={s.app_secret_set ? "Đã lưu, để trống nếu không đổi" : undefined} value={f.app_secret} onChange={set("app_secret")} autoComplete="new-password" />
            </SimpleGrid>
            <PasswordInput label="User Access Token" placeholder="Dán token từ Graph API Explorer" value={userToken} onChange={(e) => setUserToken(e.currentTarget.value)} />
            <Group><Button variant="default" loading={busy === "pages"} leftSection={<IconListDetails size={16} />} onClick={fetchPages} disabled={!userToken.trim()}>Lấy danh sách Page</Button></Group>

            {pages && (pages.length ? (
              <Stack gap={6}>
                <Text size="sm" c="dimmed">Chọn Page muốn đăng bài:</Text>
                {pages.map((p) => (
                  <UnstyledButton key={p.id} onClick={() => choosePage(p.id)}>
                    <Paper withBorder p="sm" radius="md" className="method-card">
                      <Group justify="space-between">
                        <Group gap="sm"><Avatar radius="xl" color="indigo">{(p.name || "P")[0].toUpperCase()}</Avatar><div><Text fw={600} size="sm">{p.name}</Text><Text size="xs" c="dimmed">ID {p.id}</Text></div></Group>
                        <Text size="sm" c="indigo" fw={500}>Chọn</Text>
                      </Group>
                    </Paper>
                  </UnstyledButton>
                ))}
              </Stack>
            ) : (
              <Alert color="red" variant="light">Tài khoản này không quản lý Page nào, hoặc token thiếu quyền pages_show_list.</Alert>
            ))}

            <Accordion variant="separated" radius="md">
              <Accordion.Item value="manual">
                <Accordion.Control><Text size="sm">Nhập Page ID / Page Token thủ công</Text></Accordion.Control>
                <Accordion.Panel>
                  <Stack gap="sm">
                    <TextInput label="Page ID" value={f.page_id} onChange={set("page_id")} autoComplete="off" />
                    <PasswordInput label="Page Access Token" description={s.page_token_set ? "Đã lưu, để trống nếu không đổi" : undefined} value={f.page_token} onChange={set("page_token")} autoComplete="new-password" />
                  </Stack>
                </Accordion.Panel>
              </Accordion.Item>
            </Accordion>
          </Step>
        ) : (
          <Step n={2} title="Đăng qua trình duyệt">
            <TextInput label="Địa chỉ Page" placeholder="https://www.facebook.com/TenPage" leftSection={<IconWorld size={16} />} value={f.page_url} onChange={set("page_url")} />
            <div>
              <Text size="sm" fw={500} mb={6}>Đăng nhập Facebook</Text>
              <Group gap="xs">
                <Button variant="default" leftSection={<IconWorld size={16} />} onClick={() => browserAction("login")}>Mở trình duyệt để đăng nhập</Button>
                <Button variant="subtle" onClick={() => browserAction("check")}>Kiểm tra lại</Button>
              </Group>
              {login && <Alert mt="sm" py="xs" variant="light" color={login[0]} icon={(() => { const I = login[2]; return <I size={16} />; })()}>{login[1]}</Alert>}
              <Text size="xs" c="dimmed" mt="xs">Một cửa sổ trình duyệt sẽ mở ra để bạn tự đăng nhập (kể cả mã 2FA). Ứng dụng không lưu mật khẩu, chỉ giữ phiên trong thư mục <Code>fb_profile/</Code>.</Text>
            </div>
            <div>
              <Text size="sm" fw={500} mb={6}>Giãn cách tối thiểu giữa 2 bài</Text>
              <SegmentedControl data={gaps} value={f.min_gap} onChange={set("min_gap")} />
            </div>
            <Switch checked={f.headless} onChange={set("headless")} label="Chạy ẩn trình duyệt" description="Không hiện cửa sổ khi đăng. Nên tắt trong vài lần đầu để theo dõi." />
          </Step>
        )}
      </Stack>

      <Affix position={{ bottom: 20, left: "50%" }} style={{ transform: "translateX(-50%)" }}>
        <Transition transition="slide-up" mounted={dirty}>
          {(styles) => (
            <Paper style={styles} shadow="xl" p="sm" pl="lg" radius="lg" withBorder>
              <Group gap="md" wrap="nowrap">
                <Text size="sm" fw={500}>Bạn có thay đổi chưa lưu</Text>
                <Button variant="default" onClick={() => { setF(initial()); setDirty(false); }}>Huỷ</Button>
                <Button onClick={() => save()}>Lưu cài đặt</Button>
              </Group>
            </Paper>
          )}
        </Transition>
      </Affix>
    </>
  );
}
