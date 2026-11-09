import { useEffect, useState } from "react";
import { Button, Group, Modal, Paper, Stack, Text, Textarea, UnstyledButton } from "@mantine/core";
import { IconSparkles } from "@tabler/icons-react";

import { aiApi, postsApi } from "../../api/endpoints";
import { notifyErr, notifyOk } from "../../components";

/** Page bình luận vào bài đã đăng: tự viết hoặc chọn câu AI gợi ý rồi sửa. */
export function CommentModal({ post, pageName, onClose, onDone }) {
  const [text, setText] = useState("");
  const [ideas, setIdeas] = useState([]);
  const [busy, setBusy] = useState("");
  useEffect(() => { setText(""); setIdeas([]); }, [post?.id]);

  const suggest = async () => {
    setBusy("ai");
    try {
      const kind = post.video ? "video" : post.photos?.length ? "ảnh" : "bài viết";
      const r = await aiApi.suggest({ action: "first_comment", text: post.message || `(Bài ${kind} không có chú thích)`, page: post.page });
      setIdeas(r.suggestions);
    } catch (e) { notifyErr(e.message); }
    setBusy("");
  };
  const send = async () => {
    setBusy("send");
    try { await postsApi.comment(post.id, text.trim()); notifyOk("Đã bình luận vào bài"); onDone(); onClose(); }
    catch (e) { notifyErr(e.message, "Chưa bình luận được"); }
    setBusy("");
  };

  return (
    <Modal opened={!!post} onClose={onClose} title={<Text fw={600}>Bình luận vào bài{pageName ? ` · ${pageName}` : ""}</Text>} centered radius="lg" size="lg">
      {post && (
        <Stack>
          <Text size="sm" c="dimmed" lineClamp={2}>{post.message || post.link || "Bài chỉ có ảnh / video"}</Text>
          <Textarea
            label="Nội dung bình luận (đăng bằng tên Page)" autosize minRows={3} maxRows={10} data-autofocus data-testid="comment-text"
            placeholder="vd Link sản phẩm ở đây nha: https://s.shopee.vn/..." value={text} onChange={(e) => setText(e.currentTarget.value)}
          />
          {ideas.length > 0 && (
            <Stack gap={6}>
              <Text size="xs" c="dimmed">Bấm một gợi ý để dùng (sửa thêm được):</Text>
              {ideas.map((s) => (
                <UnstyledButton key={s} onClick={() => setText(s)}>
                  <Paper withBorder p="xs" radius="md"><Text size="sm">{s}</Text></Paper>
                </UnstyledButton>
              ))}
            </Stack>
          )}
          <Group justify="space-between">
            <Button variant="light" leftSection={<IconSparkles size={16} />} onClick={suggest} loading={busy === "ai"}>AI gợi ý</Button>
            <Group gap="xs">
              <Button variant="default" onClick={onClose}>Huỷ</Button>
              <Button onClick={send} loading={busy === "send"} disabled={!text.trim()}>Bình luận</Button>
            </Group>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
