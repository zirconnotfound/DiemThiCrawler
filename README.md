# DiemThiCrawler 🕷️

**DiemThiCrawler** là một công cụ Python để tự động thu thập và xuất dữ liệu điểm thi (tra cứu điểm tuyển sinh vào lớp 10) từ cổng thông tin của Sở GD&ĐT Hà Tĩnh (https://hatinh.edu.vn). Công cụ này: thu thập, lưu trữ vào SQLite và xuất kết quả để xử lý/đưa vào Excel.

---

## 📋 Mục tiêu

- Tự động hóa việc lấy điểm thi theo `số báo danh` trong một dải số.
- Lưu kết quả vào cơ sở dữ liệu SQLite với khoá chính là `(sbd, mon_chuyen)` để xử lý các trường hợp cùng SBD có nhiều bản ghi.
- Xuất dữ liệu đã thu thập sang Excel bằng `SortWorker.py`.

---

## 🔧 Tính năng chính

- Tự động điều khiển trình duyệt (Playwright) để gửi truy vấn và nhận kết quả.
- Giải CAPTCHA bằng mô-đun nội bộ (`Captcha.py`) — ảnh CAPTCHA được lưu tạm dưới `captcha_images/` và bị ignore bởi Git.
- Lưu kết quả vào `data/output.sqlite3` (SQLite).
- Retry logic: cố gắng giải CAPTCHA cho mỗi SBD nhiều lần (configurable), và thực hiện nhiều vòng thử lại cho những SBD thất bại.

---

## 🛠️ Yêu cầu

- Python 3.8+ (hoạt động với 3.10/3.12 theo thử nghiệm).
- Các thư viện: được liệt kê trong `requirements.txt`. Cài bằng:

```bash
pip install -r requirements.txt
```

- Playwright cần được cài và cài browser binaries:

```bash
python -m playwright install
```

---

## ⚙️ Cấu hình (.env)

Sao chép `.env.example` thành `.env` rồi chỉnh các biến theo nhu cầu:

```bash
cp .env.example .env
```

Các biến quan trọng trong `.env`:

- `START` – bắt đầu của dải SBD (mặc định: 350001)
- `END` – kết thúc của dải SBD (mặc định: 350999)
- `OUTPUT_FILE` – đường dẫn/ tên file excel đầu ra (mặc định trong `.env.example`)
- `MAX_CAPTCHA_ATTEMPTS` – số lần thử giải CAPTCHA cho một SBD trong một vòng (mặc định: 7)
- `MAX_ROUNDS` – số vòng lặp thử lại các SBD thất bại (mặc định: 3)
- `RESPONSE_TIMEOUT` – thời gian chờ (giây) để đợi phản hồi sau khi submit (mặc định: 1.0)
- `ROUND_PAUSE_MS` – tạm dừng giữa các vòng (ms)
- `FINAL_WAIT_MS` – thời gian chờ cuối trước khi đóng trình duyệt (ms)
- `MIN_DELAY`, `MAX_DELAY` – khoảng random (giây) nghỉ giữa mỗi số báo danh để giảm tải lên server

Lưu ý: `.env` không nên chứa thông tin nhạy cảm đã commit — file `.env.example` chỉ là mẫu.

---

## 🚀 Chạy chương trình

1. Tạo môi trường ảo (khuyến nghị):

```bash
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\\Scripts\\activate     # Windows PowerShell
```

2. Cài phụ thuộc và Playwright:

```bash
pip install -r requirements.txt
python -m playwright install
```

3. Chuẩn bị `.env` như ý và chạy:

```bash
python Main.py
```

4. Kết quả: chương trình lưu dữ liệu vào `data/output.sqlite3`. Sau khi kết thúc, `Main.py` sẽ gọi `SortWorker` để xuất file Excel (theo `OUTPUT_FILE` trong `.env`).

---

## 📂 Cấu trúc mã nguồn (tổng quan)

```
.
├── Crawler.py         # Luồng thu thập chính: điều khiển Playwright, xử lý CAPTCHA, lưu vào SQLite
├── Captcha.py         # Tiền xử lý ảnh CAPTCHA và gọi OCR (ddddocr)
├── Main.py            # Entrypoint: load .env, khởi tạo Crawler, gọi exporter
├── SortWorker.py      # Chia/ gom/ xuất dữ liệu ra Excel theo môn chuyên
├── requirements.txt   # Thư viện cần cài
├── .env.example       # Mẫu biến môi trường
├── .gitignore
├── data/              # (tự tạo) Chứa output.sqlite3
├── captcha_images/    # (tự tạo) Ảnh captcha được lưu tạm
└── Run.txt            # Các ghi chú vận hành
```

---

## 📝 Ghi chú quan trọng / Troubleshooting

- Nếu Playwright báo lỗi thiếu trình duyệt, chạy `python -m playwright install`.
- Môi trường cục bộ cần có `pandas`, `playwright`, `beautifulsoup4`, `ddddocr`, `opencv-python` như trong `requirements.txt`.
- Nếu bạn thấy lỗi về `.body()` (Protocol error: No data found...), đã implement cơ chế bỏ qua response không đọc được và log warning — điều này là bình thường cho một số loại response không có body.
- SQLite: `data/output.sqlite3` là lưu trữ chính; sao lưu file này nếu cần giữ kết quả lâu dài.

---

## 🙏 Đóng góp

Rất hoan nghênh PR và issue. Nếu bạn muốn mở rộng (ví dụ: thay OCR, dùng external CAPTCHA service, hoặc export thêm định dạng), hãy mở issue để thảo luận trước.

---

## 🧾 Giấy phép

Dự án phát hành theo MIT License.

---

_Chúc bạn sử dụng DiemThiCrawler hiệu quả!_
