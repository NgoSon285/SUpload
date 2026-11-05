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
- **Khi nào phải để ứng dụng chạy?**
  - Cách **Graph API** + bật *Hẹn giờ trên Facebook* (mặc định): bài hẹn từ 12 phút tới 30 ngày được gửi lên Facebook
    ngay, **Facebook tự đăng kể cả khi bạn tắt máy**. Chỉ cần mở ứng dụng lúc tạo/sửa lịch (và thỉnh thoảng để
    ứng dụng đối soát trạng thái *Đã đăng*).
  - Bài *Đăng ngay*, bài còn dưới 12 phút, bài xa hơn 30 ngày, hoặc cách **Trình duyệt**: ứng dụng tự đăng khi tới giờ,
    nên cần đang chạy lúc đó. Tắt ứng dụng thì bài chưa tới giờ vẫn được giữ và đăng khi bạn mở lại.
- Dừng ứng dụng: nhấn `Ctrl + C` trong cửa sổ dòng lệnh.

## 5. Kết nối Page

Lần đầu mở, ứng dụng tự chuyển tới trang **Cài đặt**. Bạn kết nối được **nhiều Page** (mục *Thêm Page*), mỗi Page
đăng theo cách riêng (Graph API hoặc Trình duyệt). Page đầu tiên là **Page mặc định**: bài và flow không chọn Page
riêng sẽ đăng lên Page này.

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
3. Ở **Permissions**, thêm 3 quyền: `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`
   (thêm `read_insights` nếu muốn xem lượt tiếp cận trong trang Thống kê).
4. Bấm **Generate Access Token**, đăng nhập và **chọn mọi Page muốn quản lý** trong hộp thoại cấp quyền.
5. Chép chuỗi token vừa tạo.

**Bước 3: Kết nối trong SUpload**

1. Trang **Cài đặt → Thêm Page → Qua Graph API**.
2. Dán **App ID**, **App Secret**, **User Access Token**.
3. Bấm **Lấy danh sách Page** → bấm **Thêm** ở từng Page muốn dùng.
4. Ở mục *Page đã kết nối*, bấm **Kiểm tra** trên từng Page: thấy “Kết nối tốt tới Page …” là xong.

Ứng dụng tự đổi sang **Page Token dài hạn** (thường không hết hạn, trừ khi bạn đổi mật khẩu Facebook
hoặc gỡ quyền của App). User Token bạn dán vào không được lưu lại.

### Cách B: Trình duyệt

1. Trang **Cài đặt → Thêm Page → Qua trình duyệt**.
2. Bấm **Mở trình duyệt để đăng nhập**. Một cửa sổ Chromium mở ra, bạn tự đăng nhập Facebook (kể cả mã 2FA).
   Ứng dụng tự nhận biết khi đăng nhập xong và đóng cửa sổ. Mọi Page cách này dùng chung lần đăng nhập đó.
3. Nhập địa chỉ Page, ví dụ `https://www.facebook.com/TenPageCuaBan`, rồi bấm **Thêm Page**. Lặp lại cho Page khác.
4. Để tắt “Chạy ẩn trình duyệt” (mục *Cách đăng*) trong vài lần đầu để quan sát.

### Quản lý các Page

Mục **Page đã kết nối** liệt kê mọi Page kèm số bài đã đăng hôm nay. Nút **Kiểm tra** thử kết nối; menu **⋯** để
*Đặt làm mặc định*, *Đổi tên hiển thị* hoặc *Xoá Page* (chỉ xoá được khi Page không còn bài chưa đăng).
Khi có từ 2 Page trở lên:
- **Soạn bài** có ô *Đăng lên Page*; **Flow** có ô chọn Page đích ở thanh trên cùng của trình dựng.
- **Lịch đăng** ghi tên Page trên từng bài và lọc được theo Page.
- **Giới hạn an toàn tính riêng cho từng Page** (Facebook giới hạn theo từng Page).

