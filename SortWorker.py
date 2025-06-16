import pandas as pd

class MonChuyenExporter:
    def __init__(self, output_excel_path: str, grouped: str = "Môn chuyên", sort_by: list = ["Tổng điểm xét tuyển vào trường THPT chuyên Hà Tĩnh", "Điểm môn chuyên", "Tổng điểm xét tuyến vào trường THPT không chuyên"]):
        self.sort_by = sort_by
        self.grouped = grouped
        self.output_excel_path = output_excel_path

    def process_and_export(self, df):
        grouped = df.groupby(self.grouped)

        with pd.ExcelWriter(self.output_excel_path, engine='openpyxl') as writer:
            for mon_chuyen, group in grouped:
                sorted_group = group.sort_values(
                    by=self.sort_by,
                    ascending=False
                )
                sheet_name = str(mon_chuyen)[:31]
                sorted_group.to_excel(writer, sheet_name=sheet_name, index=False)


        print(f"Data has been exported to '{self.output_excel_path}'")