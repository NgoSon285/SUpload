import { useEffect, useMemo, useState } from "react";
import {
  Alert, Button, Card, Chip, Collapse, Grid, Group, Kbd, SegmentedControl, Select, Stack, Text, TextInput, Textarea, ThemeIcon,
} from "@mantine/core";
import { DateTimePicker } from "@mantine/dates";
import { useHotkeys, useInterval } from "@mantine/hooks";
import { modals } from "@mantine/modals";
import { notifications } from "@mantine/notifications";
import { IconAlertCircle, IconClock, IconLink, IconMovie, IconPencil, IconPhoto, IconPlugConnected, IconSend, IconVideo } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { mediaApi, postsApi, stateApi } from "../../api/endpoints";
import { eventValue } from "../../lib/forms";
import { configured, pagesOf, targetPage } from "../../lib/page";
import { storage } from "../../lib/storage";
import { dayLabel, hm, presetTimes, rel, toLocalIso, when } from "../../lib/time";
import { AiAssistant, PageHeader, PhotoPicker, PostPreview, SnippetMenu, VideoPicker, notifyErr, usePasteImages } from "../../components";

const TYPES = [
  { value: "photo", label: "Bài viết", icon: IconPhoto },
  { value: "video", label: "Video", icon: IconVideo },
  { value: "reel", label: "Reels", icon: IconMovie },
];
const TITLES = { photo: "Soạn bài viết", video: "Đăng video", reel: "Đăng Reels" };
const kindOf = (p) => (p.video ? (p.video_kind === "reel" ? "reel" : "video") : "photo");

const EMPTY = { message: "", link: "", photos: [], page: "", video: "", video_kind: "video" }; // page "" = Page mặc định

const confirmShift = (preview) =>
  new Promise((resolve) => modals.openConfirmModal({
    title: "Bài sẽ được dời giờ",
    children: (
      <Text size="sm">
        Do giới hạn an toàn ({preview.reason}), bài sẽ được đăng lúc <b>{when(preview.effective_at)}</b>.
        Bạn có thể đổi giới hạn trong Cài đặt.
      </Text>
    ),
    labels: { confirm: "Đồng ý", cancel: "Huỷ" },
    onConfirm: () => resolve(true), onCancel: () => resolve(false),
  }));

