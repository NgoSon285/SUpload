# SUpload: Đăng bài tự động lên Facebook Page

Ứng dụng chạy trên máy tính của bạn, có giao diện web để **soạn bài, hẹn giờ, xếp lịch hàng loạt bằng Flow kéo thả**
và tự đăng lên **Facebook Page** mà bạn quản lý.

Có 2 cách đăng:

| | **Graph API** (khuyên dùng) | **Trình duyệt** |
|---|---|---|
| Cách hoạt động | Kênh chính thức Facebook cấp cho chủ Page | Tự thao tác trên facebook.com như người dùng |
| Độ ổn định | Cao | Có thể hỏng khi Facebook đổi giao diện |
| Cần chuẩn bị | Tạo một Facebook App (miễn phí, ~10 phút) | Đăng nhập Facebook một lần |
| Mật khẩu | Không cần | Không lưu, bạn tự đăng nhập trong cửa sổ trình duyệt |

---

## 1. Chuẩn bị

- **Python 3.10 trở lên**: tải tại <https://www.python.org/downloads/>.
  Trên Windows, khi cài nhớ tích **“Add python.exe to PATH”**.
- Tài khoản Facebook là **quản trị viên (admin) của Page** muốn đăng.
- *(Khuyên)* Tạo một **Page thử nghiệm** để chạy thử trước, vì bài đăng lên Page là công khai.
- Không cần Node.js: giao diện đã được build sẵn trong thư mục `web/`.

Kiểm tra Python đã cài:

```bash
python --version
```

> Trên macOS/Linux nếu lệnh trên không chạy, dùng `python3` thay cho `python` trong toàn bộ hướng dẫn.
> Trên Windows có thể dùng `py`.

## 2. Tải mã nguồn

Cách 1, dùng git:

```bash
git clone https://github.com/NgoSon285/SUpload.git
cd SUpload
```

Cách 2, không dùng git: vào trang GitHub của dự án → **Code → Download ZIP**, giải nén rồi mở cửa sổ dòng lệnh
(Terminal / Command Prompt) trong thư mục vừa giải nén.

## 3. Cài đặt (làm 1 lần)

Tạo môi trường ảo để không ảnh hưởng tới Python của máy:

**Windows (Command Prompt / PowerShell)**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Nếu định dùng cách đăng **Trình duyệt**, cài thêm Chromium cho Playwright (~150 MB):

```bash
playwright install chromium
```

## 4. Chạy ứng dụng

```bash
python app.py
```

Trình duyệt sẽ tự mở <http://127.0.0.1:5000>. Nếu không tự mở, bạn copy địa chỉ đó dán vào trình duyệt.

- **Windows**: lần sau chỉ cần bấm đúp `start.bat` (tự dùng môi trường ảo `.venv` nếu có).
- **macOS / Linux**: lần sau chạy `source .venv/bin/activate` rồi `python app.py`.
- **Giữ cửa sổ dòng lệnh mở** trong suốt thời gian muốn đăng bài. Bài hẹn giờ chỉ được đăng khi ứng dụng đang chạy.
  Tắt ứng dụng thì các bài chưa tới giờ vẫn được giữ nguyên và sẽ đăng khi bạn mở lại.
- Dừng ứng dụng: nhấn `Ctrl + C` trong cửa sổ dòng lệnh.

## 5. Kết nối Page

Lần đầu mở, ứng dụng tự chuyển tới trang **Cài đặt**.

### Cách A: Graph API (khuyên dùng)

**Bước 1: Tạo Facebook App**

1. Vào <https://developers.facebook.com/apps>, đăng nhập bằng tài khoản quản trị Page.
   Nếu được hỏi, đăng ký làm nhà phát triển (miễn phí).
2. Bấm **Create App / Tạo ứng dụng**. Khi được hỏi trường hợp sử dụng, chọn **Other / Khác**, sau đó loại ứng dụng **Business**.
   (Giao diện của Facebook có thể đổi tên nút theo thời gian; mục tiêu là có một App loại Business.)