**Kiểm tra kết nối tự động:** ứng dụng thử kết nối từng Page qua API mỗi 6 giờ, và cập nhật ngay mỗi lần đăng
thành công/thất bại. Nếu một Page mất kết nối (token hết hạn, thiếu quyền, bị Facebook chặn tạm…), mọi trang hiện
**dải cảnh báo đỏ** kèm cách xử lý, và mục *Page đã kết nối* ghi rõ lỗi. Sửa xong (vd thêm lại Page với token mới)
thì bấm **Kiểm tra** để xác nhận. Page qua trình duyệt chỉ được kiểm tra khi bạn bấm (vì phải mở trình duyệt).

> Nâng cấp từ bản cũ (một Page): Page đang kết nối tự trở thành Page đầu tiên và là Page mặc định; bài đang chờ
> được gán vào Page đó. Bạn không cần làm gì.

> Nếu đăng lỗi, ảnh chụp màn hình lúc lỗi nằm trong thư mục `screenshots/`. Nếu Facebook đổi chữ trên nút,
> sửa các biểu thức `RE_*` ở đầu file `supload/integrations/browser.py`.

### Giới hạn an toàn (cả hai cách, tính riêng từng Page)

Trang **Cài đặt → Giới hạn an toàn** giúp Page không bị Facebook hạn chế vì đăng quá dày:

| Tuỳ chọn | Mặc định | Ý nghĩa |
|---|---|---|
| Số bài tối đa mỗi ngày | 20 | Tính cả bài đã đăng và bài đã hẹn trên Facebook trong ngày. `0` = không giới hạn |
| Giãn cách tối thiểu giữa 2 bài | 5 phút | Áp cho mọi bài, kể cả bài hẹn trên Facebook |

Bài vượt giới hạn **không bị bỏ**, mà được tự dời sang thời điểm hợp lệ kế tiếp (giãn cách → lùi vài phút;
đủ bài trong ngày → sang ngày hôm sau cùng giờ). Lịch đăng ghi rõ *“Dời sang … vì …”*; khi soạn bài hoặc chạy flow,
ứng dụng báo trước nếu có bài bị dời.

## 6. Đăng bài đầu tiên

1. Trang **Soạn bài** → viết nội dung, kéo thả ảnh (hoặc dán bằng `Ctrl + V`), thêm link nếu muốn.
2. Chọn **Đăng ngay** hoặc **Hẹn giờ** (có sẵn các mốc: Sau 1 giờ, 20:00 tối nay, 8:00 sáng mai…).
3. Bấm **Đăng ngay / Lên lịch** (hoặc `Ctrl + Enter`).
4. Xem trạng thái ở trang **Lịch đăng**:
   - *Đang chờ → Đang đăng → Đã đăng*, hoặc *Lỗi* (kèm lý do, có nút **Đăng lại**).
   - *Đang chờ → **Đã hẹn trên Facebook** → Đã đăng*: bài hẹn giờ đã được giao cho Facebook. Ứng dụng tự hỏi lại
     Facebook sau giờ hẹn để chuyển sang *Đã đăng* (hoặc báo *Lỗi* nếu quá 1 giờ mà Facebook chưa đăng).
   - **Sửa / Xoá** bài *Đã hẹn trên Facebook* sẽ **huỷ bài hẹn trên Facebook** trước. Nếu không huỷ được (mất mạng…),
     ứng dụng không xoá để tránh đăng trùng và hỏi bạn có muốn tự xoá trên Facebook không.
5. Mở Page trên Facebook để kiểm tra bài (bài hẹn giờ nằm trong mục *Bài viết đã lên lịch* của Page).

**Video & Reels:** ở ô *Ảnh* chọn **Video** hoặc **Reels**, kéo thả một file MP4/MOV/WEBM (tối đa 1 GB).
Reels cần video dọc 9:16, dài 3–90 giây. Cả hai hẹn giờ trên Facebook được như bài thường. Một bài chỉ có ảnh *hoặc* video.
Reels chỉ đăng qua Graph API (chưa hỗ trợ cách Trình duyệt).

**Xem dạng Lịch:** ở trang **Lịch đăng**, chuyển *Danh sách → Lịch* để xem theo **Tháng** hoặc **Tuần**.
- **Kéo một bài sang ngày khác** để dời lịch (giữ nguyên giờ). Bài *Đã hẹn trên Facebook* được huỷ và hẹn lại tự động.
  Không kéo được về ngày đã qua.
