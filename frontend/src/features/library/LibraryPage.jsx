import { useEffect, useState } from "react";
import {
  ActionIcon, Badge, Button, Card, CopyButton, Group, Modal, SegmentedControl, SimpleGrid, Stack, Tabs, Text, Textarea, TextInput, Tooltip,
} from "@mantine/core";
import { modals } from "@mantine/modals";
import { IconCheck, IconCopy, IconHash, IconPencil, IconPhoto, IconPlus, IconSignature, IconTemplate, IconTrash } from "@tabler/icons-react";

import { imgUrl } from "../../api/client";
import { libraryApi, mediaApi } from "../../api/endpoints";
import { EmptyState, PageHeader, PhotoPicker, notifyErr, notifyOk } from "../../components";

const KIND_ICON = { hashtag: IconHash, signature: IconSignature, template: IconTemplate };
const KIND_HINT = {
  hashtag: "#tiembanh #banhngon #hanoi",
  signature: "📍 12 Hàng Bông, Hà Nội\n☎️ 0900 000 000",
  template: "🔥 KHUYẾN MÃI {hôm nay|cuối tuần}\nGiảm 20% toàn bộ bánh kem…",
};

function ItemForm({ opened, item, onClose, onSaved }) {
  const [f, setF] = useState({ kind: "hashtag", name: "", content: "" });
  useEffect(() => { if (opened) setF(item ? { kind: item.kind, name: item.name, content: item.content } : { kind: "hashtag", name: "", content: "" }); }, [opened, item]);
  const save = async () => {
    try {
      if (item) await libraryApi.edit(item.id, f); else await libraryApi.add(f);
      notifyOk("Đã lưu vào thư viện");
      onSaved();
      onClose();
    } catch (e) { notifyErr(e.message); }
  };
  return (
    <Modal opened={opened} onClose={onClose} radius="lg" title={<Text fw={600}>{item ? "Sửa mục" : "Thêm vào thư viện"}</Text>}>
      <Stack>
        <SegmentedControl fullWidth value={f.kind} onChange={(kind) => setF({ ...f, kind })}
          data={[{ value: "hashtag", label: "Bộ hashtag" }, { value: "signature", label: "Chữ ký" }, { value: "template", label: "Mẫu bài" }]} />
        <TextInput label="Tên" placeholder="Không bắt buộc" value={f.name} onChange={(e) => setF({ ...f, name: e.currentTarget.value })} />
        <Textarea label="Nội dung" autosize minRows={4} maxRows={14} placeholder={KIND_HINT[f.kind]} value={f.content}
          onChange={(e) => setF({ ...f, content: e.currentTarget.value })} description="Có thể dùng {a|b} để chọn ngẫu nhiên khi dùng trong Flow." />
        <Group justify="flex-end"><Button variant="default" onClick={onClose}>Huỷ</Button><Button onClick={save} disabled={!f.content.trim()}>Lưu</Button></Group>
      </Stack>
    </Modal>
  );
}

function Snippets() {
  const [data, setData] = useState({ items: [], kinds: {} });
  const [form, setForm] = useState(null); // {item?}
  const load = () => libraryApi.list().then(setData, (e) => notifyErr(e.message));
  useEffect(() => { load(); }, []);
  const remove = (x) => modals.openConfirmModal({
    title: `Xoá “${x.name}”?`, labels: { confirm: "Xoá", cancel: "Huỷ" }, confirmProps: { color: "red" },
    onConfirm: async () => { await libraryApi.remove(x.id); load(); },
  });
  return (
    <Stack>
      <Group justify="space-between">
        <Text size="sm" c="dimmed">Lưu sẵn những đoạn hay dùng, rồi chèn bằng nút <b>Chèn từ thư viện</b> khi soạn bài.</Text>
        <Button leftSection={<IconPlus size={16} />} onClick={() => setForm({})}>Thêm</Button>
      </Group>
      {!data.items.length ? (
        <Card><EmptyState icon={IconHash} title="Thư viện trống" desc="Thêm bộ hashtag, chữ ký (địa chỉ, hotline) hoặc mẫu bài để dùng lại." /></Card>
      ) : Object.entries(data.kinds).map(([kind, label]) => {
        const list = data.items.filter((x) => x.kind === kind);
        if (!list.length) return null;
        const Icon = KIND_ICON[kind];
        return (
          <div key={kind}>
            <Group gap={6} mb={8}><Icon size={16} /><Text size="xs" fw={700} c="dimmed" tt="uppercase">{label} · {list.length}</Text></Group>
            <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
              {list.map((x) => (
                <Card key={x.id} p="sm" data-testid="lib-item">
                  <Group justify="space-between" wrap="nowrap" align="flex-start">
                    <Text fw={600} size="sm" truncate>{x.name}</Text>
                    <Group gap={0} wrap="nowrap">
                      <CopyButton value={x.content}>{({ copied, copy }) => (
                        <Tooltip label={copied ? "Đã chép" : "Chép"}><ActionIcon variant="subtle" color="gray" onClick={copy}>{copied ? <IconCheck size={16} /> : <IconCopy size={16} />}</ActionIcon></Tooltip>
                      )}</CopyButton>
                      <ActionIcon variant="subtle" color="gray" onClick={() => setForm({ item: x })} aria-label="Sửa"><IconPencil size={16} /></ActionIcon>
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(x)} aria-label="Xoá"><IconTrash size={16} /></ActionIcon>
                    </Group>
                  </Group>
                  <Text size="sm" c="dimmed" lineClamp={4} style={{ whiteSpace: "pre-wrap" }} mt={4}>{x.content}</Text>
                  {x.used > 0 && <Text size="xs" c="dimmed" mt={6}>Đã dùng {x.used} lần</Text>}
                </Card>
              ))}
            </SimpleGrid>
          </div>
        );
      })}
      <ItemForm opened={!!form} item={form?.item} onClose={() => setForm(null)} onSaved={load} />
    </Stack>
  );
}

