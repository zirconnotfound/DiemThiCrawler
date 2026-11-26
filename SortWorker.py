import math
import os
import re
import sqlite3
from contextlib import closing

from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, Side

_THIN = Side(style="thin")
_HEADER_FONT = Font(bold=True)
_HEADER_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="top")
# Characters Excel does not allow in sheet names
_INVALID_SHEET_CHARS = re.compile(r"[\\/*?:\[\]]")


def _to_number(value):
    """Return value as int/float, or None if it is not a number."""
    for convert in (int, float):
        try:
            number = convert(value)
        except (TypeError, ValueError):
            continue
        return None if isinstance(number, float) and math.isnan(number) else number
    return None


class MonChuyenExporter:
    def __init__(
        self,
        output_excel_path: str,
        database_path: str,
        table_name: str = "diem_thi",
        grouped: str = "Môn chuyên",
        sort_by: tuple = ("Tổng chuyên", "Điểm chuyên", "Tổng không chuyên"),
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

    def _load_rows_from_database(self) -> tuple:
        if not os.path.exists(self.database_path):
            return self.display_columns, []

        with closing(sqlite3.connect(self.database_path)) as connection:
            cursor = connection.execute(f'SELECT * FROM "{self.table_name}"')
            columns = [self.column_map.get(d[0], d[0]) for d in cursor.description]
            return columns, cursor.fetchall()

    def process_and_export_from_database(self):
        columns, rows = self._load_rows_from_database()
        self.process_and_export(columns, rows)

    def _group_rows(self, columns: list, rows: list) -> list:
        # If the grouping column doesn't exist, treat all rows as one group
        if self.grouped not in columns:
            return [("All", rows)]

        index = columns.index(self.grouped)
        groups = {}
        for row in rows:
            key = "All" if row[index] is None else str(row[index])
            groups.setdefault(key, []).append(row)
        return sorted(groups.items())

    def _sort_rows(self, columns: list, rows: list) -> list:
        """Highest scores first; rows with 'Vắng' go to the bottom.

        Numeric values in the sort columns are written as numbers, while
        any other text (such as 'Vắng') is kept as it is.
        """
        indexes = [columns.index(c) for c in self.sort_by if c in columns]
        if not indexes:
            return rows

        keyed = []
        for row in rows:
            output = list(row)
            absent = False
            scores = []
            for i in indexes:
                number = _to_number(row[i])
                if number is None:
                    absent = absent or str(row[i]).strip() == "Vắng"
                    scores.append((True, 0))  # non-numeric ranks after numbers
                else:
                    output[i] = number
                    scores.append((False, -number))
            keyed.append(((absent, scores), output))

        keyed.sort(key=lambda item: item[0])
        return [output for _, output in keyed]

    def _write_sheet(self, workbook: Workbook, title: str, columns: list, rows: list):
        title = _INVALID_SHEET_CHARS.sub("_", title)[:31] or "All"
        sheet = workbook.create_sheet(title)

        header = []
        for name in columns:
            cell = WriteOnlyCell(sheet, value=name)
            cell.font = _HEADER_FONT
            cell.border = _HEADER_BORDER
            cell.alignment = _HEADER_ALIGNMENT
            header.append(cell)
        sheet.append(header)

        for row in rows:
            sheet.append(row)

    def process_and_export(self, columns: list, rows: list):
        workbook = Workbook(write_only=True)

        if not rows:
            print("No data to export. Creating empty workbook.")
            self._write_sheet(workbook, "NoData", columns, [])
        else:
            for name, group in self._group_rows(columns, rows):
                self._write_sheet(workbook, name, columns, self._sort_rows(columns, group))

        workbook.save(self.output_excel_path)
        print(f"Data has been exported to '{self.output_excel_path}'")


if __name__ == "__main__":
    output_excel = os.getenv("OUTPUT_FILE", "output.xlsx")
    database_path = os.path.join("data", "output.sqlite3")
    table_name = "diem_thi"

    exporter = MonChuyenExporter(
        output_excel_path=output_excel,
        database_path=database_path,
        table_name=table_name,
    )
    exporter.process_and_export_from_database()