- Bấm **+** (hoặc nhấp đúp) vào một ô ngày để soạn bài cho ngày đó; bấm vào bài để sửa.
- Màu theo trạng thái: xanh tím = đang chờ, xanh lơ = đã hẹn trên Facebook, xanh lá = đã đăng, đỏ = lỗi.

## 7. Nhập bài hàng loạt từ Excel / CSV

Trang **Lịch đăng → Nhập từ file**:

1. Tải **File mẫu Excel** (hoặc CSV), mỗi dòng là một bài:

   | Cột | Bắt buộc | Ghi chú |
   |---|---|---|
   | Nội dung | ✔ | Có thể viết nhiều đoạn trong một ô (Alt+Enter trong Excel) |
   | Link | | `https://…` |
   | Ảnh | | Link ảnh `https://…` (ứng dụng tự tải về) hoặc tên ảnh đã có trong thư viện; nhiều ảnh cách nhau bởi dấu phẩy |
   | Thời gian | | `01/12/2026 20:00` (hoặc `2026-12-01 20:00`, hoặc ô ngày giờ của Excel). Để trống = đăng ngay; chỉ có ngày = 9:00 sáng |
   | Page | | Tên Page (hoặc Page ID). Để trống = Page mặc định |

   Tên cột viết có dấu hay không dấu, tiếng Việt hay tiếng Anh đều được (`noi dung`, `message`…). CSV dùng dấu phẩy hoặc chấm phẩy.
2. Kéo thả file vào hộp thoại → xem trước từng dòng; dòng lỗi tô đỏ kèm lý do (sai thời gian, Page không tồn tại…).
3. Bấm **Nhập N bài**. Có dòng lỗi thì sửa file rồi chọn lại, hoặc **Nhập các dòng hợp lệ, bỏ qua dòng lỗi**.

Bài nhập vào vẫn tuân theo **giới hạn an toàn** của từng Page. Tối đa 500 bài mỗi lần.

### Thư viện nội dung

Trang **Thư viện** lưu những thứ dùng lại nhiều lần:
- **Đoạn nội dung**: *Bộ hashtag*, *Chữ ký* (địa chỉ, hotline…), *Mẫu bài*. Khi soạn bài bấm **Chèn từ thư viện**:
  hashtag/chữ ký được thêm vào cuối bài; mẫu bài điền vào khung trống. Mục hay dùng hiện lên đầu.
- **Ảnh & video**: mọi file đã tải lên, kèm số bài/flow đang dùng. Xoá được file không còn dùng.
  Khi soạn bài, bấm **Chọn ảnh đã tải** để dùng lại ảnh cũ thay vì tải lên lần nữa.

## 8. Lên lịch hàng loạt bằng Flow

Trang **Flow chiến dịch** thay cho việc soạn từng bài: kéo thả các khối và nối chúng lại.
Bạn tạo được **nhiều flow**, mỗi flow là một kịch bản dùng lại được (vd “Khuyến mãi cuối tuần”, “Tuyển dụng”).

### Quản lý flow

Mở trang **Flow chiến dịch** sẽ thấy danh sách flow dạng thẻ. Mỗi thẻ cho biết số khối, số bài dự kiến,
số bài đang chờ / đã đăng / lỗi, lần sửa và lần chạy gần nhất.

| Việc cần làm | Cách làm |
|---|---|
| Tạo flow | **Tạo flow** → đặt tên, mô tả → chọn *Flow trống* hoặc *Mẫu chiến dịch* → **Tạo và mở** |
| Sửa nội dung flow | Bấm **Mở** trên thẻ (tự lưu khi sửa, nút **← Tất cả flow** để quay lại) |
| Đổi tên / mô tả | Menu **⋯** trên thẻ → *Đổi tên & mô tả* (hoặc menu **Flow** trong trình dựng) |
| Nhân bản | Menu **⋯** → *Nhân bản*: tạo bản sao để biến tấu mà không ảnh hưởng bản gốc |
| Xoá | Menu **⋯** → *Xoá*. Nếu flow còn bài chưa đăng trong Lịch đăng, bạn chọn được có xoá luôn các bài đó không |
| Sao lưu / chia sẻ | Menu **⋯** → *Xuất file* (`.supload-flow.json`); **Nhập file** để thêm lại |
| Tìm nhanh | Ô tìm theo tên/mô tả; sắp xếp *Mới sửa*, *Tên A–Z*, *Mới chạy* |