const fmtSize = (b) => (b > 1048576 ? `${(b / 1048576).toFixed(1)} MB` : `${Math.ceil(b / 1024)} KB`);

function Media() {
  const [media, setMedia] = useState(null);
  const [added, setAdded] = useState([]);
  const load = () => mediaApi.list().then(setMedia, (e) => notifyErr(e.message));
  useEffect(() => { load(); }, []);
  const remove = async (m) => {
    try { await mediaApi.remove(m.name); load(); } catch (e) { notifyErr(e.message); }
  };
  const unused = (media || []).filter((m) => !m.used);
  return (
    <Stack>
      <PhotoPicker compact value={added} onChange={(v) => { setAdded([]); if (v.length) load(); }} />
      <Group justify="space-between">
        <Text size="sm" c="dimmed">{media ? `${media.length} file · ${unused.length} file không còn bài/flow nào dùng` : "Đang tải…"}</Text>
      </Group>
      {media && !media.length ? (
        <Card><EmptyState icon={IconPhoto} title="Chưa có ảnh nào" desc="Ảnh tải lên khi soạn bài sẽ hiện ở đây." /></Card>
      ) : (
        <SimpleGrid cols={{ base: 3, sm: 5, lg: 7 }} spacing="xs">
          {(media || []).map((m) => (
            <Card key={m.name} p={0} data-testid="media-item">
              <div className="thumb" style={{ borderRadius: 0, border: 0 }}>
                {m.kind === "video" ? <video src={imgUrl(m.name)} muted style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <img src={imgUrl(m.name)} alt="" />}
                {m.used > 0 && <Badge size="xs" pos="absolute" top={4} left={4} color="indigo" variant="filled">dùng {m.used}</Badge>}
              </div>
              <Group justify="space-between" px={6} py={4} wrap="nowrap">
                <Text size="xs" c="dimmed">{fmtSize(m.size)}</Text>
                <Tooltip label={m.used ? "Đang được dùng, không xoá được" : "Xoá file"}>
                  <ActionIcon size="sm" variant="subtle" color="red" disabled={m.used > 0} onClick={() => remove(m)} aria-label={`Xoá ${m.name}`}><IconTrash size={14} /></ActionIcon>
                </Tooltip>
              </Group>
            </Card>
          ))}
        </SimpleGrid>
      )}
    </Stack>
  );
}

/** Thư viện: đoạn nội dung dùng lại và ảnh/video đã tải lên. */
export default function LibraryPage() {
  return (
    <>
      <PageHeader title="Thư viện" desc="Bộ hashtag, chữ ký, mẫu bài và ảnh dùng lại cho mọi bài viết." />
      <Tabs defaultValue="snippets" keepMounted={false}>
        <Tabs.List mb="md">
          <Tabs.Tab value="snippets" leftSection={<IconHash size={16} />}>Đoạn nội dung</Tabs.Tab>
          <Tabs.Tab value="media" leftSection={<IconPhoto size={16} />}>Ảnh & video</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="snippets"><Snippets /></Tabs.Panel>
        <Tabs.Panel value="media"><Media /></Tabs.Panel>
      </Tabs>
    </>
  );
}
