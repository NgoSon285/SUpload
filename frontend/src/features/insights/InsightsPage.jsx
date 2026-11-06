import { useEffect, useState } from "react";
import {
  Alert, Badge, Button, Card, Group, Image, Paper, SegmentedControl, Select, SimpleGrid, Stack, Switch, Table, Text, ThemeIcon,
} from "@mantine/core";
import { IconChartBar, IconClock, IconFileSpreadsheet, IconRepeat, IconEye, IconHeart, IconInfoCircle, IconMessageCircle, IconRefresh, IconShare3, IconSparkles } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { imgUrl } from "../../api/client";
import { insightsApi } from "../../api/endpoints";
import { BarChart } from "../../components/BarChart";
import { EmptyState, PageHeader, notifyErr, notifyOk } from "../../components";
import { pagesOf } from "../../lib/page";
import { RecycleCard } from "./RecycleCard";
import { when } from "../../lib/time";

const nf = (n) => (n == null ? "—" : Number(n).toLocaleString("vi-VN"));

function Tile({ icon: Icon, label, value, note }) {
  return (
    <Paper withBorder p="md" shadow="xs">
      <Group gap="sm" wrap="nowrap" align="flex-start">
        <ThemeIcon size={38} radius="md" variant="light"><Icon size={20} /></ThemeIcon>
        <div style={{ minWidth: 0 }}>
          <Text fz={24} fw={700} lh={1.15}>{value}</Text>
          <Text size="sm" c="dimmed">{label}</Text>
          {note && <Text size="xs" c="dimmed" mt={2}>{note}</Text>}
        </div>
      </Group>
    </Paper>
  );
}

export function StatsLine({ stats }) {
  if (!stats || stats.reactions == null) return null;
  return (
    <Group gap="sm" c="dimmed" fz="xs" data-testid="post-stats">
      <Group gap={3}><IconHeart size={13} />{nf(stats.reactions)}</Group>
      <Group gap={3}><IconMessageCircle size={13} />{nf(stats.comments)}</Group>
      <Group gap={3}><IconShare3 size={13} />{nf(stats.shares)}</Group>
      {stats.reach != null && <Group gap={3}><IconEye size={13} />{nf(stats.reach)}</Group>}
    </Group>
  );
}

