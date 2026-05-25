import os
import sqlite3
import pandas as pd
import asyncio
import random
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from Captcha import read_captcha

class DiemThiCrawler:
    def __init__(
        self,
        start: int,
        end: int,
        url: str = "https://hatinh.edu.vn/tracuudiemthi_ts10",
        max_captcha_attempts: int = 7,
        max_rounds: int = 3,
        response_timeout: float = 1.0,
        round_pause_ms: int = 1000,
        final_wait_ms: int = 3000,
        min_delay: float = 1.0,
        max_delay: float = 2.0,
    ):
        self.start = start
        self.end = end
        self.columns = [
            "Số báo danh", "Họ và tên", "Điểm Toán", "Điểm Anh", "Điểm Văn",
            "Điểm ƯT", "Điểm KK", "Tổng không chuyên", "Môn chuyên",
            "Điểm chuyên", "Tổng chuyên", "Ghi chú"
        ]
        self.url = url
        self.captcha_image_path = os.path.join("captcha_images", "captcha.png")
        self.database_path = os.path.join("data", "output.sqlite3")
        self.table_name = "diem_thi"
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
        # Configurable parameters
        self.max_captcha_attempts = int(max_captcha_attempts)
        self.max_rounds = int(max_rounds)
        self.response_timeout = float(response_timeout)
        self.round_pause_ms = int(round_pause_ms)
        self.final_wait_ms = int(final_wait_ms)
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)

    def _get_connection(self) -> sqlite3.Connection:
        os.makedirs(os.path.dirname(self.database_path), exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_table(self, connection: sqlite3.Connection) -> None:
        column_definitions = []
        for index, column_name in enumerate(self.db_columns):
            column_definitions.append(f'"{column_name}" TEXT')
        # Use composite primary key on (sbd, mon_chuyen)
        pk_columns = ("sbd", "mon_chuyen")
        connection.execute(
            f'CREATE TABLE IF NOT EXISTS "{self.table_name}" ({", ".join(column_definitions)}, PRIMARY KEY ("{pk_columns[0]}", "{pk_columns[1]}"))'
        )
        connection.commit()

    def _insert_row(self, connection: sqlite3.Connection, row: list) -> None:
        placeholders = ", ".join(["?"] * len(self.db_columns))
        quoted_columns = ", ".join([f'"{column}"' for column in self.db_columns])
        connection.execute(
            f'INSERT OR IGNORE INTO "{self.table_name}" ({quoted_columns}) VALUES ({placeholders})',
            row
        )
        connection.commit()

    def _load_existing_sbds(self, connection: sqlite3.Connection) -> set:
        self._ensure_table(connection)
        cursor = connection.execute(
            f'SELECT DISTINCT "{self.db_columns[0]}" FROM "{self.table_name}"'
        )
        return {str(row[0]) for row in cursor.fetchall() if row[0] is not None}

    async def extract_columns_from_table(self, page):
        headers = await page.eval_on_selector_all(
            "thead > tr > th",
            "ths => ths.map(th => th.innerText)"
        )
        self.columns = headers

    def extract_scores_from_html(self, html: str) -> pd.DataFrame:
        soup = BeautifulSoup(html, "html.parser")
        tbody = soup.find("tbody")
        data = []

        if not tbody:
            return pd.DataFrame(columns=self.columns)

        for row in tbody.find_all("tr"):
            cols = [col.get_text(strip=True) for col in row.find_all("td")]
            if cols:
                data.append(cols)

        if data:
            return pd.DataFrame(data, columns=self.columns)
        else:
            return pd.DataFrame(columns=self.columns)

    def verify_response(self, response_url: str, html: str) -> bool:
        return "hatinh.edu.vn" in response_url and "BotDetect" not in html
    
    async def solve_captcha(self, image_bytes: bytes) -> str:
        os.makedirs(os.path.dirname(self.captcha_image_path), exist_ok=True)
        with open(self.captcha_image_path, "wb") as image_file:
            image_file.write(image_bytes)

        return read_captcha(self.captcha_image_path)

    async def run(self) -> None:
        valid_response_received = asyncio.Event()

        with self._get_connection() as connection:
            self._ensure_table(connection)
            existing_sbds = self._load_existing_sbds(connection)
            pending_numbers = [str(n) for n in range(self.start, self.end + 1) if str(n) not in existing_sbds]

            if not pending_numbers:
                print("No pending SBDs to crawl. Exiting early.")
                return

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()

                async def handle_response(response):
                    if response.request.method == "POST":
                        try:
                            body = await response.body()
                        except Exception as e:
                            # Some responses (e.g., data URLs, service workers, or streamed resources)
                            # may not expose body via Playwright's API. Skip these silently but log.
                            try:
                                url = response.url
                            except Exception:
                                url = "<unknown>"
                            print(f"Warning: could not read response body for {url}: {e}")
                            return

                        try:
                            html = body.decode("utf-8")
                        except Exception:
                            html = body.decode("utf-8", errors="ignore")

                        if self.verify_response(response.url, html):
                            scores_df = self.extract_scores_from_html(html)
                            for row in scores_df.values.tolist():
                                if row:
                                    self._insert_row(connection, row)
                            valid_response_received.set()

                await page.goto(self.url)
                await page.wait_for_load_state("networkidle")

                await self.extract_columns_from_table(page)

                page.on("response", handle_response)

                for round_no in range(1, self.max_rounds + 1):
                    if not pending_numbers:
                        break
                    print(f"Round {round_no}/{self.max_rounds} - attempting {len(pending_numbers)} numbers")
                    next_round = []

                    for num in list(pending_numbers):
                        await page.fill("input[name='keyword']", num)
                        solved = False

                        for attempt in range(1, self.max_captcha_attempts + 1):
                            valid_response_received.clear()
                            await page.fill("#captcha_code", "")

                            try:
                                captcha_img = await page.wait_for_selector(".captcha-refresh > img")
                                captcha_src = await captcha_img.get_attribute("src")
                                url = "https://hatinh.edu.vn" + captcha_src
                                img_response = await page.request.get(url)
                                captcha_bytes = await img_response.body()
                                captcha_solution = await self.solve_captcha(captcha_bytes)
                                await page.fill("#captcha_code", captcha_solution)
                            except Exception as e:
                                print(f"Error fetching/solving CAPTCHA for {num} (attempt {attempt}/{self.max_captcha_attempts}): {e}")
                                if attempt == self.max_captcha_attempts:
                                    print(f"Failed to solve CAPTCHA for {num} after {self.max_captcha_attempts} attempts.")
                                continue

                            await page.click("button.btn.btn-primary")

                            try:
                                await asyncio.wait_for(valid_response_received.wait(), timeout=self.response_timeout)
                                solved = True
                                break
                            except asyncio.TimeoutError:
                                print(f"No valid response for {num} on attempt {attempt}/{self.max_captcha_attempts}. Retrying...")

                        if not solved:
                            next_round.append(num)

                        # polite delay between each number to reduce request rate
                        await asyncio.sleep(random.uniform(self.min_delay, self.max_delay))

                    pending_numbers = next_round
                    # slight pause between rounds to avoid hammering the server
                    if pending_numbers:
                        await page.wait_for_timeout(self.round_pause_ms)

                await page.wait_for_timeout(self.final_wait_ms)
                await browser.close()

            return None
