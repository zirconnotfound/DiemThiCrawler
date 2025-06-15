from Crawler import DiemThiCrawler as Crawler
from SortWorker import MonChuyenExporter as Exporter
import asyncio
import os

def main():
    crawler = Crawler(start=350001, end=350010, mode="manual", api_key=os.getenv("API_KEY_2CAPTCHA", ""))
    df = asyncio.run(crawler.run())

    output_excel = os.getenv("OUTPUT_EXCEL", "separated_by_mon_chuyen.xlsx")
    exporter = Exporter(output_excel)
    exporter.process_and_export(df)

if __name__ == "__main__":
    main()