"""Thư viện nội dung & thư viện ảnh."""
import pytest

from conftest import upload


def items(client):
    return client.get("/api/library").get_json()["items"]


def test_crud_and_default_name(client):
    r = client.post("/api/library", json={"kind": "hashtag", "content": "#tiembanh #banhngon"}).get_json()["item"]
    assert r["name"] == "#tiembanh #banhngon"
    client.post("/api/library", json={"kind": "signature", "name": "Chữ ký", "content": "Hotline: 0900 000 000"})
    client.put(f"/api/library/{r['id']}", json={"name": "Hashtag chính"})
    assert {x["name"] for x in items(client)} == {"Hashtag chính", "Chữ ký"}
    client.delete(f"/api/library/{r['id']}")
    assert [x["kind"] for x in items(client)] == ["signature"]


@pytest.mark.parametrize("body", [{"kind": "zzz", "content": "x"}, {"kind": "hashtag", "content": "  "}, {"kind": "template", "content": "x" * 5001}])
def test_invalid_items(client, body):
    assert client.post("/api/library", json=body).status_code == 400


def test_most_used_first(client):
    a = client.post("/api/library", json={"kind": "hashtag", "name": "A", "content": "#a"}).get_json()["item"]
    b = client.post("/api/library", json={"kind": "hashtag", "name": "B", "content": "#b"}).get_json()["item"]
    client.post(f"/api/library/{b['id']}/used")
    assert [x["name"] for x in items(client)] == ["B", "A"]
    assert a


def test_media_list_with_usage_and_safe_delete(connected, svc):
    used = upload(connected, "dung.png")
    free = upload(connected, "khong-dung.png")
    connected.post("/api/posts", json={"message": "x", "photos": [used]})
    media = {m["name"]: m for m in connected.get("/api/media").get_json()["media"]}
    assert media[used]["used"] == 1 and media[free]["used"] == 0 and media[used]["kind"] == "image"
    r = connected.delete(f"/api/media/{used}")
    assert r.status_code == 400 and "đang được" in r.get_json()["error"]
    assert connected.delete(f"/api/media/{free}").status_code == 200
    assert not (svc.config.upload_dir / free).exists()


def test_media_delete_cannot_escape_uploads(connected, svc):
    (svc.config.base_dir / "secret.txt").write_text("x")
    assert connected.delete("/api/media/../secret.txt").status_code == 404
    assert (svc.config.base_dir / "secret.txt").exists()
