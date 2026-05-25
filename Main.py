from Crawler import DiemThiCrawler as Crawler
from SortWorker import MonChuyenExporter as Exporter
import asyncio
import os
from dotenv import load_dotenv

def main():
    load_dotenv()
    # Read numeric configuration from environment (fall back to defaults)
    start = int(os.getenv("START", "350001"))
    end = int(os.getenv("END", "350999"))
    max_captcha_attempts = int(os.getenv("MAX_CAPTCHA_ATTEMPTS", "7"))
    max_rounds = int(os.getenv("MAX_ROUNDS", "3"))
    response_timeout = float(os.getenv("RESPONSE_TIMEOUT", "1.0"))
    round_pause_ms = int(os.getenv("ROUND_PAUSE_MS", "1000"))
    final_wait_ms = int(os.getenv("FINAL_WAIT_MS", "3000"))
    min_delay = float(os.getenv("MIN_DELAY", "1.0"))
    max_delay = float(os.getenv("MAX_DELAY", "2.0"))

    crawler = Crawler(
        start=start,
        end=end,
        max_captcha_attempts=max_captcha_attempts,
        max_rounds=max_rounds,
        response_timeout=response_timeout,
        round_pause_ms=round_pause_ms,
        final_wait_ms=final_wait_ms,
        min_delay=min_delay,
        max_delay=max_delay,
    )

    # Run the crawler to populate the database
    asyncio.run(crawler.run())

    output_excel = os.getenv("OUTPUT_FILE", "output.xlsx")
    exporter = Exporter(
        output_excel_path=output_excel,
        database_path=crawler.database_path,
        table_name=crawler.table_name,
    )
    exporter.process_and_export_from_database()

if __name__ == "__main__":
    main()