3. Vào **App settings → Basic**, chép **App ID** và **App Secret** (bấm *Show*).

> Để App ở chế độ **Development** là đủ: bạn là admin của App nên dùng được với Page của chính bạn,
> không cần gửi Facebook duyệt.

**Bước 2: Lấy User Token**

1. Mở **Graph API Explorer**: <https://developers.facebook.com/tools/explorer>.
2. Ở ô **Meta App**, chọn App vừa tạo. Ở ô **User or Page**, chọn **User Token**.
3. Ở **Permissions**, thêm 3 quyền: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`.
4. Bấm **Generate Access Token**, đăng nhập và **chọn Page muốn đăng** trong hộp thoại cấp quyền.
5. Chép chuỗi token vừa tạo.

**Bước 3: Kết nối trong SUpload**

1. Trang **Cài đặt** → chọn **Graph API**.
2. Dán **App ID**, **App Secret**, **User Access Token**.
3. Bấm **Lấy danh sách Page** → bấm chọn Page của bạn.
4. Bấm **Kiểm tra kết nối**: thấy “Kết nối tốt tới Page …” là xong.

Ứng dụng tự đổi sang **Page Token dài hạn** (thường không hết hạn, trừ khi bạn đổi mật khẩu Facebook
hoặc gỡ quyền của App). User Token bạn dán vào không được lưu lại.

### Cách B: Trình duyệt

1. Trang **Cài đặt** → chọn **Trình duyệt**.
2. Nhập địa chỉ Page, ví dụ `https://www.facebook.com/TenPageCuaBan`, rồi bấm **Lưu cài đặt**.
3. Bấm **Mở trình duyệt để đăng nhập**. Một cửa sổ Chromium mở ra, bạn tự đăng nhập Facebook (kể cả mã 2FA).
   Ứng dụng tự nhận biết khi đăng nhập xong và đóng cửa sổ.
4. Chọn **giãn cách** giữa 2 bài (mặc định 5 phút). Để tắt “Chạy ẩn trình duyệt” trong vài lần đầu để quan sát.

> Nếu đăng lỗi, ảnh chụp màn hình lúc lỗi nằm trong thư mục `screenshots/`. Nếu Facebook đổi chữ trên nút,
> sửa các biểu thức `RE_*` ở đầu file `browser_poster.py`.

## 6. Đăng bài đầu tiên

1. Trang **Soạn bài** → viết nội dung, kéo thả ảnh (hoặc dán bằng `Ctrl + V`), thêm link nếu muốn.
2. Chọn **Đăng ngay** hoặc **Hẹn giờ** (có sẵn các mốc: Sau 1 giờ, 20:00 tối nay, 8:00 sáng mai…).
3. Bấm **Đăng ngay / Lên lịch** (hoặc `Ctrl + Enter`).
4. Xem trạng thái ở trang **Lịch đăng**: *Đang chờ → Đang đăng → Đã đăng* hoặc *Lỗi* (kèm lý do, có nút **Đăng lại**).
5. Mở Page trên Facebook để kiểm tra bài.

## 7. Lên lịch hàng loạt bằng Flow

Trang **Flow chiến dịch** thay cho việc soạn từng bài: kéo thả các khối và nối chúng lại.

| Nhóm | Khối | Dùng để |
|---|---|---|
| Khởi đầu | **Bắt đầu** | Chạy ngay khi bấm *Chạy flow*, hoặc từ một thời điểm cụ thể. |
| Nội dung | **Bài viết** | Một bài. Bật *Nhiều phiên bản* (cách nhau bằng dòng `---`) để mỗi lần chọn ngẫu nhiên 1 bản. |
| | **Nhiều bài** | Dán nhiều bài (tách theo dòng trống / dòng `---` / mỗi dòng), thả nhiều ảnh, chọn khoảng cách giữa các bài, xáo trộn, giới hạn số bài. |
| | **Định dạng** | Thêm phần đầu/cuối (hashtag, chữ ký, hotline) cho mọi bài phía sau. |
| Thời gian | **Chờ** | Chờ cố định, ngẫu nhiên trong khoảng, tới giờ cố định hằng ngày, hoặc tới thứ trong tuần. |
| | **Khung giờ** | Chỉ đăng vào ngày/giờ cho phép (vd T2–T6, 08:00–21:00); bài ngoài khung tự lùi sang khung kế. |
| | **Lặp lại** | Chạy các khối phía sau N lần, mỗi lần cách nhau X. |

