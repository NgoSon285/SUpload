import { useState } from "react";
import {
  Accordion, Alert, Anchor, Avatar, Button, Code, Group, List, Paper, PasswordInput, SimpleGrid, Stack, Tabs, Text, TextInput,
} from "@mantine/core";
import { IconAlertTriangle, IconBolt, IconCheck, IconClock, IconListDetails, IconPlus, IconWorld } from "@tabler/icons-react";

import { pagesApi, settingsApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";

const LOGIN = {
  waiting: ["orange", "Đang chờ bạn đăng nhập trong cửa sổ trình duyệt…", IconClock],
  checking: ["orange", "Đang kiểm tra phiên đăng nhập…", IconClock],
  yes: ["teal", "Đã đăng nhập Facebook", IconCheck],
  no: ["red", "Chưa đăng nhập: bấm “Mở trình duyệt để đăng nhập”", IconAlertTriangle],
  busy: ["orange", "Trình duyệt đang bận đăng bài, thử lại sau ít phút", IconClock],
};

function ApiTab({ settings, existing, onAdded }) {
  const [appId, setAppId] = useState(settings.app_id || "");
  const [secret, setSecret] = useState("");
  const [userToken, setUserToken] = useState("");
  const [found, setFound] = useState(null);
  const [busy, setBusy] = useState(false);
  const [manual, setManual] = useState({ fb_page_id: "", token: "", name: "" });

  const fetchPages = async () => {
    setBusy(true);
    try { setFound((await settingsApi.fetchPages({ app_id: appId.trim(), app_secret: secret.trim(), user_token: userToken.trim() })).pages); }
    catch (e) { notifyErr(e.message); }
    setBusy(false);
  };
  const choose = async (p) => {
    try { await settingsApi.selectPage(p.id); notifyOk(`Đã kết nối Page “${p.name}”`); onAdded(); }
    catch (e) { notifyErr(e.message); }
  };
  const addManual = async () => {
    try {
      await pagesApi.add({ kind: "api", ...manual });
      setManual({ fb_page_id: "", token: "", name: "" });
      notifyOk("Đã thêm Page");
      onAdded();
    } catch (e) { notifyErr(e.message); }
  };
  const have = new Set(existing.filter((p) => p.kind === "api").map((p) => p.fb_page_id));

  return (
    <Stack gap="md">
      <List type="ordered" size="sm" spacing={4} c="dimmed">
        <List.Item>Tạo App loại <b>Business</b> tại <Anchor href="https://developers.facebook.com/apps" target="_blank">developers.facebook.com/apps</Anchor>, chép <b>App ID</b> và <b>App Secret</b> (Settings → Basic).</List.Item>
        <List.Item>Mở <Anchor href="https://developers.facebook.com/tools/explorer" target="_blank">Graph API Explorer</Anchor>, chọn App, cấp quyền <Code>pages_show_list</Code> <Code>pages_read_engagement</Code> <Code>pages_manage_posts</Code>, bấm <b>Generate Access Token</b> và chọn <b>mọi Page</b> muốn quản lý.</List.Item>
        <List.Item>Dán token vào dưới đây, bấm <b>Lấy danh sách Page</b> rồi thêm từng Page.</List.Item>
      </List>
      <SimpleGrid cols={{ base: 1, sm: 2 }}>
        <TextInput label="App ID" value={appId} onChange={(e) => setAppId(e.currentTarget.value)} autoComplete="off" />
        <PasswordInput label="App Secret" description={settings.app_secret_set ? "Đã lưu, để trống nếu không đổi" : undefined} value={secret} onChange={(e) => setSecret(e.currentTarget.value)} autoComplete="new-password" />
      </SimpleGrid>
      <PasswordInput label="User Access Token" placeholder="Dán token từ Graph API Explorer" value={userToken} onChange={(e) => setUserToken(e.currentTarget.value)} />
      <Group><Button variant="default" loading={busy} leftSection={<IconListDetails size={16} />} onClick={fetchPages} disabled={!userToken.trim()}>Lấy danh sách Page</Button></Group>

      {found && (found.length ? (
        <Stack gap={6}>
          {found.map((p) => (
            <Paper key={p.id} withBorder p="sm" radius="md">
              <Group justify="space-between">
                <Group gap="sm"><Avatar radius="xl" color="indigo">{(p.name || "P")[0].toUpperCase()}</Avatar><div><Text fw={600} size="sm">{p.name}</Text><Text size="xs" c="dimmed">ID {p.id}</Text></div></Group>
                {have.has(p.id)
                  ? <Button size="xs" variant="subtle" color="gray" onClick={() => choose(p)}>Đã thêm · cập nhật token</Button>
                  : <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => choose(p)}>Thêm</Button>}
              </Group>
            </Paper>
          ))}
        </Stack>
      ) : <Alert color="red" variant="light">Tài khoản này không quản lý Page nào, hoặc token thiếu quyền pages_show_list.</Alert>)}

      <Accordion variant="separated" radius="md">
        <Accordion.Item value="manual">
          <Accordion.Control><Text size="sm">Nhập Page ID / Page Token thủ công</Text></Accordion.Control>
          <Accordion.Panel>
            <Stack gap="sm">
              <TextInput label="Page ID" value={manual.fb_page_id} onChange={(e) => setManual({ ...manual, fb_page_id: e.currentTarget.value })} autoComplete="off" />
              <PasswordInput label="Page Access Token" value={manual.token} onChange={(e) => setManual({ ...manual, token: e.currentTarget.value })} autoComplete="new-password" />
              <TextInput label="Tên hiển thị" placeholder="Không bắt buộc" value={manual.name} onChange={(e) => setManual({ ...manual, name: e.currentTarget.value })} />
              <Group><Button onClick={addManual} disabled={!manual.fb_page_id.trim() || !manual.token.trim()} leftSection={<IconPlus size={16} />}>Thêm Page</Button></Group>
            </Stack>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    </Stack>
  );
}

