import { ActionIcon, Alert, Badge, Card, Group, Image, Stack, Text, ThemeIcon, Tooltip } from "@mantine/core";
import {
  IconAlertTriangle, IconBrandFacebook, IconCheck, IconClock, IconCopy, IconLink, IconPencil, IconPhoto, IconRefresh,
  IconSend, IconSitemap, IconTrash, IconArrowForward, IconMovie, IconMessageCircle, IconMessagePlus,
} from "@tabler/icons-react";

import { imgUrl } from "../../api/client";
import { hm, rel, when } from "../../lib/time";
import { StatsLine } from "../insights/InsightsPage";
import { STATUS, upcomingTime } from "./status";

/** Bình luận đầu tiên (AI / link affiliate) của bài: sẽ bình luận, đã bình luận, hay lỗi. */
function FirstCommentLine({ p }) {
  const fc = p.first_comment || {};
  const what = p.affiliate_link ? (p.ai_comment ? "AI + link affiliate" : "link affiliate") : "AI";
  const [color, text] = fc.id ? ["teal", `Đã bình luận đầu tiên (${what})`]
    : fc.error ? ["orange", `Chưa bình luận đầu tiên được (lần ${fc.tries || 1}): ${fc.error}`]
    : ["dimmed", `Sẽ bình luận đầu tiên sau khi đăng (${what})`];
  return (
    <Tooltip label={fc.text} disabled={!fc.text} multiline maw={360} withinPortal>
      <Group gap={4} fz="xs" c={color} wrap="nowrap" data-testid="first-comment-line"><IconMessageCircle size={14} /><Text span size="xs" lineClamp={1}>{text}</Text></Group>
    </Tooltip>
  );
}

function TimeLine({ p }) {
  if (p.status === "done") return <><IconCheck size={14} />Đã đăng {p.done_at ? when(p.done_at) : ""}</>;
  if (p.status === "running") return <><IconSend size={14} />Đang đăng…</>;
  if (p.status === "scheduled") return <><IconBrandFacebook size={14} />Facebook sẽ tự đăng lúc {when(p.fb_scheduled_at)} · {rel(p.fb_scheduled_at)}</>;
  const t = upcomingTime(p);
  if (!t) return <><IconSend size={14} />Đăng ngay khi đến lượt</>;
  return <><IconClock size={14} />{hm(t)} · {rel(t)}{p.fb_handoff ? " · sẽ hẹn trên Facebook" : ""}</>;
}

export function PostRow({ p, pageName, canComment, onAction }) {
  const st = STATUS[p.status] || STATUS.pending;
  const act = (a, Icon, label, color = "gray") => (
    <Tooltip label={label} withArrow>
      <ActionIcon variant="subtle" color={color} onClick={() => onAction(a, p)} aria-label={label}><Icon size={18} /></ActionIcon>
    </Tooltip>
  );
  return (
    <Card p="sm" shadow="none" data-testid="post-row">
      <Group align="flex-start" wrap="nowrap" gap="md">
        {p.video ? (
          <ThemeIcon size={64} radius="md" variant="light" color="grape"><IconMovie size={26} /></ThemeIcon>
        ) : p.photos.length ? (
          <div style={{ position: "relative", flex: "none" }}>
            <Image src={imgUrl(p.photos[0])} w={64} h={64} radius="md" fit="cover" />
            {p.photos.length > 1 && <Badge size="xs" color="dark" style={{ position: "absolute", right: 4, bottom: 4 }}>+{p.photos.length - 1}</Badge>}
          </div>
        ) : (
          <ThemeIcon size={64} radius="md" variant="light" color="gray">{p.link ? <IconLink size={24} /> : <IconPencil size={24} />}</ThemeIcon>
        )}
        <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
          <Group gap={6}>
            <Badge variant="light" color={st.color} size="sm">{st.label}</Badge>
            {p.channel === "instagram" && <Badge variant="light" color="pink" size="sm" data-testid="ig-badge">Instagram</Badge>}
            {p.source === "recycle" && <Badge variant="light" color="teal" size="sm">Đăng lại</Badge>}
            {p.video && <Badge variant="light" color="grape" size="sm">{p.video_kind === "reel" ? "Reels" : "Video"}</Badge>}
            {pageName && <Badge variant="outline" color="indigo" size="sm" style={{ textTransform: "none" }}>{pageName}</Badge>}
            {p.flow && <Badge variant="outline" color="gray" size="sm" leftSection={<IconSitemap size={11} />} style={{ textTransform: "none" }}>{p.flow}</Badge>}
          </Group>
          <Text lineClamp={2} size="sm" c={p.message ? undefined : "dimmed"} fs={p.message ? undefined : "italic"}>
            {p.message || p.link || "Bài chỉ có ảnh"}
          </Text>
          <Group gap="md" c="dimmed">
            <Group gap={4} fz="xs"><TimeLine p={p} /></Group>
            {p.photos.length > 0 && <Group gap={4} fz="xs"><IconPhoto size={14} />{p.photos.length} ảnh</Group>}
            {p.link && p.message && <Group gap={4} fz="xs"><IconLink size={14} />có link</Group>}
          </Group>
          {p.status === "done" && <StatsLine stats={p.stats} />}
          {p.shift_reason && (
            <Group gap={4} fz="xs" c="orange" data-testid="shift-reason">
              <IconArrowForward size={14} />Dời sang {when(p.effective_at)} vì {p.shift_reason}
            </Group>
          )}
          {(p.ai_comment || p.affiliate_link) && <FirstCommentLine p={p} />}
          {p.page_comments?.length > 0 && (
            <Tooltip label={p.page_comments.at(-1).text} multiline maw={360} withinPortal>
              <Group gap={4} fz="xs" c="indigo" data-testid="page-comments"><IconMessageCircle size={14} />Page đã bình luận {p.page_comments.length} lần</Group>
            </Tooltip>
          )}
          {p.error && <Alert color="red" variant="light" p="xs" mt={4} icon={<IconAlertTriangle size={16} />}><Text size="xs">{p.error}</Text></Alert>}
        </Stack>
        {p.status !== "running" && (
          <Group gap={2} wrap="nowrap">
            {p.status === "error" && act("retry", IconRefresh, "Đăng lại ngay", "indigo")}
            {canComment && act("comment", IconMessagePlus, "Bình luận vào bài", "indigo")}
            {p.status !== "done" && act("edit", IconPencil, "Sửa")}
            {act("dup", IconCopy, "Dùng lại nội dung")}
            {act("del", IconTrash, "Xoá", "red")}
          </Group>
        )}
      </Group>
    </Card>
  );
}
