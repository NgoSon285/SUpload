import { useCallback, useEffect, useState } from "react";
import {
  AppShell, Avatar, Badge, Burger, Group, NavLink, Paper, SegmentedControl, Stack, Text, Tooltip,
  UnstyledButton, useMantineColorScheme, Indicator,
} from "@mantine/core";
import { useDisclosure, useInterval } from "@mantine/hooks";
import {
  IconPencil, IconCalendarEvent, IconSitemap, IconListDetails, IconAdjustments, IconSun, IconMoon,
  IconDeviceDesktop, IconSend,
} from "@tabler/icons-react";

import { stateApi } from "../api/endpoints";
import ComposePage from "../features/compose/ComposePage";
import FlowPage from "../features/flow/FlowPage";
import LogPage from "../features/log/LogPage";
import QueuePage from "../features/queue/QueuePage";
import SettingsPage from "../features/settings/SettingsPage";
import { HealthBanner } from "../components";
import { configured, defaultPage, KIND_LABEL, pageInitial, pagesOf } from "../lib/page";
import { storage } from "../lib/storage";
import { AppContext } from "./context";

const VIEWS = [
  { id: "compose", label: "Soạn bài", icon: IconPencil },
  { id: "queue", label: "Lịch đăng", icon: IconCalendarEvent },
  { id: "flow", label: "Flow chiến dịch", icon: IconSitemap },
  { id: "log", label: "Nhật ký", icon: IconListDetails },
  { id: "settings", label: "Cài đặt", icon: IconAdjustments },
];

function ThemeSwitch() {
  const { colorScheme, setColorScheme } = useMantineColorScheme();
  const item = (value, Icon, label) => ({
    value,
    label: (
      <Tooltip label={label} withArrow>
        <span style={{ display: "grid", placeItems: "center" }}><Icon size={16} /></span>
      </Tooltip>
    ),
  });
  return (
    <SegmentedControl
      fullWidth size="xs" value={colorScheme} onChange={setColorScheme}
      data={[item("light", IconSun, "Sáng"), item("auto", IconDeviceDesktop, "Theo hệ thống"), item("dark", IconMoon, "Tối")]}
    />
  );
}

function ConnectionCard({ state, onClick }) {
  const ok = configured(state);
  const page = defaultPage(state);
  const n = pagesOf(state).length;
  const name = page?.name || "Chưa kết nối";
  return (
    <Paper withBorder p="sm" component={UnstyledButton} onClick={onClick} style={{ width: "100%" }}>
      <Group gap="sm" wrap="nowrap">
        <Indicator color={!ok ? "gray" : pagesOf(state).some((p) => p.health && !p.health.ok) ? "red" : "teal"} size={10} offset={4} position="bottom-end" withBorder>
          <Avatar color="indigo" radius="xl">{pageInitial(page)}</Avatar>
        </Indicator>
        <div style={{ minWidth: 0 }}>
          <Text size="sm" fw={600} truncate>{name}</Text>
          <Text size="xs" c="dimmed">{ok ? (n > 1 ? `Mặc định · ${n} Page` : KIND_LABEL[page.kind]) : "Bấm để thiết lập"}</Text>
        </div>
      </Group>
    </Paper>
  );
}

export default function App() {
  const [state, setState] = useState(null);
  const [offline, setOffline] = useState(false);
  const [view, setViewRaw] = useState(() => storage.get("view", "compose"));
  const [draftPost, setDraftPost] = useState(null); // {post, mode: 'edit'|'dup'} chuyển sang trang Soạn bài
  const [opened, { toggle, close }] = useDisclosure(false);

  const refresh = useCallback(async () => {
    try {
      setState(await stateApi.get());
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  const setView = useCallback((v) => {
    setViewRaw(v);
    storage.set("view", v);
    close();
    window.scrollTo(0, 0);
  }, [close]);

  useEffect(() => { refresh(); }, [refresh]);
  const interval = useInterval(refresh, 3000);
  useEffect(() => { interval.start(); return interval.stop; }, []); // eslint-disable-line

  // Lần đầu chưa kết nối Page -> mở Cài đặt
  useEffect(() => {
    if (state && !configured(state) && storage.get("view") === null) setView("settings");
  }, [state, setView]);

  const posts = state?.posts || [];
  const nPending = posts.filter((p) => p.status === "pending" || p.status === "running").length;
  const nErr = posts.filter((p) => p.status === "error").length;
  const ok = configured(state);
  const isFlow = view === "flow";

  const ctx = { state, refresh, setView, draftPost, setDraftPost, offline };

  return (
    <AppContext.Provider value={ctx}>
      <AppShell
        header={{ height: 56, collapsed: false }}
        navbar={{ width: 250, breakpoint: "sm", collapsed: { mobile: !opened } }}
        padding={isFlow ? 0 : "lg"}
      >
        <AppShell.Header px="md">
          <Group h="100%" justify="space-between" wrap="nowrap">
            <Group gap="sm" wrap="nowrap">
              <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" aria-label="Mở menu" />
              <div className="brand-mark"><IconSend size={17} /></div>
              <Text fw={700} size="lg">SUpload</Text>
            </Group>
            <Group gap="xs" wrap="nowrap">
              {offline ? (
                <Badge color="red" variant="light">Mất kết nối tới ứng dụng</Badge>
              ) : state && state.worker !== "Đang rảnh" ? (
                <Badge color="orange" variant="light" leftSection="●" maw={320} style={{ textTransform: "none" }}>{state.worker}</Badge>
              ) : (
                <Badge color="teal" variant="light" leftSection="●" style={{ textTransform: "none" }}>Sẵn sàng</Badge>
              )}
            </Group>
          </Group>
        </AppShell.Header>

        <AppShell.Navbar p="sm">
          <AppShell.Section grow>
            <Stack gap={4}>
              {VIEWS.map(({ id, label, icon: Icon }) => {
                let right = null;
                if (id === "queue" && nPending + nErr > 0) right = <Badge size="sm" circle={nPending + nErr < 10} color={nErr ? "red" : "indigo"}>{nPending + nErr}</Badge>;
                if (id === "settings" && state && !ok) right = <Badge size="sm" color="red" circle>!</Badge>;
                return (
                  <NavLink
                    key={id} label={label} active={view === id} onClick={() => setView(id)}
                    leftSection={<Icon size={19} stroke={1.8} />} rightSection={right}
                    style={{ borderRadius: "var(--mantine-radius-md)" }} fw={500}
                  />
                );
              })}
            </Stack>
          </AppShell.Section>
          <AppShell.Section>
            <Stack gap="sm">
              <ConnectionCard state={state} onClick={() => setView("settings")} />
              <ThemeSwitch />
            </Stack>
          </AppShell.Section>
        </AppShell.Navbar>

        <AppShell.Main>
          {state && view !== "settings" && (
            <div style={view === "flow" ? { padding: "var(--mantine-spacing-md) var(--mantine-spacing-md) 0" } : undefined}>
              <HealthBanner pages={pagesOf(state)} onFix={() => setView("settings")} />
            </div>
          )}
          {!state ? null : view === "compose" ? <ComposePage /> : view === "queue" ? <QueuePage /> : view === "flow" ? <FlowPage /> : view === "log" ? <LogPage /> : <SettingsPage />}
        </AppShell.Main>
      </AppShell>
    </AppContext.Provider>
  );
}