function BrowserTab({ login, onAdded }) {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const status = LOGIN[login] || (login?.startsWith("error") ? ["red", login.replace(/^error: /, "Lỗi: "), IconAlertTriangle] : null);
  const add = async () => {
    try { await pagesApi.add({ kind: "browser", url: url.trim(), name: name.trim() }); setUrl(""); setName(""); notifyOk("Đã thêm Page"); onAdded(); }
    catch (e) { notifyErr(e.message); }
  };
  const browser = async (a) => { await settingsApi.browser(a); setTimeout(onAdded, 600); };
  return (
    <Stack gap="md">
      <Text size="sm" c="dimmed">Ứng dụng tự thao tác trên facebook.com như người dùng. Chậm hơn API và có thể hỏng khi Facebook đổi giao diện. Mọi Page cách này dùng chung một lần đăng nhập.</Text>
      <div>
        <Text size="sm" fw={500} mb={6}>1. Đăng nhập Facebook (một lần)</Text>
        <Group gap="xs">
          <Button variant="default" leftSection={<IconWorld size={16} />} onClick={() => browser("login")}>Mở trình duyệt để đăng nhập</Button>
          <Button variant="subtle" onClick={() => browser("check")}>Kiểm tra lại</Button>
        </Group>
        {status && <Alert mt="sm" py="xs" variant="light" color={status[0]} icon={(() => { const I = status[2]; return <I size={16} />; })()}>{status[1]}</Alert>}
        <Text size="xs" c="dimmed" mt="xs">Bạn tự đăng nhập trong cửa sổ hiện ra (kể cả mã 2FA). Ứng dụng không lưu mật khẩu, chỉ giữ phiên trong <Code>fb_profile/</Code>.</Text>
      </div>
      <div>
        <Text size="sm" fw={500} mb={6}>2. Thêm Page</Text>
        <SimpleGrid cols={{ base: 1, sm: 2 }}>
          <TextInput label="Địa chỉ Page" placeholder="https://www.facebook.com/TenPage" leftSection={<IconWorld size={16} />} value={url} onChange={(e) => setUrl(e.currentTarget.value)} />
          <TextInput label="Tên hiển thị" placeholder="Không bắt buộc" value={name} onChange={(e) => setName(e.currentTarget.value)} />
        </SimpleGrid>
        <Group mt="sm"><Button onClick={add} disabled={!url.trim()} leftSection={<IconPlus size={16} />}>Thêm Page</Button></Group>
      </div>
    </Stack>
  );
}

/** Thêm Page: qua Graph API (khuyên dùng) hoặc qua trình duyệt. */
export function AddPage({ settings, pages, login, onAdded }) {
  return (
    <Tabs defaultValue="api" variant="outline" radius="md">
      <Tabs.List>
        <Tabs.Tab value="api" leftSection={<IconBolt size={16} />}>Qua Graph API (khuyên dùng)</Tabs.Tab>
        <Tabs.Tab value="browser" leftSection={<IconWorld size={16} />}>Qua trình duyệt</Tabs.Tab>
      </Tabs.List>
      <Tabs.Panel value="api" pt="md"><ApiTab settings={settings} existing={pages} onAdded={onAdded} /></Tabs.Panel>
      <Tabs.Panel value="browser" pt="md"><BrowserTab login={login} onAdded={onAdded} /></Tabs.Panel>
    </Tabs>
  );
}

