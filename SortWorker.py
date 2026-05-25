import os
import sqlite3

import pandas as pd


class MonChuyenExporter:
    def __init__(
        self,
        output_excel_path: str,
        database_path: str,
        table_name: str = "diem_thi",
        grouped: str = "Môn chuyên",
        sort_by: list = ["Tổng chuyên", "Điểm chuyên", "Tổng không chuyên"],
    ):
        self.sort_by = sort_by
        self.grouped = grouped
        self.output_excel_path = output_excel_path
        self.database_path = database_path
        self.table_name = table_name
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
        self.display_columns = [
            "Số báo danh",
            "Họ và tên",
            "Điểm Toán",
            "Điểm Anh",
            "Điểm Văn",
            "Điểm ƯT",
            "Điểm KK",
            "Tổng không chuyên",
            "Môn chuyên",
            "Điểm chuyên",
            "Tổng chuyên",
            "Ghi chú",
        ]
        self.column_map = dict(zip(self.db_columns, self.display_columns))

    def _load_dataframe_from_database(self) -> pd.DataFrame:
        if not os.path.exists(self.database_path):
            return pd.DataFrame(columns=self.display_columns)

        with sqlite3.connect(self.database_path) as connection:
            query = f'SELECT * FROM "{self.table_name}"'
            df = pd.read_sql_query(query, connection)

        return df.rename(columns=self.column_map)

    def process_and_export_from_database(self):
        df = self._load_dataframe_from_database()
        self.process_and_export(df)

    def process_and_export(self, df):
        # Defensive: handle empty dataframe
        if df is None or df.empty:
            print("No data to export. Creating empty workbook.")
            with pd.ExcelWriter(self.output_excel_path, engine='openpyxl') as writer:
                pd.DataFrame(columns=self.display_columns).to_excel(writer, sheet_name='NoData', index=False)
            print(f"Data has been exported to '{self.output_excel_path}'")
            return

        # If the grouping column doesn't exist, treat whole DF as one group
        try:
            grouped = df.groupby(self.grouped)
        except Exception:
            grouped = [(None, df)]

        written_any = False
        with pd.ExcelWriter(self.output_excel_path, engine='openpyxl') as writer:
            for mon_chuyen, group in grouped:
                try:
                    # Only sort by columns that actually exist in this group
                    available_sort_cols = [c for c in self.sort_by if c in group.columns]
                    if available_sort_cols:
                        sorted_group = group.sort_values(by=available_sort_cols, ascending=False)
                    else:
                        sorted_group = group

                    sheet_name = (str(mon_chuyen)[:31] if mon_chuyen is not None else 'All')
                    sorted_group.to_excel(writer, sheet_name=sheet_name, index=False)
                    written_any = True
                except Exception as e:
                    print(f"Skipping group '{mon_chuyen}': {e}")

            # Ensure at least one visible sheet exists (openpyxl requires it)
            if not written_any:
                df.head(0).to_excel(writer, sheet_name='Sheet1', index=False)

        print(f"Data has been exported to '{self.output_excel_path}'")