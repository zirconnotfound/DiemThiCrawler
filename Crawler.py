import base64
import time
import pandas as pd
import asyncio
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import requests

class DiemThiCrawler:
    def __init__(self, start: int, end: int, mode: str, api_key: str = ""):
        self.start = start
        self.end = end
        self.mode = mode
        self.api_key = api_key
        self.columns = [
            "Số báo danh", "Họ và tên", "Điểm Toán", "Điểm Anh", "Điểm Văn",
            "Điểm ƯT", "Điểm KK", "Tổng không chuyên", "Môn chuyên",
            "Điểm chuyên", "Tổng chuyên", "Ghi chú"
        ]
        self.captured_data = []

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
        b64_image = base64.b64encode(image_bytes).decode()
        resp = requests.post("http://2captcha.com/in.php", data={
            "key": self.api_key,
            "method": "base64",
            "body": b64_image,
            "json": 1
        }).json()

        if resp["status"] != 1:
            raise Exception("2Captcha submission failed:", resp["request"])

        captcha_id = resp["request"]
        for _ in range(20):
            time.sleep(5)
            check = requests.get("http://2captcha.com/res.php", params={
                "key": self.api_key,
                "action": "get",
                "id": captcha_id,
                "json": 1
            }).json()
            if check["status"] == 1:
                return check["request"]
            elif check["request"] != "CAPCHA_NOT_READY":
                raise Exception("2Captcha error:", check["request"])
        raise Exception("2Captcha timed out")

    async def run(self) -> pd.DataFrame:
        df = pd.DataFrame(columns=self.columns)
        valid_response_received = asyncio.Event()
        current_number = self.start

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            async def handle_response(response):
                if response.request.method == "POST":
                    body = await response.body()
                    html = body.decode("utf-8")
                    if self.verify_response(response.url, html):
                        scores_df = self.extract_scores_from_html(html)
                        self.captured_data.extend(scores_df.values.tolist())
                        valid_response_received.set()

            await page.goto("https://hatinh.edu.vn/tracuudiemthi_ts10")
            await page.wait_for_load_state("networkidle")

            await page.evaluate("""
                window.__isTyping = false;
                const input = document.querySelector("#captcha_code");
                input.addEventListener("input", () => { window.__isTyping = true; });
                input.addEventListener("blur", () => { window.__isTyping = false; });
            """)

            page.on("response", handle_response)

            while current_number < self.end + 1:
                valid_response_received.clear()
                await page.fill("input[name='keyword']", str(current_number))
                await page.fill("#captcha_code", "")

                if self.mode == "manual":
                    await page.focus("input#captcha_code")
                    while not await page.evaluate("window.__isTyping"):
                        await asyncio.sleep(0.1)
                    while await page.evaluate("window.__isTyping"):
                        await asyncio.sleep(0.1)
                    await asyncio.sleep(0.5)
                else:  # auto
                    try:
                        captcha_img = await page.wait_for_selector(".captcha-refresh > img")
                        captcha_src = await captcha_img.get_attribute("src")
                        url = "https://hatinh.edu.vn" + captcha_src
                        img_response = await page.request.get(url)
                        captcha_bytes = await img_response.body()
                        captcha_solution = await self.solve_captcha(captcha_bytes)
                        await page.fill("#captcha_code", captcha_solution)
                    except Exception as e:
                        print(f"Error fetching/solving CAPTCHA: {e}")
                        continue

                await page.click("button.btn.btn-primary")

                try:
                    await asyncio.wait_for(valid_response_received.wait(), timeout=1.0)
                    current_number += 1
                except asyncio.TimeoutError:
                    print("No valid response. Retrying...")

                if self.captured_data:
                    df = pd.DataFrame(self.captured_data, columns=self.columns)
                    df.to_csv("output.csv", encoding="utf-8-sig", index=False)

            await page.wait_for_timeout(3000)
            await browser.close()
        
        return df