> File xuất chỉ chứa tên ảnh, không chứa ảnh. Nhập trên máy khác thì cần copy cả thư mục `uploads/`.

### Dựng flow

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

### Thống kê tương tác

Trang **Thống kê** cho biết các bài đăng qua **Graph API** đang được tương tác thế nào (bài qua Trình duyệt không có số liệu):
- Ứng dụng tự lấy **cảm xúc, bình luận, chia sẻ, tiếp cận** của bài khoảng 10 phút sau khi đăng, rồi cập nhật mỗi 6 giờ trong 14 ngày.
  Bấm **Cập nhật số liệu** để lấy lại ngay.
- **Giờ hiệu quả nhất**: khung giờ có từ 2 bài trở lên và tương tác trung bình cao hơn mức chung. Dùng nó để đặt khối
  **Khung giờ** trong Flow.
- Biểu đồ theo giờ và theo thứ (rê chuột để xem số liệu, hoặc bật *Xem dạng bảng số liệu*), danh sách bài nổi bật.
- **Lượt tiếp cận** cần thêm quyền `read_insights` khi tạo User Token; thiếu quyền này các số liệu khác vẫn hiện đủ.

## 9. Dữ liệu được lưu ở đâu

| File / thư mục | Nội dung |
|---|---|
| `data.json` | Cài đặt, **token**, lịch đăng, flow, nhật ký |
| `uploads/` | Ảnh bạn đã tải lên |
| `backups/` | Bản sao lưu tự động của `data.json` (giữ 14 bản gần nhất) |
| `fb_profile/` | Phiên đăng nhập Facebook (chỉ khi dùng cách Trình duyệt) |
| `screenshots/` | Ảnh chụp khi đăng lỗi (cách Trình duyệt) |

Mặc định các thư mục này nằm cạnh `app.py`. Muốn để chỗ khác (ổ khác, thư mục đồng bộ…), đặt biến môi trường
`SUPLOAD_HOME` trước khi chạy, ví dụ Windows `set SUPLOAD_HOME=D:\SUploadData`, macOS/Linux `export SUPLOAD_HOME=~/SUploadData`.

**Sao lưu & dọn dẹp tự động** (mỗi ngày một lần khi ứng dụng chạy; hoặc bấm *Sao lưu & dọn dẹp ngay* trong
**Cài đặt → Dữ liệu & sao lưu**):
- Sao lưu `data.json` vào `backups/data-NămThángNgày-GiờPhútGiây.json` (trước khi dọn).
- Xoá khỏi danh sách các bài **đã đăng** quá 90 ngày (đổi được: 30 ngày, 1 năm, hoặc giữ mãi). Bài lỗi/đang chờ không bị đụng tới.
- Xoá ảnh trong `uploads/` không còn bài hay flow nào dùng, sau 7 ngày (để không xoá nhầm ảnh trong bản nháp).

**Khôi phục từ bản sao lưu:** tắt ứng dụng, chép file mong muốn trong `backups/` đè lên `data.json`, rồi mở lại.

**Chỉ chạy được một ứng dụng mỗi lúc** trên cùng thư mục dữ liệu: nếu lỡ chạy `python app.py` lần hai, nó sẽ báo
“đã chạy ở cửa sổ khác” và mở lại giao diện đang chạy, thay vì chạy song song (hai phiên cùng chạy sẽ đăng trùng bài).

- **Không chia sẻ** `data.json`, `backups/` và `fb_profile/`: ai có chúng là đăng được lên Page của bạn.
  Các thư mục này đã nằm trong `.gitignore`.
- Ứng dụng chỉ mở ở `127.0.0.1`, máy khác trong mạng không truy cập được.

## 10. Xử lý lỗi thường gặp

