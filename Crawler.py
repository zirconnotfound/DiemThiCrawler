import os
import re
import json
import time
import base64
import random
import sqlite3
import binascii
from contextlib import closing
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup, SoupStrainer

from Captcha import read_captcha

CAPTCHA_FIELDS = ("captcha_code", "captcha_check", "BDC_UserSpecifiedCaptchaId")

THROTTLE_STATUSES = (429, 503)
MAX_BACKOFF_SECONDS = 300.0

_IMG_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"BM", b"RIFF")

# Request mà nút tìm kiếm trên trang gửi đi (tải lại module Content.Listing).
# 1016 là id module do trình duyệt tự cấp khi nạp bảng kết quả.
SEARCH_PATH = (
    "/?module=Content.Listing&moduleId=1016&cmd=redraw&url_mode=rewrite"
    "&submitFormId=1016&page=&site=32982"
)
# Field cố định của POST; keyword (SBD), securityToken và CAPTCHA được thêm khi gửi
SEARCH_FIELDS = {
    "service": "Content.Decl.DataSet.Grouping.select",
    "itemId": "6a460ec2f27bb143f004ca12",   # bộ dữ liệu năm 2026, đổi khi tra năm khác
    "layout": "Decl.DataSet.Detail.default",
    "type": "Decl.DataSet",
    "gridModuleParentId": "16",
    "moduleParentId": "-1",
    "modulePosition": "0",
    "itemsPerPage": "1000",
    "pageNo": "1",
    "page": "",
    "orderBy": "",
    "unRegex": "",
}


def decode_image_body(body: bytes) -> bytes:
    """
    Trả về byte ảnh thật, bất kể server trả:
      - byte ảnh thô (thường gặp; DevTools chỉ *hiển thị* dạng hex)
      - chuỗi hex dạng text
      - base64 / data URL
    """
    if body.startswith(_IMG_MAGIC):
        return body
    text = body.strip().decode("ascii", errors="ignore")
    if text.startswith("data:image"):
        return base64.b64decode(text.split(",", 1)[1])
    hex_candidate = text[2:] if text.lower().startswith("0x") else text
    if hex_candidate and re.fullmatch(r"[0-9a-fA-F\s]+", hex_candidate):
        raw = bytes.fromhex(re.sub(r"\s+", "", hex_candidate))
        if raw.startswith(_IMG_MAGIC):
            return raw
    try:
        raw = base64.b64decode(text, validate=True)
        if raw.startswith(_IMG_MAGIC):
            return raw
    except (binascii.Error, ValueError):
        pass
    raise ValueError(f"Không nhận ra định dạng ảnh, 16 byte đầu: {body[:16]!r}")


