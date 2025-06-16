from Crawler import DiemThiCrawler as Crawler
from SortWorker import MonChuyenExporter as Exporter
import asyncio
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    crawler = Crawler(start=350001, end=350001, mode="manual", api_key=os.getenv("API_KEY_2CAPTCHA", ""))
    df = asyncio.run(crawler.run())

    output_excel = os.getenv("OUTPUT_EXCEL", "separated_by_mon_chuyen.xlsx")
    print(output_excel)
    exporter = Exporter(output_excel)
    exporter.process_and_export(df)

if __name__ == "__main__":
    main()