| Hiện tượng | Cách xử lý |
|---|---|
| `python` không được nhận diện | Cài lại Python, tích “Add to PATH”; hoặc dùng `py` (Windows) / `python3` (macOS, Linux). |
| “SUpload đã chạy ở cửa sổ khác” | Đã có một cửa sổ đang chạy: dùng giao diện đó (vừa được mở lại). Muốn khởi động lại thì tắt cửa sổ cũ bằng `Ctrl + C` trước. |
| `Address already in use` / cổng 5000 bận | Chạy ở cổng khác: Windows `set PORT=5050` rồi `python app.py`; macOS/Linux `PORT=5050 python app.py`. |
| Trang trắng, báo “Chưa có giao diện” | Thư mục `web/` bị thiếu: tải lại mã nguồn, hoặc build lại (mục 12). |
| Lỗi `[190] ...` | Token hết hạn/không hợp lệ: lấy User Token mới ở Graph API Explorer và làm lại **Bước 3**. |
| Lỗi `[200] ...` hoặc `[10] ...` | Thiếu quyền: tạo lại token với đủ 3 quyền và nhớ **chọn đúng Page** khi cấp quyền. |
| Lỗi `[368] ...` | Facebook tạm chặn vì đăng quá dày/nội dung giống spam: giãn lịch đăng, đa dạng nội dung. |
| “Không có Page nào” khi lấy danh sách | Tài khoản chưa là admin của Page, hoặc khi cấp quyền chưa chọn Page đó. |
| Bài hẹn giờ không được đăng | Bài *Đang chờ* (chưa *Đã hẹn trên Facebook*) cần ứng dụng đang chạy lúc tới giờ; kiểm tra giờ của máy tính có đúng không. |
| Bài bị “Dời sang …” | Do **Giới hạn an toàn** (số bài/ngày, giãn cách). Chỉnh trong Cài đặt nếu muốn. |
| “Không huỷ được bài hẹn trên Facebook” | Kiểm tra mạng rồi thử lại; hoặc chọn *Vẫn xoá khỏi danh sách* rồi tự xoá bài hẹn trong mục *Bài viết đã lên lịch* của Page. |
| Bài bị đánh dấu Lỗi “Ứng dụng bị tắt khi đang đăng” | Kiểm tra Page xem bài đã lên chưa rồi mới bấm **Đăng lại** để tránh trùng. |
| Cách Trình duyệt: `chưa cài playwright` | Chạy `pip install -r requirements.txt` rồi `playwright install chromium`. |
| Cách Trình duyệt: không tìm thấy nút | Xem ảnh trong `screenshots/`; tắt chạy ẩn để quan sát; sửa `RE_*` trong `supload/integrations/browser.py`. |

Mọi hoạt động và lỗi đều được ghi ở trang **Nhật ký**.

## 11. Chạy kiểm thử (tuỳ chọn)

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Facebook được giả lập trong mọi test, **không đăng bài thật**.

| File | Kiểm tra |
|---|---|
| `tests/test_planner.py` | Giới hạn an toàn (logic thuần) |
| `tests/test_facebook.py` | Lớp Graph API: đăng, hẹn giờ, huỷ, kiểm tra trạng thái |
| `tests/test_fb_scheduling.py` | Vòng đời bài hẹn trên Facebook, đối soát, giới hạn an toàn trong luồng nền |
| `tests/test_app.py` | API, luồng đăng nền, quản lý flow, token không lộ ra trình duyệt |
| `tests/test_pages.py` | Nhiều Page: chuyển dữ liệu cũ, đăng đúng Page, giới hạn theo Page |
| `tests/test_maintenance.py`, `tests/test_instance.py`, `tests/test_health.py` | Sao lưu & dọn dẹp, chặn chạy 2 lần, kiểm tra kết nối |
| `tests/test_insights.py` | Lấy chỉ số tương tác, tổng hợp, giờ hiệu quả |
| `tests/test_video.py` | Video thường & Reels (tải lên 3 bước, hẹn giờ, đối soát) |
| `tests/test_import.py`, `tests/test_library.py` | Nhập bài từ CSV/Excel, thư viện nội dung & ảnh |
| `tests/test_e2e.py` | Giao diện thật bằng trình duyệt tự động (kể cả kéo thả trên Lịch) (cần `playwright install chromium`; tự bỏ qua nếu chưa cài) |