class DiemThiCrawler:
    def __init__(
        self,
        start: int,
        end: int,
        base_url: str = "https://hatinh.edu.vn",
        post_path: str = SEARCH_PATH,
        form_page_path: str = "/tracuudiemthi_ts10",
        site: str = "32982",
        captcha_path: str = "/api/Common/Captcha/getCaptcha",
        keyword_field: str = "keyword",
        captcha_width: int = 150,
        captcha_height: int = 50,
        csrf_field: str = "securityToken",          # giá trị lấy từ csrfToken trong cookie JWT
        base_fields: dict = None,                   # None = dùng SEARCH_FIELDS
        extra_headers: dict = None,
        jwt_cookie_name: str = "AUTH_BEARER_default",
        max_captcha_attempts: int = 7,
        max_rounds: int = 3,
        round_pause_ms: int = 1000,
        min_delay: float = 1.0,
        max_delay: float = 2.0,
        timeout: float = 15.0,
        response_timeout: float = 1.0,
        final_wait_ms: int = 3000,
        url: str = None,
    ):
        self.start = start
        self.end = end
        self.database_path = os.path.join("data", "output.sqlite3")
        self.table_name = "diem_thi"
        self.status_table_name = "trang_thai"
        self.db_columns = [
            "sbd",
            "ho_va_ten",
            "diem_toan",
            "diem_anh",
            "diem_van",
            "diem_ut",
            "diem_kk",
            "tong_khong_chuyen",
            "mon_chuyen",
            "diem_chuyen",
            "tong_chuyen",
            "ghi_chu",
        ]

        self.base = base_url.rstrip("/")
        self.post_path = post_path
        self.form_page_path = form_page_path or url
        self.site = site
        self.captcha_path = captcha_path
        self.captcha_width = captcha_width
        self.captcha_height = captcha_height
        self.keyword_field = keyword_field
        self.csrf_field = csrf_field
        self.base_fields = dict(SEARCH_FIELDS if base_fields is None else base_fields)
        self.jwt_cookie_name = jwt_cookie_name
        self.timeout = float(timeout)

        self.max_captcha_attempts = int(max_captcha_attempts)
        self.max_rounds = int(max_rounds)
        self.round_pause_ms = int(round_pause_ms)
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (DiemThiCrawler)",
            "Referer": self.base + (self.form_page_path or "/"),
            "Origin": self.base,
            "X-Requested-With": "XMLHttpRequest",
            **(extra_headers or {}),
        })

    def open_form_page(self) -> requests.Response:
        """GET trang form để có cookie JWT ban đầu (guestId, csrfToken)."""
        if not self.form_page_path:
            raise ValueError("Chưa cấu hình form_page_path")
        r = self.session.get(self.base + self.form_page_path, timeout=self.timeout)
        r.raise_for_status()
        return r

    def fetch_captcha(self) -> bytes:
        """
        GET ảnh CAPTCHA mới. Mỗi lần gọi ghi đè đáp án cũ phía server.
        r.content thường đã là byte JPEG thô (FF D8 FF); decode_image_body là lớp phòng hờ.
        """
        params = {
            "returnType": "image",
            "site": self.site,
            "width": self.captcha_width,
            "height": self.captcha_height,
            "t": int(time.time() * 1000),  # chống cache
        }
        r = self.session.get(self.base + self.captcha_path, params=params, timeout=self.timeout)
        r.raise_for_status()
        body = r.content
        return body if body[:3] == b"\xff\xd8\xff" else decode_image_body(body)

    def submit(self, answer: str, fields: dict) -> requests.Response:
        """POST form: fields (keyword + csrf + field khác) + 3 field CAPTCHA mang đáp án."""
        data = dict(fields)
        for name in CAPTCHA_FIELDS:
            data[name] = answer
        return self.session.post(self.base + self.post_path, data=data, timeout=self.timeout)

    def _jwt_payload(self) -> dict:
        token = None
        if self.jwt_cookie_name:
            token = self.session.cookies.get(self.jwt_cookie_name)
        else:
            for c in self.session.cookies:
                if c.value and c.value.count(".") == 2 and c.value.startswith("eyJ"):
                    token = c.value
                    break
        if not token:
            return {}
        try:
            part = token.split(".")[1]
            part += "=" * (-len(part) % 4)
            return json.loads(base64.urlsafe_b64decode(part))
        except (IndexError, ValueError, binascii.Error):
            return {}

    def _csrf_token(self) -> str:
        data = str(self._jwt_payload().get("data", ""))
        m = re.search(r'csrfToken\|s:\d+:"([^"]*)"', data)
        return m.group(1) if m else None

    def _guest_id(self) -> str:
        data = str(self._jwt_payload().get("data", ""))
        m = re.search(r'guestId\|s:\d+:"([^"]*)"', data)
        return m.group(1) if m else None

    def _build_fields(self, keyword) -> dict:
        fields = dict(self.base_fields)
        fields[self.keyword_field] = str(keyword)   # giữ dạng chuỗi như bản cũ
        if self.csrf_field:
            token = self._csrf_token()
            if token:
                fields[self.csrf_field] = token
        return fields

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_tables(self, connection: sqlite3.Connection) -> None:
        column_definitions = [f'"{name}" TEXT' for name in self.db_columns]
        with connection:
            connection.execute(
                f'CREATE TABLE IF NOT EXISTS "{self.table_name}" '
                f'({", ".join(column_definitions)}, PRIMARY KEY ("sbd", "mon_chuyen"))'
            )
            # SBD đã tra xong, kể cả khi không có dòng điểm nào
            connection.execute(
                f'CREATE TABLE IF NOT EXISTS "{self.status_table_name}" '
                f'(sbd TEXT PRIMARY KEY, so_dong INTEGER NOT NULL, '
                f'cap_nhat TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)'
            )

    def _save_result(self, connection: sqlite3.Connection, sbd: str, rows: list) -> None:
        """Ghi các dòng điểm và trạng thái của một SBD trong cùng một transaction."""
        placeholders = ", ".join(["?"] * len(self.db_columns))
        quoted_columns = ", ".join([f'"{c}"' for c in self.db_columns])
        with connection:  # tự commit, hoặc rollback nếu lỗi
            connection.executemany(
                f'INSERT OR IGNORE INTO "{self.table_name}" ({quoted_columns}) VALUES ({placeholders})',
                rows
            )
            connection.execute(
                f'INSERT OR REPLACE INTO "{self.status_table_name}" (sbd, so_dong) VALUES (?, ?)',
                (sbd, len(rows))
            )

    def _load_existing_sbds(self, connection: sqlite3.Connection) -> set:
        cursor = connection.execute(
            f'SELECT "{self.db_columns[0]}" FROM "{self.table_name}" '
            f'UNION SELECT sbd FROM "{self.status_table_name}"'
        )
        return {str(row[0]) for row in cursor if row[0] is not None}

    # ============================ Parse HTML ============================
    def extract_scores_from_html(self, html):
        """
        Trả về list các dòng trong tbody đầu tiên, hoặc None nếu trang không có tbody.
        html: bytes (ưu tiên, để BS tự dò charset) hoặc str.
        """
        soup = BeautifulSoup(html, "lxml", parse_only=SoupStrainer("tbody"))
        tbody = soup.find("tbody")
        if tbody is None:
            return None

        rows = []
        for row in tbody.find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if cols:
                rows.append(cols)
        return rows

    def verify_response(self, response_url: str, html: bytes) -> bool:
        same_host = urlsplit(response_url).hostname == urlsplit(self.base).hostname
        return same_host and b"BotDetect" not in html

    def solve_captcha(self, image_bytes: bytes) -> str:
        """Giải CAPTCHA trực tiếp từ byte ảnh trong bộ nhớ."""
        return read_captcha(image_bytes)

    def _backoff(self, error: Exception, attempt: int) -> None:
        """Nếu server trả 429/503 thì chờ theo Retry-After, không có thì tăng dần theo cấp số nhân."""
        response = getattr(error, "response", None)
        if response is None or response.status_code not in THROTTLE_STATUSES:
            return
        try:
            delay = float(response.headers.get("Retry-After", ""))
        except ValueError:
            delay = self.max_delay * 2 ** attempt
        delay = min(max(delay, self.min_delay), MAX_BACKOFF_SECONDS)
        print(f"Server trả {response.status_code}, chờ {delay:.1f}s")
        time.sleep(delay)

    def run(self) -> None:
        if not self.post_path:
            raise ValueError("Chưa cấu hình post_path")

        with closing(self._get_connection()) as connection:
            self._ensure_tables(connection)
            existing_sbds = self._load_existing_sbds(connection)
            pending_numbers = [
                str(n) for n in range(self.start, self.end + 1)
                if str(n) not in existing_sbds
            ]
            if not pending_numbers:
                print("No pending SBDs to crawl. Exiting early.")
                return

            # Mở trang form: lấy cookie JWT ban đầu
            if self.form_page_path:
                try:
                    self.open_form_page()
                except Exception as e:
                    print(f"Warning: could not open form page: {e}")
                    self._backoff(e, 1)

            for round_no in range(1, self.max_rounds + 1):
                if not pending_numbers:
                    break
                print(f"Round {round_no}/{self.max_rounds} - attempting {len(pending_numbers)} numbers")
                next_round = []

                for num in list(pending_numbers):
                    solved = False

                    for attempt in range(1, self.max_captcha_attempts + 1):
                        try:
                            captcha_bytes = self.fetch_captcha()
                            captcha_solution = self.solve_captcha(captcha_bytes)
                        except Exception as e:
                            print(f"Error fetching/solving CAPTCHA for {num} "
                                  f"(attempt {attempt}/{self.max_captcha_attempts}): {e}")
                            if attempt == self.max_captcha_attempts:
                                print(f"Failed to solve CAPTCHA for {num} "
                                      f"after {self.max_captcha_attempts} attempts.")
                            self._backoff(e, attempt)
                            continue

                        if not captcha_solution:
                            print(f"Bỏ qua {num}: không có đáp án CAPTCHA.")
                            break

                        fields = self._build_fields(num)
                        try:
                            resp = self.submit(captcha_solution.strip(), fields)
                            resp.raise_for_status()
                        except Exception as e:
                            print(f"Error submitting for {num} (attempt {attempt}): {e}")
                            self._backoff(e, attempt)
                            continue

                        if self.verify_response(resp.url, resp.content):
                            rows = self.extract_scores_from_html(resp.content)
                            if rows is None:
                                # Trang lạ: không lưu trạng thái, lần chạy sau sẽ tra lại
                                print(f"[{num}] Không thấy bảng kết quả")
                            elif any(len(row) != len(self.db_columns) for row in rows):
                                print(f"[{num}] Số cột không khớp db_columns, không lưu")
                            else:
                                self._save_result(connection, num, rows)
                                print(f"[{num}] OK - {len(rows)} dòng")
                            solved = True
                            break
                        else:
                            print(f"No valid response for {num} on attempt "
                                  f"{attempt}/{self.max_captcha_attempts}. Retrying...")

                    if not solved:
                        next_round.append(num)

                    time.sleep(random.uniform(self.min_delay, self.max_delay))

                pending_numbers = next_round
                if pending_numbers:
                    time.sleep(self.round_pause_ms / 1000.0)

        return None


if __name__ == "__main__":
    crawler = DiemThiCrawler(
        start=350001,
        end=350001,
    )
    crawler.run()
