"""Đổi Access Token của Page Graph API: User token (tự lấy Page token) hoặc Page token (Graph API giả lập)."""


def page_id(client):
    return client.get("/api/pages").get_json()["pages"][0]["id"]


def token_of(svc):
    return svc.store.load()["pages"][0]["token"]


def test_user_token_is_exchanged_for_page_token(connected, svc, graph):
    connected.post("/api/settings", json={"app_id": "APP", "app_secret": "SECRET"})
    r = connected.post(f"/api/pages/{page_id(connected)}/token", json={"token": "USER_SHORT"})
    assert r.status_code == 200 and r.get_json()["ok"] is True  # lưu xong tự kiểm tra kết nối
    assert token_of(svc) == "PAGE_TOKEN_1"  # Page token dài hạn của đúng Page 111
    assert graph.by("GET", "oauth/access_token")[0]["params"]["fb_exchange_token"] == "USER_SHORT"
    assert "Đã đổi Access Token" in svc.store.load()["log"][1]["text"]


def test_user_token_without_app_credentials_still_works(connected, svc, graph):
    connected.post(f"/api/pages/{page_id(connected)}/token", json={"token": "USER_SHORT"})
    assert token_of(svc) == "PAGE_TOKEN_1" and graph.by("GET", "oauth/access_token") == []


def test_user_token_not_managing_this_page(connected, svc, graph):
    old = token_of(svc)
    with svc.store.transaction() as data:
        data["pages"][0]["fb_page_id"] = "999"
    r = connected.post(f"/api/pages/{page_id(connected)}/token", json={"token": "USER"})
    assert r.status_code == 400 and "không quản lý Page 999" in r.get_json()["error"] and token_of(svc) == old


def test_page_token_used_directly_if_it_belongs_to_page(connected, svc, graph):
    graph.page_tokens = {"EAA_PAGE": "111", "EAA_OTHER": "222"}
    pid = page_id(connected)
    r = connected.post(f"/api/pages/{pid}/token", json={"token": "EAA_OTHER"})
    assert r.status_code == 400 and "không thuộc Page 111" in r.get_json()["error"]
    assert connected.post(f"/api/pages/{pid}/token", json={"token": " EAA_PAGE "}).status_code == 200
    assert token_of(svc) == "EAA_PAGE"


def test_token_required_and_api_pages_only(connected, client):
    assert connected.post(f"/api/pages/{page_id(connected)}/token", json={"token": " "}).status_code == 400
    from conftest import add_browser_page
    add_browser_page(client)
    browser = next(p["id"] for p in client.get("/api/pages").get_json()["pages"] if p["kind"] == "browser")
    assert client.post(f"/api/pages/{browser}/token", json={"token": "x"}).status_code == 400
