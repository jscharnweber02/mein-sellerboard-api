import os
from fastapi import FastAPI, Query
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime
import base64
import json

load_dotenv()
app = FastAPI()

# SERVICE_ACCOUNT aus Umgebungsvariable dekodieren
service_account_info = json.loads(
    base64.b64decode(os.getenv("GOOGLE_JSON")).decode("utf-8")
)
creds = service_account.Credentials.from_service_account_info(
    service_account_info, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
)

SHEET_ID = os.getenv("SHEET_ID")
RANGE = "Tabelle1!A1:Z1000"

def get_sheet_data():
    service = build("sheets", "v4", credentials=creds)
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=RANGE).execute()
    return result.get("values", [])

@app.get("/umsatz")
def get_umsatz(asin: str = Query(...), datum: str = Query(default=None)):
    values = get_sheet_data()
    if not values or len(values) < 2:
        return {"error": "Keine Daten"}

    headers = [h.replace('\ufeff', '').strip('"') for h in values[0]]
    data = values[1:]

    try:
        asin_col = headers.index("ASIN")
        date_col = headers.index("Date")
        sales_col = headers.index("SalesOrganic")
        ppc_col = headers.index("SalesPPC")
    except ValueError as e:
        return {"error": f"Spalte fehlt: {e}", "headers": headers}

    total = 0.0
    matched = 0

    for row in data:
        if len(row) <= max(asin_col, date_col, sales_col, ppc_col):
            continue
        try:
            if row[asin_col] != asin:
                continue

            # Datum konvertieren (deutsch → ISO)
            row_date_obj = datetime.strptime(row[date_col], "%d.%m.%Y").date()
            if datum:
                if row_date_obj.isoformat() != datum:
                    continue
            else:
                if row_date_obj != datetime.today().date():
                    continue

            sales_organic = float(row[sales_col].replace(",", "."))
            sales_ppc = float(row[ppc_col].replace(",", "."))
            total += sales_organic + sales_ppc
            matched += 1
        except Exception:
            continue

    return {
        "asin": asin,
        "datum": datum or datetime.today().isoformat(),
        "umsatz": round(total, 2),
        "zeilen_gefunden": matched
    }

@app.get("/debug")
def debug_headers():
    values = get_sheet_data()
    if not values:
        return {"error": "No data"}
    return {
        "headers_raw": values[0],
        "headers_cleaned": [h.replace('\ufeff', '').strip('"') for h in values[0]]
    }