export default function ComposePage() {
  const { state, refresh, setView, draftPost, setDraftPost, setComposeType } = useApp();
  const [post, setPost] = useState(() => ({ ...EMPTY, ...(storage.get("draft", EMPTY) || {}) }));
  const [mediaType, setMediaTypeState] = useState(() => storage.get("compose-type", kindOf(post)));
  const [showLink, setShowLink] = useState(!!post.link);
  const [mode, setMode] = useState("now");
  const [at, setAt] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [, tick] = useState(0);
  useInterval(() => tick((x) => x + 1), 30000, { autoInvoke: true });

  // Nhận bài từ Lịch đăng (Sửa / Dùng lại)
  useEffect(() => {
    if (!draftPost) return;
    const p = draftPost.post;
    if (draftPost.mode === "type") {  // từ menu "Đăng Reels": chỉ đổi loại bài, giữ nội dung đang soạn
      setMediaType(p.video_kind);
      setDraftPost(null);
      return;
    }
    setPost({ message: p.message || "", link: p.link || "", photos: [...(p.photos || [])], page: p.page || "", video: p.video || "", video_kind: p.video_kind || "video" });
    setMediaTypeState(p.video ? (p.video_kind === "reel" ? "reel" : "video") : "photo");
    setShowLink(!!p.link);
    if (draftPost.mode === "schedule") {  // từ Lịch: soạn bài mới cho một ngày
      setEditingId(null);
      setMode("later");
      setAt(new Date(p.scheduled_at));
    } else if (draftPost.mode === "edit") {
      setEditingId(p.id);
      const future = p.scheduled_at && new Date(p.scheduled_at) > new Date();
      setMode(future ? "later" : "now");
      setAt(future ? new Date(p.scheduled_at) : null);
    } else {
      setEditingId(null);
      setMode("now");
    }
    setDraftPost(null);
  }, [draftPost, setDraftPost]);

  useEffect(() => { if (!editingId) storage.set("draft", post); }, [post, editingId]);

  const set = (k) => (v) => { const val = eventValue(v); setPost((p) => ({ ...p, [k]: val })); };
  const s = state.settings;
  const ok = configured(state);
  const pages = pagesOf(state);
  const target = targetPage(state, post.page);
  const presets = useMemo(presetTimes, [mode, Math.floor(Date.now() / 60000)]); // eslint-disable-line
  const atValid = at && at > new Date();
  const isEmpty = !post.message.trim() && !post.photos.length && !post.link.trim() && !post.video;
  useEffect(() => { storage.set("compose-type", mediaType); setComposeType?.(mediaType); }, [mediaType, setComposeType]);
  const setMediaType = (t) => {
    t = TYPES.some((x) => x.value === t) ? t : "photo";
    setMediaTypeState(t);
    setPost((p) => ({ ...p, photos: t === "photo" ? p.photos : [], video: t === "photo" ? "" : p.video, video_kind: t === "reel" ? "reel" : "video" }));
  };

  const chooseMode = (m) => {
    setMode(m);
    if (m === "later" && !atValid) setAt(presets[0]?.[1] || new Date(Date.now() + 3600000));
  };

  const reset = () => {
    // giữ loại bài đang chọn (vd đăng nhiều Reels liên tiếp)
    setPost((p) => ({ ...EMPTY, video_kind: p.video_kind || "video" })); setShowLink(false); setMode("now"); setAt(null); setEditingId(null);
    storage.set("draft", EMPTY);
  };

  const askClear = () =>
    isEmpty ? reset() : modals.openConfirmModal({
      title: "Xoá nội dung đang soạn?",
      children: <Text size="sm">Nội dung và ảnh trong khung soạn sẽ bị xoá.</Text>,
      labels: { confirm: "Xoá nội dung", cancel: "Huỷ" },
      confirmProps: { color: "red" },
      onConfirm: reset,
    });

  const submit = async () => {
    if (!ok) {
      notifications.show({ color: "orange", title: "Chưa kết nối Page", message: "Vào Cài đặt để kết nối Page trước khi đăng." });
      return;
    }
    if (isEmpty) return notifyErr("Bài viết đang trống");
    if (mode === "later" && !atValid) return notifyErr("Chọn thời gian hẹn trong tương lai");
    const body = { ...post, scheduled_at: mode === "later" ? toLocalIso(at) : null };
    if (!body.video) { delete body.video; delete body.video_kind; }
    setBusy(true);
    try {
      // Giới hạn an toàn có thể dời bài -> báo trước để người dùng quyết định
      const preview = editingId ? null : (await stateApi.previewPlan([{ scheduled_at: body.scheduled_at, page: post.page }])).items[0];
      if (preview?.shifted && !(await confirmShift(preview))) { setBusy(false); return; }
      if (editingId) {
        await postsApi.edit(editingId, body);
        notifications.show({ color: "teal", message: "Đã lưu thay đổi" });
        reset();
        setView("queue");
      } else {
        await postsApi.add(body);
        const real = preview?.shifted ? new Date(preview.effective_at) : mode === "later" ? at : null;
        notifications.show({
          color: real ? "teal" : "indigo",
          title: real ? "Đã lên lịch" : "Đang đăng bài",
          message: real ? `Bài sẽ được đăng lúc ${hm(real)}, ${dayLabel(real).toLowerCase()}.` : "Bài đã vào hàng đợi và sẽ được đăng ngay.",
        });
        reset();
      }
      refresh();
    } catch (e) {
      notifyErr(e.message);
    }
    setBusy(false);
  };

  useHotkeys([["mod+Enter", submit]], []);
  const fbSchedules = target?.kind === "api" && s.fb_schedule;
  const onPaste = usePasteImages(async (files) => {
    try { const names = await mediaApi.upload(files); setPost((p) => ({ ...p, photos: [...p.photos, ...names] })); }
    catch (e) { notifyErr(e.message); }
  });

  return (
    <>
      <PageHeader title={editingId ? "Sửa bài viết" : TITLES[mediaType]}
        desc={mediaType === "reel" ? "Đăng video dọc ngắn dạng Reels lên Page, đăng ngay hoặc hẹn giờ." : "Viết nội dung, thêm ảnh hoặc video và chọn thời điểm đăng lên Page."} />

      {!ok && (
        <Alert mb="lg" variant="light" color="indigo" radius="lg" icon={<IconPlugConnected />} title="Kết nối Page để bắt đầu">
          <Group justify="space-between">
            <Text size="sm">Bạn cần kết nối Page một lần trước khi đăng bài.</Text>
            <Button size="xs" onClick={() => setView("settings")}>Thiết lập ngay</Button>
          </Group>
        </Alert>
      )}

      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <Card p="lg">
            <Stack gap="md">
              {editingId && (
                <Alert color="orange" variant="light" icon={<IconPencil size={18} />} py="xs">
                  <Group justify="space-between">
                    <Text size="sm" fw={500}>Đang sửa một bài trong lịch đăng</Text>
                    <Button size="compact-sm" variant="subtle" color="orange" onClick={() => { reset(); setView("queue"); }}>Huỷ sửa</Button>
                  </Group>
                </Alert>
              )}

              <SegmentedControl
                fullWidth size="md" radius="md" value={mediaType} onChange={setMediaType} data-testid="media-type"
                data={TYPES.map(({ value, label, icon: Icon }) => ({ value, label: <Group gap={8} justify="center" wrap="nowrap"><Icon size={18} />{label}</Group> }))}
              />

              {pages.length > 1 && (
                <Select
                  label="Đăng lên Page" data-testid="page-select" allowDeselect={false} comboboxProps={{ withinPortal: true }}
                  value={post.page || ""} onChange={(v) => setPost((p) => ({ ...p, page: v || "" }))}
                  data={[{ value: "", label: `Page mặc định (${pages.find((p) => p.default)?.name || pages[0].name})` },
                    ...pages.map((p) => ({ value: p.id, label: p.name }))]}
                />
              )}

              <Textarea
                label="Nội dung" placeholder="Bạn muốn chia sẻ điều gì với người theo dõi Page?"
                autosize minRows={5} maxRows={16} value={post.message} onChange={set("message")} onPaste={onPaste}
                description={`${post.message.length.toLocaleString("vi-VN")} ký tự · dán ảnh trực tiếp bằng Ctrl+V`}
                inputWrapperOrder={["label", "input", "description"]} size="md"
              />

              <Group gap="xs" mt={-8}>
                <SnippetMenu value={post.message} onChange={(v) => setPost((p) => ({ ...p, message: v }))} onOpenLibrary={() => setView("library")} />
                <AiAssistant text={post.message} page={post.page} onApply={(v) => setPost((p) => ({ ...p, message: v }))} onOpenSettings={() => setView("settings")} />
              </Group>

              <div>
                <Text size="sm" fw={500} mb={6}>{mediaType === "photo" ? "Ảnh" : mediaType === "reel" ? "Video Reels" : "Video"}</Text>
                {mediaType === "reel" && (
                  <Alert variant="light" color={target?.kind === "browser" ? "red" : "violet"} py="xs" mb="xs" icon={<IconMovie size={18} />} data-testid="reel-hint">
                    <Text size="sm">
                      {target?.kind === "browser"
                        ? "Page này đăng qua Trình duyệt: Reels chỉ đăng được với Page kết nối qua Graph API."
                        : "Video dọc 9:16, dài 3–90 giây. Facebook cho tối đa 30 Reels qua API mỗi Page trong 24 giờ."}
                    </Text>
                  </Alert>
                )}
                {mediaType === "photo"
                  ? <PhotoPicker value={post.photos} onChange={set("photos")} />
                  : <VideoPicker value={post.video} onChange={set("video")} reel={mediaType === "reel"} />}
              </div>

              <div>
                {!showLink ? (
                  <Button variant="subtle" size="compact-sm" leftSection={<IconLink size={16} />} onClick={() => setShowLink(true)}>Thêm link</Button>
                ) : (
                  <TextInput label="Link" placeholder="https://..." leftSection={<IconLink size={16} />} value={post.link} onChange={set("link")} />
                )}
              </div>

              <Card withBorder={false} shadow="none" bg="var(--mantine-color-default-hover)" p="md" radius="md">
                <Group justify="space-between" wrap="wrap">
                  <Text fw={600} size="sm">Thời điểm đăng</Text>
                  <SegmentedControl value={mode} onChange={chooseMode} data={[{ value: "now", label: "Đăng ngay" }, { value: "later", label: "Hẹn giờ" }]} />
                </Group>
                <Collapse in={mode === "later"}>
                  <Stack gap="sm" mt="md">
                    <Group gap={6}>
                      {presets.map(([label, d]) => (
                        <Chip key={label} size="sm" checked={!!at && +at === +d} onChange={() => setAt(d)}>{label}</Chip>
                      ))}
                    </Group>
                    <DateTimePicker
                      placeholder="Chọn ngày giờ" value={at} onChange={setAt} minDate={new Date()}
                      valueFormat="HH:mm, DD/MM/YYYY" leftSection={<IconClock size={16} />} maw={300} clearable={false}
                    />
                    {atValid ? (
                      <>
                        <Text size="sm" c="indigo" fw={500}>Sẽ đăng lúc {hm(at)}, {dayLabel(at).toLowerCase()} ({rel(at)})</Text>
                        <Text size="xs" c="dimmed" data-testid="who-posts">
                          {fbSchedules && at - Date.now() >= 12 * 60000
                            ? "Bài sẽ được gửi lên Facebook để Facebook tự đăng đúng giờ, kể cả khi bạn tắt máy."
                            : "Ứng dụng sẽ tự đăng khi tới giờ, nên cần để ứng dụng đang chạy lúc đó."}
                        </Text>
                      </>
                    ) : (
                      <Group gap={6} c="red"><IconAlertCircle size={16} /><Text size="sm">{at ? "Thời gian này đã qua" : "Chọn ngày giờ muốn đăng"}</Text></Group>
                    )}
                  </Stack>
                </Collapse>
              </Card>

              <Group justify="space-between">
                <Button variant="subtle" color="gray" onClick={askClear}>Xoá nội dung</Button>
                <Group gap="sm">
                  <Text size="xs" c="dimmed" visibleFrom="sm"><Kbd size="xs">Ctrl</Kbd> + <Kbd size="xs">Enter</Kbd></Text>
                  <Button size="md" loading={busy} onClick={submit} leftSection={mode === "later" ? <IconClock size={18} /> : <IconSend size={18} />}>
                    {editingId ? "Lưu thay đổi" : mode === "later" ? "Lên lịch" : "Đăng ngay"}
                  </Button>
                </Group>
              </Group>
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 5 }}>
          <div style={{ position: "sticky", top: 80 }}>
            <Group gap={6} mb="xs"><ThemeIcon size="sm" variant="light" radius="xl"><IconSend size={12} /></ThemeIcon><Text size="xs" fw={700} c="dimmed" tt="uppercase">Xem trước</Text></Group>
            <PostPreview
              name={target?.name} {...post}
              scheduled={mode === "later" && atValid}
              timeLabel={mode === "later" && atValid ? when(at) : "Vừa xong"}
            />
            <Text size="xs" c="dimmed" mt="xs">Bản xem trước chỉ mang tính minh hoạ, hiển thị thực tế trên Facebook có thể khác một chút.</Text>
          </div>
        </Grid.Col>
      </Grid>
    </>
  );
}
