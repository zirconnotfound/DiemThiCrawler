import sqlite3
import pandas as pd

def export_tables_to_csv(db_path, tables):
    try:
        # 1. Establish connection to the database
        conn = sqlite3.connect(db_path)
        
        for table in tables:
            print(f"Exporting {table}...")
            
            # 2. Read the table into a DataFrame
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            
            # 3. Save to CSV
            output_file = f"{table}.csv"
            df.to_csv(output_file, index=False)
            
            print(f"Successfully saved to {output_file}")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

# Configuration
DB_NAME = "data/output.sqlite3"
TABLES_TO_EXPORT = ["diem_thi"]

if __name__ == "__main__":
    export_tables_to_csv(DB_NAME, TABLES_TO_EXPORT)