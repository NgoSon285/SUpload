# SUpload – Đăng bài tự động lên Facebook Page

Công cụ dòng lệnh Python đăng bài lên **Facebook Page** bằng **Graph API chính thức**:
không cần lưu mật khẩu, không giả lập trình duyệt, ít rủi ro bị khóa tài khoản.

Hỗ trợ: bài chữ, bài kèm link, 1 hoặc nhiều ảnh (URL hoặc file trên máy), hẹn giờ đăng, đăng hàng loạt từ file JSON.

> Vì sao không tự đăng nhập bằng username/password? Tự động hóa việc đăng nhập vi phạm
> điều khoản của Facebook, thường bị checkpoint/2FA chặn và dễ làm khóa tài khoản.
> Graph API là cách Facebook cho phép để quản lý Page tự động.

## 0. Giao diện trực quan (khuyên dùng)

```bash
pip install -r requirements.txt
python app.py
```

Trên Windows có thể bấm đúp `start.bat`. Trình duyệt sẽ tự mở <http://127.0.0.1:5000>. Giao diện đã được build sẵn
trong thư mục `web/`, **không cần cài Node.js** để dùng.

| Trang | Chức năng |
|---|---|
| **Soạn bài** | Soạn nội dung, kéo thả / dán ảnh (kéo để đổi thứ tự), thêm link, xem trước, đăng ngay hoặc hẹn giờ với các mốc nhanh (Sau 1 giờ, 20:00 tối nay…). `Ctrl+Enter` để đăng. |
| **Lịch đăng** | Bài gom theo ngày, trạng thái Đang chờ / Đang đăng / Đã đăng / Lỗi; sửa, dùng lại nội dung, đăng lại, xoá. |
| **Flow chiến dịch** | Thay cho việc viết file JSON: kéo thả các khối **Bắt đầu → Bài viết → Chờ → Nhiều bài** trên bảng vẽ, xem ngay giờ đăng dự kiến của từng bài, rồi bấm **Chạy flow** để đưa tất cả vào Lịch đăng. Flow được tự lưu để dùng lại. |
| **Nhật ký** | Lịch sử hoạt động. |
| **Cài đặt** | Chọn cách đăng (Graph API hoặc Trình duyệt), lấy danh sách Page từ User Token, kiểm tra kết nối, đăng nhập trình duyệt. |

**Các khối trong Flow** (bảng Thuộc tính bên phải cho phép cấu hình từng khối)

| Nhóm | Khối | Cấu hình |
|---|---|---|
| Khởi đầu | **Bắt đầu** | Chạy ngay khi bấm *Chạy flow* hoặc từ một thời điểm cụ thể. |
| Nội dung | **Bài viết** | Nội dung, ảnh, link. Bật *Nhiều phiên bản* (cách nhau bởi dòng `---`) để chọn ngẫu nhiên 1 bản. |
| | **Nhiều bài** | Dán nhiều bài, tách theo dòng trống / dòng `---` / mỗi dòng; thả nhiều ảnh, chọn số ảnh mỗi bài; khoảng cách giữa các bài; theo thứ tự hoặc xáo trộn; giới hạn số bài. |
| | **Định dạng** | Thêm phần đầu / cuối (hashtag, chữ ký, hotline) cho mọi bài phía sau. |
| Thời gian | **Chờ** | Cố định (X phút/giờ/ngày), ngẫu nhiên trong khoảng, đợi tới giờ cố định hằng ngày, hoặc đợi tới thứ trong tuần. |
| | **Khung giờ** | Chỉ đăng vào ngày và giờ cho phép (vd T2–T6, 08:00–21:00); bài rơi ngoài khung tự lùi sang đầu khung kế tiếp. |
| | **Lặp lại** | Chạy các khối phía sau N lần, mỗi lần cách nhau X. |

- Mọi khối đều có **Tuỳ chỉnh khối**: tên hiển thị, ghi chú, và **tắt khối** (bỏ qua nhưng vẫn chạy các khối phía sau).
  Thanh công cụ nhanh (tắt / nhân bản / xoá) hiện phía trên khối đang chọn.
- Viết `{Chào|Xin chào} {bạn|mọi người}` trong nội dung để chọn ngẫu nhiên một phương án.
- Lựa chọn ngẫu nhiên được cố định theo flow: **Lịch dự kiến chính là lịch sẽ chạy**. Bấm nút xúc xắc để xáo lại.
- Một khối có thể rẽ nhiều nhánh; mỗi nhánh tự tính giờ từ điểm rẽ. Khối thiếu cấu hình hoặc chưa nối sẽ có viền cam.
- Thêm loại khối mới: chỉ cần khai báo trong `frontend/src/lib/nodes.jsx` (trường cấu hình, mặc định, cách tính lịch);
  bảng Thuộc tính tự sinh giao diện từ khai báo đó.

Lưu ý:
- Bài hẹn giờ do ứng dụng tự đăng khi tới giờ, nên **phải để ứng dụng chạy** (không tắt cửa sổ dòng lệnh).
- Ứng dụng chỉ nghe ở `127.0.0.1` (chỉ máy bạn truy cập được). Cài đặt, token, flow và hàng đợi lưu trong `data.json`,
  ảnh lưu trong `uploads/`. Đừng chia sẻ các file này.
- Chế độ Trình duyệt cần thêm: `playwright install chromium`.

### Phát triển giao diện (tuỳ chọn)

Mã nguồn giao diện nằm trong `frontend/` (Vite + React 18, [Mantine](https://mantine.dev) cho component,
[React Flow](https://reactflow.dev) cho trình dựng flow, Tabler Icons).

```bash
python app.py                      # chạy API ở cổng 5000
cd frontend && npm install
npm run dev                        # http://localhost:5173, tự tải lại khi sửa code
npm run build                      # build ra ../web cho Flask phục vụ
```

Các mục dưới đây là cách dùng bằng dòng lệnh.

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