Cách dùng:

1. Kéo khối từ cột trái vào bảng vẽ, hoặc **bấm** vào khối để thêm nối tiếp khối đang chọn.
2. Nối khối: kéo từ chấm dưới khối này sang khối khác. Xoá: chọn khối/đường nối rồi nhấn `Delete`.
3. Bấm vào khối để cấu hình ở cột phải. Mục **Tuỳ chỉnh khối** cho phép đặt tên, ghi chú hoặc **tắt khối**.
4. Xem thẻ **Lịch dự kiến** để biết chính xác bài nào đăng lúc nào. Khối viền cam là khối cần kiểm tra.
5. Bấm **Chạy flow**: toàn bộ bài được đưa vào **Lịch đăng**, ở đó bạn vẫn sửa/xoá từng bài được.

Mẹo:
- Viết `{Chào|Xin chào} {bạn|mọi người}` để chọn ngẫu nhiên một phương án.
- Lựa chọn ngẫu nhiên được cố định theo flow, nên **Lịch dự kiến chính là lịch sẽ chạy**. Bấm nút 🎲 để xáo lại.
- Bài nối ngay sau bài khác mà không có khối **Chờ** ở giữa sẽ đăng cùng lúc; hãy chèn khối Chờ để giãn ra.
- Flow tự lưu, chọn lại ở ô danh sách flow phía trên.

## 8. Dữ liệu được lưu ở đâu

| File / thư mục | Nội dung |
|---|---|
| `data.json` | Cài đặt, **token**, lịch đăng, flow, nhật ký |
| `uploads/` | Ảnh bạn đã tải lên |
| `fb_profile/` | Phiên đăng nhập Facebook (chỉ khi dùng cách Trình duyệt) |
| `screenshots/` | Ảnh chụp khi đăng lỗi (cách Trình duyệt) |

- Sao lưu: copy `data.json` và `uploads/`.
- **Không chia sẻ** `data.json` và `fb_profile/`: ai có chúng là đăng được lên Page của bạn.
  Các file này đã nằm trong `.gitignore`.
- Ứng dụng chỉ mở ở `127.0.0.1`, máy khác trong mạng không truy cập được.

## 9. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `python` không được nhận diện | Cài lại Python, tích “Add to PATH”; hoặc dùng `py` (Windows) / `python3` (macOS, Linux). |
| `Address already in use` / cổng 5000 bận | Chạy ở cổng khác: Windows `set PORT=5050` rồi `python app.py`; macOS/Linux `PORT=5050 python app.py`. |
| Trang trắng, báo “Chưa có giao diện” | Thư mục `web/` bị thiếu: tải lại mã nguồn, hoặc build lại (mục 11). |
| Lỗi `[190] ...` | Token hết hạn/không hợp lệ: lấy User Token mới ở Graph API Explorer và làm lại **Bước 3**. |
| Lỗi `[200] ...` hoặc `[10] ...` | Thiếu quyền: tạo lại token với đủ 3 quyền và nhớ **chọn đúng Page** khi cấp quyền. |
| Lỗi `[368] ...` | Facebook tạm chặn vì đăng quá dày/nội dung giống spam: giãn lịch đăng, đa dạng nội dung. |
| “Không có Page nào” khi lấy danh sách | Tài khoản chưa là admin của Page, hoặc khi cấp quyền chưa chọn Page đó. |
| Bài hẹn giờ không được đăng | Ứng dụng phải đang chạy lúc tới giờ; kiểm tra giờ của máy tính có đúng không. |
| Bài bị đánh dấu Lỗi “Ứng dụng bị tắt khi đang đăng” | Kiểm tra Page xem bài đã lên chưa rồi mới bấm **Đăng lại** để tránh trùng. |
| Cách Trình duyệt: `chưa cài playwright` | Chạy `pip install -r requirements.txt` rồi `playwright install chromium`. |
| Cách Trình duyệt: không tìm thấy nút | Xem ảnh trong `screenshots/`; tắt chạy ẩn để quan sát; sửa `RE_*` trong `browser_poster.py`. |

