import { useEffect, useState } from "react";
import { Button, Group, Stack, Text, TextInput, Textarea } from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { IconDownload, IconFolder, IconFolderOpen } from "@tabler/icons-react";

import { useApp } from "../../app/context";
import { reviewApi } from "../../api/endpoints";
import { PageHeader, notifyErr, notifyOk } from "../../components";
import { Step } from "../settings/ui";

const LINK_RE = /^https?:\/\/\S*(shopee\.|shp\.ee|tiktok)/i;

/** Ảnh sản phẩm Shopee / TikTok Shop: thư mục lưu + danh sách link. Phần lấy ảnh làm sau. */
export default function ReviewPage() {
  const { state, refresh } = useApp();
  const saved = state.settings.review_dir || "";
  const [dir, setDir] = useState(saved);
  const [links, setLinks] = useState("");
  const [picking, setPicking] = useState(false);
  useEffect(() => { setDir(saved); }, [saved]);
  const count = new Set(links.split("\n").map((l) => l.trim()).filter((l) => LINK_RE.test(l))).size;

  const saveDir = async (d = dir) => {
    try { const r = await reviewApi.setDir(d); setDir(r.dir); notifyOk("Đã lưu thư mục"); refresh(); }
    catch (e) { notifyErr(e.message); }
  };
  const pickDir = async () => {  // hộp chọn thư mục của hệ điều hành; chọn xong lưu luôn
    setPicking(true);
    try { const r = await reviewApi.pickDir(); if (r.dir) await saveDir(r.dir); }
    catch (e) { notifyErr(e.message); }
    setPicking(false);
  };
  const open = () => reviewApi.open().catch((e) => notifyErr(e.message));
  // ponytail: chưa có logic lấy ảnh; nối vào đây khi làm
  const fetchImages = () => notifications.show({ color: "orange", title: "Đang phát triển", message: `Chức năng lấy ảnh cho ${count} sản phẩm sẽ có sau.` });

  return (
    <>
      <PageHeader title="Ảnh sản phẩm" desc="Lấy ảnh sản phẩm Shopee / TikTok Shop về máy để làm bài review. Mỗi sản phẩm một thư mục." />
      <Stack maw={820} gap="lg">
        <Step n={1} title="Thư mục lưu ảnh" right={saved && <Button size="xs" variant="default" leftSection={<IconFolderOpen size={14} />} onClick={open}>Mở thư mục</Button>}>
          <Group align="flex-end" wrap="nowrap">
            <TextInput
              style={{ flex: 1 }} label="Đường dẫn đầy đủ" leftSection={<IconFolder size={16} />} data-testid="review-dir"
              placeholder="vd /Users/ten/Pictures/Review hoặc D:\Review" value={dir} onChange={(e) => setDir(e.currentTarget.value)}
              description={saved ? `Đang lưu vào: ${saved}` : "Bắt buộc chọn trước khi lấy ảnh: bấm Chọn thư mục… hoặc dán đường dẫn rồi Lưu (chưa có thì tự tạo)."}
            />
            <Button variant="default" leftSection={<IconFolderOpen size={16} />} onClick={pickDir} loading={picking}>Chọn thư mục…</Button>
            <Button onClick={() => saveDir()} disabled={!dir.trim() || dir.trim() === saved}>Lưu</Button>
          </Group>
        </Step>

        <Step n={2} title="Link sản phẩm">
          <Textarea
            label="Mỗi dòng một link" autosize minRows={6} maxRows={14} data-testid="review-links"
            placeholder={"https://shopee.vn/...-i.123.456\nhttps://www.tiktok.com/view/product/..."}
            value={links} onChange={(e) => setLinks(e.currentTarget.value)}
            description={`${count} link Shopee / TikTok hợp lệ`}
          />
          <Group>
            <Button leftSection={<IconDownload size={16} />} onClick={fetchImages} disabled={!saved || !count}>Lấy ảnh</Button>
            {!saved && <Text size="sm" c="orange">Chọn thư mục lưu ở bước 1 trước.</Text>}
          </Group>
        </Step>
      </Stack>
    </>
  );
}
