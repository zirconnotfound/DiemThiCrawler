# DiemThiCrawler 🕷️

**DiemThiCrawler** là một công cụ được viết bằng Python dùng để **tự động thu thập và sắp xếp dữ liệu điểm thi vào lớp 10 THPT** của tỉnh **Hà Tĩnh** từ cổng thông tin chính thức: [https://hatinh.edu.vn](https://hatinh.edu.vn).

---

## 📋 Tính năng

- ✅ **Tự động thu thập** dữ liệu điểm thi từ website của Sở GD&ĐT Hà Tĩnh.
- 🔢 **Sắp xếp và lọc dữ liệu** để dễ dàng phân tích.
- 🧠 **Thiết kế theo mô-đun**, dễ bảo trì và mở rộng.

---

## 🛠️ Yêu cầu

- Python **3.7+**
- Trình quản lý gói `pip`

---

## ⚙️ Cài đặt

1. Tải mã nguồn:
   ```bash
   git clone https://github.com/zirconnotfound/DiemThiCrawler.git
   cd DiemThiCrawler
   ```

2. Cài đặt các thư viện phụ thuộc:
   ```bash
   pip install -r requirements.txt
   ```

---

## 🧪 Cấu hình

Sao chép file `.env.example` thành `.env` và điền các biến môi trường cần thiết:

```bash
cp .env.example .env
```

Tuỳ chỉnh thông tin như API key (nếu có), cấu hình proxy hoặc các tuỳ chọn crawler khác (nếu cần).

---

## 🚀 Cách sử dụng

Chạy toàn bộ quy trình:
```bash
python Main.py
```

Kết quả (CSV, Excel, JSON...) sẽ được lưu tại thư mục hiện hành hoặc đường dẫn đầu ra bạn cấu hình.

---

## 📂 Cấu trúc thư mục

```
.
├── Crawler.py       # Thu thập dữ liệu điểm thi từ trang web
├── Main.py          # Tập lệnh chính để chạy toàn bộ quá trình
├── SortWorker.py    # Xử lý, sắp xếp dữ liệu điểm đã crawl
├── requirements.txt # Danh sách thư viện Python cần cài
├── .env.example     # Mẫu file biến môi trường
├── .gitignore
└── Run.txt          # Ghi chú/câu lệnh ví dụ để chạy
```

---

## 📝 Đóng góp

Rất hoan nghênh mọi đóng góp! Bạn có thể gửi pull request để cải thiện mã nguồn, sửa lỗi hoặc thêm tính năng mới.

---

## 🧾 Giấy phép

Dự án được phát hành theo giấy phép [MIT License](LICENSE) — bạn được phép sử dụng và chỉnh sửa tự do.

---

## 📞 Liên hệ

Nếu có câu hỏi, vui lòng mở issue trên GitHub hoặc liên hệ qua email cá nhân (nếu có cung cấp).

---

*Chúc bạn sử dụng DiemThiCrawler hiệu quả! 🇻🇳📊*
