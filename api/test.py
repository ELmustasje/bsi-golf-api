import os
import pandas as pd


def read_excel_files(directory):
    attendees = []
    for filename in os.listdir(directory):
        if filename.endswith(".xlsx"):
            file_path = os.path.join(directory, filename)

            # Read the Excel file
            df = pd.read_excel(file_path, header=None)

            # Find the start and end indices dynamically
            start_index = df[df[0].str.contains("Deltar", na=False)].index[0] + 2
            # Skip the "Navn" row
            # Stop before "Ikke svart" or "Kommer ikke"
            end_index = df[
                df[0].str.contains("Ikke svart|Kommer ikke", na=False)
            ].index[0]

            # Extract the names
            for i in df.iloc[start_index:end_index, 0].dropna().tolist():
                attendees.append(i)

    return attendees


a = read_excel_files("./xlsx_files")
print(a)
