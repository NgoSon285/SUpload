import { useEffect, useState } from "react";
import { Button, Menu, Text } from "@mantine/core";
import { IconBooks, IconHash, IconSignature, IconTemplate } from "@tabler/icons-react";

import { libraryApi } from "../api/endpoints";

const ICON = { hashtag: IconHash, signature: IconSignature, template: IconTemplate };

/** Chèn đoạn nội dung dùng lại (hashtag, chữ ký, mẫu bài) vào văn bản. */
export function insertSnippet(text, item) {
  const base = (text || "").trimEnd();
  if (item.kind === "template" && !base) return item.content;
  return base ? `${base}\n\n${item.content}` : item.content;
}

export function SnippetMenu({ value, onChange, onOpenLibrary }) {
  const [data, setData] = useState({ items: [], kinds: {} });
  const load = () => libraryApi.list().then(setData, () => {});
  useEffect(() => { load(); }, []);
  const pick = (item) => { onChange(insertSnippet(value, item)); libraryApi.used(item.id).catch(() => {}); };
  return (
    <Menu position="bottom-start" withinPortal onOpen={load} width={320}>
      <Menu.Target><Button variant="subtle" size="compact-sm" leftSection={<IconBooks size={16} />}>Chèn từ thư viện</Button></Menu.Target>
      <Menu.Dropdown>
        {!data.items.length && <Menu.Item onClick={onOpenLibrary}><Text size="sm" c="dimmed">Thư viện trống: bấm để thêm hashtag, chữ ký, mẫu bài</Text></Menu.Item>}
        {Object.entries(data.kinds).map(([kind, label]) => {
          const list = data.items.filter((x) => x.kind === kind);
          if (!list.length) return null;
          const Icon = ICON[kind];
          return [
            <Menu.Label key={kind}>{label}</Menu.Label>,
            ...list.map((x) => (
              <Menu.Item key={x.id} leftSection={<Icon size={16} />} onClick={() => pick(x)}>
                <Text size="sm" truncate>{x.name}</Text>
                <Text size="xs" c="dimmed" truncate>{x.content}</Text>
              </Menu.Item>
            )),
          ];
        })}
      </Menu.Dropdown>
    </Menu>
  );
}