Mọi hoạt động và lỗi đều được ghi ở trang **Nhật ký**.

## 10. Chạy kiểm thử (tuỳ chọn)

```bash
pip install -r requirements-dev.txt
python -m pytest
```

- `tests/test_fb_poster.py`, `tests/test_app.py`: API, luồng đăng nền, bảo mật token (Facebook được giả lập, **không đăng bài thật**).
- `tests/test_e2e.py`: mở giao diện thật bằng trình duyệt tự động (cần `playwright install chromium`; tự bỏ qua nếu chưa cài).

Kiểm thử bộ tính lịch của Flow (cần Node.js 18+):

```bash
cd frontend
npm install
npm test
```

## 11. Sửa giao diện (dành cho lập trình viên)

Mã nguồn giao diện nằm trong `frontend/` (Vite + React 18, Mantine, React Flow, Tabler Icons). Cần Node.js 18+.

```bash
python app.py                 # cửa sổ 1: chạy API ở cổng 5000
cd frontend && npm install    # cửa sổ 2
npm run dev                   # http://localhost:5173, tự tải lại khi sửa code
npm run build                 # build ra ../web để python app.py phục vụ
```

Thêm loại khối Flow mới: khai báo trong `frontend/src/lib/nodes.jsx` (trường cấu hình, mặc định, cách tính lịch);
bảng Thuộc tính tự sinh giao diện từ khai báo đó.

## 12. Dùng bằng dòng lệnh (không cần giao diện)

Tạo `.env` từ mẫu `.env.example` và điền `FB_APP_ID`, `FB_APP_SECRET`, rồi:

```bash
python fb_poster.py token --user-token <USER_TOKEN>   # in ra FB_PAGE_ID / FB_PAGE_TOKEN để dán vào .env
python fb_poster.py post -m "Xin chào" -p ./anh.jpg
python fb_poster.py post -m "Hẹn giờ" -s "2026-12-01 09:00"   # Facebook tự đăng (10 phút – 30 ngày)
python fb_poster.py batch posts.json --delay 120              # mẫu: posts.example.json
```

Cách Trình duyệt bằng dòng lệnh:

```bash
python browser_poster.py login
python browser_poster.py post --page https://www.facebook.com/TenPage -m "Xin chào" -p ./anh.jpg
```

Giá trị trong `.env` (`FB_PAGE_ID`, `FB_PAGE_TOKEN`…) cũng được giao diện dùng làm mặc định khi chưa cấu hình.

## Cấu trúc thư mục

```
app.py              Máy chủ giao diện + luồng đăng bài nền
fb_poster.py        Đăng qua Graph API (dùng được độc lập bằng dòng lệnh)
browser_poster.py   Đăng qua trình duyệt (Playwright)
web/                Giao diện đã build (không sửa trực tiếp)
frontend/           Mã nguồn giao diện React
tests/              Kiểm thử Python (pytest)
start.bat           Mở nhanh trên Windows
```

## Lưu ý

- Chỉ dùng cho Page bạn quản lý và tuân thủ [Điều khoản của Facebook](https://www.facebook.com/terms).
- Đăng quá dày hoặc nội dung lặp lại có thể bị Facebook giới hạn: dùng khối **Khung giờ**, **Chờ ngẫu nhiên**
  và nhiều phiên bản nội dung để lịch đăng tự nhiên hơn.
