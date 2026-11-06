import { useEffect, useState } from "react";
import { Affix, Anchor, Autocomplete, Button, Code, Group, NumberInput, Paper, PasswordInput, SegmentedControl, Stack, Switch, Text, TextInput, Transition } from "@mantine/core";
import { IconDatabase } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { settingsApi, stateApi } from "../../api/endpoints";
import { PageHeader, notifyErr, notifyOk } from "../../components";
import { eventValue } from "../../lib/forms";
import { pagesOf } from "../../lib/page";
import { when } from "../../lib/time";
import { AddPage } from "./AddPageCard";
import { AppCard } from "./AppCard";
import { PagesCard } from "./PagesCard";
import { GAPS, Step } from "./ui";

/** Cài đặt: Page đã kết nối, thêm Page, cách đăng, giới hạn an toàn, dữ liệu & sao lưu. */
export default function SettingsPage() {
  const { state, refresh } = useApp();
  const s = state.settings;
  const pages = pagesOf(state);
  const hasApi = pages.some((p) => p.kind === "api");
  const hasBrowser = pages.some((p) => p.kind === "browser");
  const initial = () => ({
    fb_schedule: s.fb_schedule ?? true, headless: !!s.headless, min_gap: String(s.min_gap ?? 300),
    daily_max: s.daily_max ?? 20, keep_done_days: String(s.keep_done_days ?? 90),
    openai_api_key: "", ai_model: s.ai_model || "gpt-5.4-mini", ai_base_url: s.ai_base_url || "",
  });
  const [f, setF] = useState(initial);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!dirty) setF(initial()); }, [state]); // eslint-disable-line

  const set = (k) => (v) => { const val = eventValue(v); setF((x) => ({ ...x, [k]: val })); setDirty(true); };
  const gaps = GAPS.some((g) => g.value === f.min_gap) ? GAPS : [...GAPS, { value: f.min_gap, label: `${Math.round(f.min_gap / 60)} phút` }];

  const save = async () => {
    try {
      await settingsApi.save({ ...f, min_gap: Number(f.min_gap), daily_max: Number(f.daily_max) || 0, keep_done_days: Number(f.keep_done_days) });
      setDirty(false);
      setF((x) => ({ ...x, openai_api_key: "" }));
      await refresh();
      notifyOk("Đã lưu cài đặt");
    } catch (e) { notifyErr(e.message); }
  };
  const runMaintenance = async () => {
    setBusy(true);
    try {
      const r = await stateApi.runMaintenance();
      notifyOk(`Đã sao lưu (${r.last_backup}). Dọn ${r.removed_posts} bài cũ, ${r.removed_files} ảnh không dùng.`);
      refresh();
    } catch (e) { notifyErr(e.message); }
    setBusy(false);
  };

  return (
    <>
      <PageHeader title="Cài đặt" desc="Kết nối các Page và tuỳ chỉnh cách đăng bài." />
      <Stack maw={820} gap="lg" pb={90}>
        <Step n={1} title={`Page đã kết nối (${pages.length})`}>
          <PagesCard pages={pages} perPageToday={state.limits?.per_page} dailyMax={s.daily_max} onChanged={refresh} />
        </Step>

        <Step n={2} title="Thêm Page">
          <AddPage settings={s} pages={pages} login={state.login} onAdded={refresh} />
        </Step>

        <Step n={3} title="Cách đăng">
          <Switch
            checked={f.fb_schedule} onChange={set("fb_schedule")} label="Hẹn giờ trên Facebook (Page qua API)" data-testid="fb-schedule" disabled={!hasApi && pages.length > 0}
            description="Bài hẹn từ 12 phút tới 30 ngày được gửi lên Facebook ngay để Facebook tự đăng đúng giờ, kể cả khi bạn tắt máy. Tắt đi thì ứng dụng tự đăng khi tới giờ (phải để ứng dụng chạy)."
          />
          <Switch
            checked={f.headless} onChange={set("headless")} label="Chạy ẩn trình duyệt (Page qua trình duyệt)" disabled={!hasBrowser}
            description="Không hiện cửa sổ khi đăng. Nên tắt trong vài lần đầu để theo dõi."
          />
        </Step>

        <Step n={4} title="Giới hạn an toàn">
          <Text size="sm" c="dimmed">
            Áp dụng <b>riêng cho từng Page</b>, giúp Page không bị Facebook hạn chế vì đăng quá dày. Bài vượt giới hạn
            được tự dời sang thời điểm hợp lệ kế tiếp; Lịch đăng sẽ ghi rõ lý do.
          </Text>
          <NumberInput
            label="Số bài tối đa mỗi ngày (mỗi Page)" description="0 = không giới hạn. Tính cả bài đã đăng và bài đã hẹn trên Facebook trong ngày."
            min={0} max={500} value={f.daily_max} onChange={(v) => { setF((x) => ({ ...x, daily_max: v })); setDirty(true); }} maw={300}
          />
          <div>
            <Text size="sm" fw={500} mb={6}>Giãn cách tối thiểu giữa 2 bài (cùng Page)</Text>
            <SegmentedControl data={gaps} value={f.min_gap} onChange={set("min_gap")} />
          </div>
          {state.limits && (
            <Text size="sm" c="dimmed" data-testid="limits-today">
              Hôm nay (Page mặc định): {state.limits.today}{state.limits.daily_max ? ` / ${state.limits.daily_max}` : ""} bài
            </Text>
          )}
        </Step>

        <Step n={5} title="Trợ lý AI (OpenAI)">
          <Text size="sm" c="dimmed">
            Gợi ý nội dung, hashtag và viết bài từ ý tưởng trong trang Soạn bài. Cần API key OpenAI của riêng bạn
            (tạo tại <Anchor href="https://platform.openai.com/api-keys" target="_blank">platform.openai.com</Anchor>);
            mỗi lần gợi ý tính phí nhỏ vào tài khoản đó.
          </Text>
          <PasswordInput
            label="API key OpenAI" placeholder="sk-…" value={f.openai_api_key} onChange={set("openai_api_key")} autoComplete="new-password" maw={460}
            description={s.openai_api_key_set ? "Đã lưu, để trống nếu không đổi" : s.ai_env_key ? "Đang dùng biến môi trường OPENAI_API_KEY" : "Chưa có key"}
          />
          <Autocomplete
            label="Model" maw={460} comboboxProps={{ withinPortal: true }} value={f.ai_model} onChange={set("ai_model")}
            description="Chọn gợi ý hoặc gõ tên model khác"
            data={[{ value: "gpt-5.4-mini", label: "gpt-5.4-mini" }, { value: "gpt-5.4", label: "gpt-5.4" }, { value: "gpt-5-mini", label: "gpt-5-mini" }]}
          />
          <TextInput
            label="Địa chỉ API (tuỳ chọn)" placeholder="https://api.openai.com/v1" value={f.ai_base_url} onChange={set("ai_base_url")} maw={460}
            description="Để trống nếu dùng OpenAI. Điền địa chỉ nếu dùng dịch vụ tương thích OpenAI (vd http://localhost:11434/v1)."
          />
        </Step>

        <Step n={6} title="Dữ liệu & sao lưu">
          <Text size="sm" c="dimmed">
            Mỗi ngày ứng dụng tự sao lưu <Code>data.json</Code> vào thư mục <Code>backups/</Code> (giữ 14 bản gần nhất),
            dọn bài đã đăng lâu ngày và xoá ảnh không còn bài/flow nào dùng (sau 7 ngày).
          </Text>
          <div>
            <Text size="sm" fw={500} mb={6}>Tự xoá bài đã đăng khỏi danh sách sau</Text>
            <SegmentedControl value={f.keep_done_days} onChange={set("keep_done_days")}
              data={[{ value: "30", label: "30 ngày" }, { value: "90", label: "90 ngày" }, { value: "365", label: "1 năm" }, { value: "0", label: "Giữ mãi" }]} />
          </div>
          <Group justify="space-between" wrap="wrap">
            <Text size="sm" c="dimmed" data-testid="backup-info">
              {state.maintenance?.last_run
                ? `Lần gần nhất: ${when(state.maintenance.last_run)} · ${state.maintenance.backups} bản sao lưu`
                : "Chưa sao lưu lần nào"}
            </Text>
            <Button variant="default" leftSection={<IconDatabase size={16} />} loading={busy} onClick={runMaintenance}>Sao lưu & dọn dẹp ngay</Button>
          </Group>
        </Step>

        <Step n={7} title="Ứng dụng">
          <AppCard />
        </Step>
      </Stack>

      <Affix position={{ bottom: 20, left: "50%" }} style={{ transform: "translateX(-50%)" }}>
        <Transition transition="slide-up" mounted={dirty}>
          {(styles) => (
            <Paper style={styles} shadow="xl" p="sm" pl="lg" radius="lg" withBorder>
              <Group gap="md" wrap="nowrap">
                <Text size="sm" fw={500}>Bạn có thay đổi chưa lưu</Text>
                <Button variant="default" onClick={() => { setF(initial()); setDirty(false); }}>Huỷ</Button>
                <Button onClick={save}>Lưu cài đặt</Button>
              </Group>
            </Paper>
          )}
        </Transition>
      </Affix>
    </>
  );
}
