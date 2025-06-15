import pandas as pd

class MonChuyenExporter:
    def __init__(self, output_excel_path: str):
        self.output_excel_path = output_excel_path

    def process_and_export(self, df):
        grouped = df.groupby("Môn chuyên")

        with pd.ExcelWriter(self.output_excel_path) as writer:
            for mon_chuyen, group in grouped:
                sorted_group = group.sort_values(
                    by=["Tổng chuyên", "Điểm chuyên", "Tổng không chuyên"],
                    ascending=[False, False, False]
                )
                sheet_name = str(mon_chuyen)[:31]
                sorted_group.to_excel(writer, sheet_name=sheet_name, index=False)

        print(f"Data has been exported to '{self.output_excel_path}'")
