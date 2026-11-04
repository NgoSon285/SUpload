import { useMemo, useState } from "react";
import { ActionIcon, Badge, Button, Group, Paper, SegmentedControl, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { IconChevronLeft, IconChevronRight, IconPlus } from "@tabler/icons-react";
import dayjs from "dayjs";

import { eventTime, monthGrid, MOVABLE, sameDay, weekGrid } from "../../lib/calendar";
import { hm } from "../../lib/time";
import { STATUS } from "./status";

const DOW = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"];
const MAX_IN_CELL = 3;

function Chip({ p, pageName, onOpen, onDragStart }) {
  const st = STATUS[p.status] || STATUS.pending;
  const movable = MOVABLE.has(p.status);
  return (
    <Tooltip label={`${st.label}${pageName ? ` · ${pageName}` : ""}${p.shift_reason ? ` · dời vì ${p.shift_reason}` : ""}`} withArrow openDelay={400}>
      <UnstyledButton
        className="cal-chip" data-status={p.status} data-testid="cal-chip" draggable={movable}
        onDragStart={(e) => { if (!movable) return e.preventDefault(); e.dataTransfer.setData("text/supload-post", p.id); e.dataTransfer.effectAllowed = "move"; onDragStart(p.id); }}
        onClick={(e) => { e.stopPropagation(); onOpen(p); }}
        style={{ "--chip": `var(--mantine-color-${st.color}-6)`, cursor: movable ? "grab" : "pointer" }}
      >
        <Text span size="xs" fw={700}>{hm(eventTime(p))}</Text>{" "}
        <Text span size="xs">{p.message || p.link || "Bài chỉ có ảnh"}</Text>
      </UnstyledButton>
    </Tooltip>
  );
}

/** Lịch tháng/tuần. Kéo bài sang ngày khác để đổi lịch (giữ giờ), bấm ô trống để soạn bài cho ngày đó. */
export function CalendarView({ posts, pageName, onOpen, onMove, onCreateAt }) {
  const [mode, setMode] = useState("month");
  const [cursor, setCursor] = useState(() => new Date());
  const [dragging, setDragging] = useState(null);
  const [over, setOver] = useState(null);
  const [expanded, setExpanded] = useState(null);

  const days = mode === "month" ? monthGrid(cursor) : weekGrid(cursor);
  const byDay = useMemo(() => {
    const m = new Map();
    for (const p of posts) {
      const t = eventTime(p);
      if (!t) continue;
      const k = dayjs(t).format("YYYY-MM-DD");
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(p);
    }
    for (const list of m.values()) list.sort((a, b) => new Date(eventTime(a)) - new Date(eventTime(b)));
    return m;
  }, [posts]);

  const step = (n) => setCursor((c) => dayjs(c).add(n, mode === "month" ? "month" : "week").toDate());
  const title = mode === "month"
    ? `Tháng ${dayjs(cursor).month() + 1}, ${dayjs(cursor).year()}`
    : `${dayjs(days[0]).format("D/M")} – ${dayjs(days[6]).format("D/M/YYYY")}`;
  const today = new Date();

  const drop = (e, day) => {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/supload-post") || dragging;
    setOver(null);
    setDragging(null);
    const p = posts.find((x) => x.id === id);
    if (p && !sameDay(eventTime(p), day)) onMove(p, day);
  };

  return (
    <Stack gap="sm">
      <Group justify="space-between" wrap="wrap">
        <Group gap="xs">
          <ActionIcon variant="default" size="lg" onClick={() => step(-1)} aria-label="Trước"><IconChevronLeft size={18} /></ActionIcon>
          <Button variant="default" onClick={() => setCursor(new Date())}>Hôm nay</Button>
          <ActionIcon variant="default" size="lg" onClick={() => step(1)} aria-label="Sau"><IconChevronRight size={18} /></ActionIcon>
          <Text fw={700} ml="xs" data-testid="cal-title">{title}</Text>
        </Group>
        <SegmentedControl value={mode} onChange={setMode} data={[{ value: "month", label: "Tháng" }, { value: "week", label: "Tuần" }]} />
      </Group>

      <Paper withBorder radius="lg" style={{ overflow: "hidden" }}>
        <div className="cal-grid cal-head">
          {DOW.map((d) => <Text key={d} size="xs" fw={700} c="dimmed" ta="center" py={6}>{d}</Text>)}
        </div>
        <div className={`cal-grid ${mode === "week" ? "cal-week" : "cal-month"}`}>
          {days.map((day) => {
            const key = dayjs(day).format("YYYY-MM-DD");
            const list = byDay.get(key) || [];
            const outside = mode === "month" && dayjs(day).month() !== dayjs(cursor).month();
            const past = dayjs(day).isBefore(today, "day");
            const show = mode === "week" || expanded === key ? list : list.slice(0, MAX_IN_CELL);
            return (
              <div
                key={key} className="cal-cell" data-testid="cal-day" data-date={key}
                data-outside={outside || undefined} data-today={sameDay(day, today) || undefined}
                data-over={over === key || undefined} data-past={past || undefined}
                onDragOver={(e) => { if (dragging && !past) { e.preventDefault(); setOver(key); } }}
                onDragLeave={() => setOver((o) => (o === key ? null : o))}
                onDrop={(e) => drop(e, day)}
                onDoubleClick={() => !past && onCreateAt(day)}
              >
                <Group justify="space-between" gap={2} wrap="nowrap">
                  <Text size="xs" fw={sameDay(day, today) ? 700 : 500} className="cal-daynum">{dayjs(day).date()}</Text>
                  {!past && (
                    <ActionIcon className="cal-add" size="xs" variant="subtle" onClick={() => onCreateAt(day)} aria-label={`Soạn bài ngày ${dayjs(day).format("D/M")}`}>
                      <IconPlus size={12} />
                    </ActionIcon>
                  )}
                </Group>
                <Stack gap={3} mt={4}>
                  {show.map((p) => <Chip key={p.id} p={p} pageName={pageName(p)} onOpen={onOpen} onDragStart={setDragging} />)}
                  {list.length > show.length && (
                    <Badge size="xs" variant="light" color="gray" style={{ cursor: "pointer", textTransform: "none" }} onClick={() => setExpanded(key)}>
                      +{list.length - show.length} bài
                    </Badge>
                  )}
                </Stack>
              </div>
            );
          })}
        </div>
      </Paper>
      <Text size="xs" c="dimmed">Kéo bài sang ngày khác để đổi lịch (giữ nguyên giờ). Bấm + hoặc nhấp đúp vào ô ngày để soạn bài cho ngày đó. Bấm vào bài để sửa.</Text>
    </Stack>
  );
}
