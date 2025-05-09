import gspread
from google.oauth2.service_account import Credentials

# Konfiguration
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
client = gspread.authorize(creds)

# Indsæt dit eget Google Sheet ID her:
SPREADSHEET_ID = "1vxXhq155OQEC-4ZsfqFmPJG1V8K8azA6eGRkt7WBMyI"
sheet = client.open_by_key(SPREADSHEET_ID)

# Test: skriv noget i fanen 'timer'
worksheet = sheet.worksheet("timer")
worksheet.append_row(["Hamse", "Opgave 1", 3.5, "2025-05-04"])
print("✅ Skrevet til Google Sheet!")