/** Thống kê tương tác: tổng quan, khung giờ hiệu quả, bài nổi bật. */
export default function InsightsPage() {
  const { state, refresh: refreshState, setView, setDraftPost } = useApp();
  const pages = pagesOf(state);
  const [days, setDays] = useState("30");
  const [page, setPage] = useState("");
  const [data, setData] = useState(null);
  const [table, setTable] = useState(false);

  const load = () => insightsApi.get({ days, page }).then(setData, (e) => notifyErr(e.message));
  useEffect(() => { load(); }, [days, page]); // eslint-disable-line
  const refresh = async () => {
    try { const r = await insightsApi.refresh(); notifyOk(`Đang cập nhật số liệu ${r.queued} bài, xong sau ít phút`); setTimeout(load, 4000); }
    catch (e) { notifyErr(e.message); }
  };

  const hourData = (data?.by_hour || []).map((b) => ({ key: b.key, label: `${b.key}h`, value: b.avg, tip: b.posts ? `${b.key}:00–${b.key}:59 · TB ${b.avg} tương tác · ${b.posts} bài` : `${b.key}:00–${b.key}:59 · chưa có bài` }));
  const dowData = (data?.by_dow || []).map((b) => ({ key: b.key, label: b.label, value: b.avg, tip: b.posts ? `${b.label} · TB ${b.avg} tương tác · ${b.posts} bài` : `${b.label} · chưa có bài` }));
  const t = data?.totals || {};
  const noPerm = !data?.reach_note || data.reach_note.includes("read_insights");

  return (
    <>
      <PageHeader
        title="Thống kê" desc="Tương tác của các bài đã đăng qua Graph API, và khung giờ đăng hiệu quả nhất."
        right={<Group gap="xs">
          <Button component="a" href={insightsApi.reportUrl({ days, page })} variant="default" leftSection={<IconFileSpreadsheet size={16} />}>Xuất Excel</Button>
          <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={refresh}>Cập nhật số liệu</Button>
        </Group>}
      />
      <Group mb="lg" gap="sm">
        <SegmentedControl value={days} onChange={setDays} data={[{ value: "7", label: "7 ngày" }, { value: "30", label: "30 ngày" }, { value: "90", label: "90 ngày" }]} />
        {pages.length > 1 && (
          <Select w={220} value={page} onChange={(v) => setPage(v || "")} allowDeselect={false} aria-label="Lọc theo Page" comboboxProps={{ withinPortal: true }}
            data={[{ value: "", label: "Tất cả Page" }, ...pages.map((p) => ({ value: p.id, label: p.name }))]} />
        )}
        {data?.updated_at && <Text size="xs" c="dimmed">Cập nhật lần cuối {when(data.updated_at)}</Text>}
      </Group>

      {!data ? null : data.posts === 0 ? (
        <Card>
          <EmptyState icon={IconChartBar} title="Chưa có số liệu"
            desc={data.waiting ? `Đang chờ lấy số liệu cho ${data.waiting} bài. Số liệu có khoảng 10 phút sau khi đăng, cập nhật mỗi 6 giờ trong 14 ngày.`
              : "Số liệu chỉ có cho bài đăng qua Graph API (không có cho cách Trình duyệt). Đăng vài bài rồi quay lại sau."} />
        </Card>
      ) : (
        <Stack gap="lg">
          <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }}>
            <Tile icon={IconChartBar} label="Bài có số liệu" value={nf(data.posts)} />
            <Tile icon={IconHeart} label="Tổng tương tác" value={nf(t.engagement)} note={`${nf(t.reactions)} cảm xúc · ${nf(t.comments)} bình luận · ${nf(t.shares)} chia sẻ`} />
            <Tile icon={IconSparkles} label="Tương tác trung bình / bài" value={nf(data.avg_engagement)} />
            <Tile icon={IconEye} label="Tiếp cận / lượt xem" value={nf(t.reach)}
              note={data.reach_missing ? (noPerm ? "Cần quyền read_insights" : "Chưa lấy được") : "Bài: người xem · Video/Reels: lượt xem"} />
          </SimpleGrid>

          {data.reach_missing && (
            <Alert variant="light" color="gray" icon={<IconInfoCircle />} py="xs">
              {noPerm
                ? <>Token chưa có quyền <b>read_insights</b> nên chưa xem được lượt tiếp cận. Tạo lại User Token với thêm quyền này rồi thêm lại Page (Cài đặt → Thêm Page).</>
                : <>Chưa lấy được lượt tiếp cận: {data.reach_note}</>}
            </Alert>
          )}

          <Card p="lg">
            <Group justify="space-between" mb="xs" wrap="wrap">
              <div>
                <Text fw={600}>Tương tác trung bình theo giờ đăng</Text>
                <Text size="sm" c="dimmed">Tổng cảm xúc + bình luận + chia sẻ, chia theo số bài đăng trong khung giờ đó.</Text>
              </div>
              {data.best_hours.length > 0 && (
                <Badge size="lg" variant="light" leftSection={<IconClock size={14} />} style={{ textTransform: "none" }} data-testid="best-hours">
                  Giờ hiệu quả nhất: {data.best_hours.map((h) => `${h}:00`).join(", ")}
                </Badge>
              )}
            </Group>
            <BarChart data={hourData} labelEvery={3} testId="chart-hour" />
            {!data.best_hours.length && <Text size="xs" c="dimmed" mt="xs">Cần ít nhất 2 bài trong cùng một khung giờ để so sánh.</Text>}
          </Card>

          <Card p="lg">
            <Text fw={600} mb="xs">Tương tác trung bình theo thứ trong tuần</Text>
            <BarChart data={dowData} height={120} testId="chart-dow" />
            <Switch mt="md" size="xs" label="Xem dạng bảng số liệu" checked={table} onChange={(e) => setTable(e.currentTarget.checked)} />
            {table && (
              <SimpleGrid cols={{ base: 1, sm: 2 }} mt="sm">
                {[["Giờ", data.by_hour.map((b) => ({ ...b, label: `${b.key}:00` }))], ["Thứ", data.by_dow]].map(([title, rows]) => (
                  <Table key={title} fz="xs" striped>
                    <Table.Thead><Table.Tr><Table.Th>{title}</Table.Th><Table.Th>Số bài</Table.Th><Table.Th>TB tương tác</Table.Th></Table.Tr></Table.Thead>
                    <Table.Tbody>{rows.filter((r) => r.posts).map((r) => <Table.Tr key={r.key}><Table.Td>{r.label}</Table.Td><Table.Td>{r.posts}</Table.Td><Table.Td>{r.avg}</Table.Td></Table.Tr>)}</Table.Tbody>
                  </Table>
                ))}
              </SimpleGrid>
            )}
          </Card>

          <Card p="lg">
            <Text fw={600} mb="sm">Bài nổi bật</Text>
            <Table verticalSpacing="xs" highlightOnHover data-testid="top-posts">
              <Table.Thead><Table.Tr><Table.Th>Bài</Table.Th><Table.Th w={150}>Đăng lúc</Table.Th><Table.Th w={220}>Tương tác</Table.Th><Table.Th w={60} /></Table.Tr></Table.Thead>
              <Table.Tbody>
                {data.top.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>
                      <Group gap="sm" wrap="nowrap">
                        {p.photos?.[0] && <Image src={imgUrl(p.photos[0])} w={36} h={36} radius="sm" />}
                        <Text size="sm" lineClamp={2}>{p.message || (p.video ? "Video" : "Bài chỉ có ảnh")}</Text>
                      </Group>
                    </Table.Td>
                    <Table.Td><Text size="xs">{when(p.done_at)}</Text></Table.Td>
                    <Table.Td><StatsLine stats={p.stats} /></Table.Td>
                    <Table.Td>
                      <Button size="compact-xs" variant="subtle" leftSection={<IconRepeat size={13} />} aria-label="Đăng lại bài này"
                        onClick={() => { const orig = state.posts.find((x) => x.id === p.id); if (orig) { setDraftPost({ post: orig, mode: "dup" }); setView("compose"); } }}>
                        Đăng lại
                      </Button>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </Card>
        </Stack>
      )}
      {data && <div style={{ marginTop: "var(--mantine-spacing-lg)" }}><RecycleCard onPosted={refreshState} /></div>}
    </>
  );
}
