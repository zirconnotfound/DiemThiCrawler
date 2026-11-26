import csv
import sqlite3
from contextlib import closing


def export_tables_to_csv(db_path, tables):
    try:
        # closing() releases the connection; connect() itself may raise first
        with closing(sqlite3.connect(db_path)) as conn:
            for table in tables:
                print(f"Exporting {table}...")

                cursor = conn.execute(f'SELECT * FROM "{table}"')
                output_file = f"{table}.csv"
                with open(output_file, "w", encoding="utf-8", newline="") as csv_file:
                    writer = csv.writer(csv_file)
                    writer.writerow([d[0] for d in cursor.description])
                    writer.writerows(cursor)

                print(f"Successfully saved to {output_file}")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Configuration
DB_NAME = "data/output.sqlite3"
TABLES_TO_EXPORT = ["diem_thi"]

if __name__ == "__main__":
    export_tables_to_csv(DB_NAME, TABLES_TO_EXPORT)
