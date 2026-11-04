# SUpload – Đăng bài tự động lên Facebook Page

Công cụ dòng lệnh Python đăng bài lên **Facebook Page** bằng **Graph API chính thức**:
không cần lưu mật khẩu, không giả lập trình duyệt, ít rủi ro bị khóa tài khoản.

Hỗ trợ: bài chữ, bài kèm link, 1 hoặc nhiều ảnh (URL hoặc file trên máy), hẹn giờ đăng, đăng hàng loạt từ file JSON.

> Vì sao không tự đăng nhập bằng username/password? Tự động hóa việc đăng nhập vi phạm
> điều khoản của Facebook, thường bị checkpoint/2FA chặn và dễ làm khóa tài khoản.
> Graph API là cách Facebook cho phép để quản lý Page tự động.

## 1. Cài đặt

```bash
pip install -r requirements.txt
cp .env.example .env
```

## 2. Lấy token (làm 1 lần)

1. Vào <https://developers.facebook.com/apps> → **Create App** (loại *Business*).
2. Copy **App ID** và **App Secret** (Settings → Basic) vào `.env`.
3. Mở **Graph API Explorer** (<https://developers.facebook.com/tools/explorer>), chọn App vừa tạo,
   bấm **Generate Access Token** và cấp các quyền:
   `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
4. Copy User Token đó rồi chạy:

```bash
python fb_poster.py token --user-token <USER_TOKEN>
```

Lệnh này in ra `FB_PAGE_ID` và `FB_PAGE_TOKEN` cho từng Page bạn quản lý. Dán vào `.env`.
Page token lấy từ user token dài hạn **không hết hạn** (trừ khi đổi mật khẩu hoặc gỡ quyền App).

> Giữ bí mật file `.env`: ai có `FB_PAGE_TOKEN` đều đăng được bài lên Page của bạn. File này đã nằm trong `.gitignore`.

## 3. Đăng bài

```bash
# Bài chữ
python fb_poster.py post -m "Xin chào!"

# Kèm link
python fb_poster.py post -m "Xem bài này" -l https://example.com

# Nhiều ảnh (URL hoặc file)
python fb_poster.py post -m "Album" -p ./a.jpg -p ./b.jpg

# Hẹn giờ (10 phút – 30 ngày tới, theo giờ máy)
python fb_poster.py post -m "Hẹn giờ" -s "2026-12-01 09:00"
```

## 4. Đăng hàng loạt

Tạo `posts.json` theo mẫu `posts.example.json`, rồi chạy:

```bash
python fb_poster.py batch posts.json --delay 120
```

Kết quả từng bài được ghi vào `post_log.jsonl`.

## 5. Chạy định kỳ (tùy chọn)

Linux/macOS (cron, mỗi ngày 8h):

```
0 8 * * * cd /path/SUpload && python fb_poster.py batch posts.json
```

Windows: dùng **Task Scheduler** để chạy cùng lệnh.
Hoặc đơn giản hơn: dùng tham số `schedule` trong JSON để Facebook tự đăng đúng giờ.

## 6. Cách 2: Đăng qua trình duyệt (Playwright)

Dùng khi bạn muốn thao tác trên giao diện web như người dùng thường.

```bash
pip install -r requirements.txt
playwright install chromium
```

**Đăng nhập 1 lần** (tự nhập tài khoản + 2FA trong cửa sổ mở ra; công cụ không lưu mật khẩu,
chỉ lưu phiên trong thư mục `fb_profile/`):

```bash
python browser_poster.py login
```

**Đăng bài** (công cụ tự chuyển sang vai trò Page nếu Facebook hỏi "Chuyển ngay"):

```bash
python browser_poster.py post --page https://www.facebook.com/TenPage -m "Xin chào" -p ./anh.jpg
python browser_poster.py batch posts.json --page https://www.facebook.com/TenPage
```

- `batch` mặc định chờ ngẫu nhiên 5–15 phút giữa các bài (`--min-delay`, `--max-delay`).
- Thêm `--headless` để chạy ẩn (nên chạy hiện cửa sổ vài lần đầu để theo dõi).
- Lỗi sẽ được chụp màn hình vào `screenshots/`, kết quả ghi ở `browser_post_log.jsonl`.
- Ảnh phải là file trên máy (không hỗ trợ URL); không hỗ trợ hẹn giờ – dùng cron/Task Scheduler.
- Giao diện Facebook thay đổi thường xuyên; nếu không tìm thấy nút, hãy sửa các biểu thức
  `RE_*` ở đầu `browser_poster.py` cho khớp với chữ trên nút.
- **Giữ bí mật thư mục `fb_profile/`**: nó chứa phiên đăng nhập của bạn.
- Thực tế, tự động hóa trình duyệt dễ bị Facebook nghi ngờ hơn Graph API (cách 1), vì API là kênh
  Facebook cấp chính thức cho chủ Page.

## Lưu ý

- Nếu App ở chế độ *Development*, chỉ admin/tester của App dùng được. Với Page của chính bạn thì vậy là đủ.
- Đừng spam: giãn cách giữa các bài (`--delay`) để tránh bị giới hạn tần suất.