Kiểm thử bộ tính lịch của Flow (cần Node.js 18+):

```bash
cd frontend
npm install
npm test
```

## 12. Sửa giao diện (dành cho lập trình viên)

Mã nguồn giao diện nằm trong `frontend/` (Vite + React 18, Mantine, React Flow, Tabler Icons). Cần Node.js 18+.

```bash
python app.py                 # cửa sổ 1: chạy API ở cổng 5000
cd frontend && npm install    # cửa sổ 2
npm run dev                   # http://localhost:5173, tự tải lại khi sửa code
npm run build                 # build ra ../web để python app.py phục vụ
```

Thêm loại khối Flow mới: khai báo trong `frontend/src/features/flow/engine/nodes.jsx` (trường cấu hình, mặc định,
cách tính lịch); bảng Thuộc tính tự sinh giao diện từ khai báo đó.

## 13. Dùng bằng dòng lệnh (không cần giao diện)

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

## 14. Kiến trúc

```
app.py, fb_poster.py, browser_poster.py   Lối vào (chỉ vài dòng, gọi vào package supload/)

supload/                      Backend (Python, Flask)
  app.py                      create_app(config): ghép các phần lại (application factory)
  config.py                   Đường dẫn & cài đặt mặc định (không dùng biến toàn cục)
  storage.py                  Store: đọc/ghi data.json an toàn luồng, transaction
  domain/                     Nghiệp vụ thuần, không phụ thuộc Flask/mạng
    posts.py                    vòng đời bài: pending → running/scheduled → done/error
    pages.py                    các Page đã kết nối, chuyển dữ liệu kiểu cũ
    health.py                   tình trạng kết nối từng Page, lỗi Facebook dễ hiểu
    flows.py  settings.py
    planner.py                  giới hạn an toàn: tính thời điểm đăng thực tế
  integrations/               Giao tiếp bên ngoài
    facebook.py                 Graph API (đăng, hẹn giờ, huỷ, kiểm tra)
    browser.py                  Playwright
  services/                   Điều phối
    publisher.py                đăng ngay / giao Facebook hẹn giờ / huỷ / đối soát
    scheduler.py                luồng nền: đối soát → đăng bài đến giờ → giao Facebook → kiểm tra kết nối → bảo trì
    maintenance.py              sao lưu & dọn dữ liệu hằng ngày
  api/                        HTTP, mỗi file một nhóm tài nguyên (Flask blueprint)
    state.py  posts.py  flows.py  pages.py  settings.py
  cli/                        Dòng lệnh (fb_poster.py, browser_poster.py)

frontend/src/                 Giao diện (React + Mantine + React Flow)
  app/                        Khung ứng dụng, context dùng chung
  api/                        client.js (fetch) + endpoints.js (mọi API, gom theo nhóm)
  components/                 UI dùng chung: PageHeader, PhotoPicker, PostPreview, EmptyState…
  features/                   Mỗi tính năng một thư mục
    compose/  queue/  log/  settings/
    flow/  FlowPage, FlowList, FlowDialogs, editor/ (bảng vẽ, khối, thuộc tính), engine/ (tính lịch, danh mục khối)
  lib/                        Tiện ích: thời gian, localStorage, form, Page

web/                          Giao diện đã build (không sửa trực tiếp)
tests/                        Kiểm thử Python (pytest)
```

Nguyên tắc: `api/` chỉ nhận/trả HTTP rồi gọi `domain/` và `services/`; `domain/` không gọi mạng nên test nhanh,
không cần giả lập; mọi lời gọi Facebook đi qua `integrations/facebook.call` (test thay bằng bản giả).

## Lưu ý

- Chỉ dùng cho Page bạn quản lý và tuân thủ [Điều khoản của Facebook](https://www.facebook.com/terms).
- Đăng quá dày hoặc nội dung lặp lại có thể bị Facebook giới hạn: dùng khối **Khung giờ**, **Chờ ngẫu nhiên**
  và nhiều phiên bản nội dung để lịch đăng tự nhiên hơn.
