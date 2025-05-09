from fastapi import FastAPI
from pydantic import BaseModel
from typing import Literal
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS (så dine web-clients kan tilgå API’et)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Google Sheets‐opsætning
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file(
    "/etc/secrets/credentials.json",  # Secret File du har uploadet i Render
    scopes=SCOPE
)
client = gspread.authorize(creds)

SPREADSHEET_ID = "1vxXhq155OQEC-4ZsfqFmPJG1V8K8azA6eGRkt7WBMyI"
sheet = client.open_by_key(SPREADSHEET_ID)

# Besked‐model til “send” endpoint
class Message(BaseModel):
    from_agent: Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    to_agent: Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    content: dict

# Agent‐funktioner
def opgave_agent(content):
    ws = sheet.worksheet("opgaver")
    ws.append_row([
        content.get("opgave_navn", "Ukendt"),
        content.get("medarbejder", "Ukendt"),
        content.get("status", "aktiv"),
        datetime.now().isoformat()
    ])

def tids_agent(content):
    ws = sheet.worksheet("timer")
    ws.append_row([
        content.get("medarbejder", "Ukendt"),
        content.get("opgave", "Ukendt"),
        content.get("timer", 0),
        datetime.now().isoformat()
    ])
    # Videre til LønAgent
    return {
        "from_agent": "TidsAgent",
        "to_agent": "LønAgent",
        "content": {
            "medarbejder": content["medarbejder"],
            "timer": content["timer"]
        }
    }

def lon_agent(content):
    belob = content["timer"] * 150  # timesats
    ws = sheet.worksheet("løn")
    ws.append_row([
        content.get("medarbejder", "Ukendt"),
        content.get("timer", 0),
        belob,
        datetime.now().isoformat()
    ])
    return {"lønbeløb": belob}

# “send” endpoint: modtag beskeder internt mellem agenter
@app.post("/send")
async def send_message(message: Message):
    if message.to_agent == "OpgaveAgent":
        opgave_agent(message.content)
        return {"status": "opgave tilføjet"}
    elif message.to_agent == "TidsAgent":
        return tids_agent(message.content)
    elif message.to_agent == "LønAgent":
        return lon_agent(message.content)
    return {"status": "ukendt agent"}

# Hent alle opgaver for en medarbejder
@app.get("/opgaver/{medarbejder}")
def hent_opgaver(medarbejder: str):
    ws = sheet.worksheet("opgaver")
    rows = ws.get_all_values()
    headers = rows[0]
    return [
        dict(zip(headers, row))
        for row in rows[1:]
        if row[1].strip().lower() == medarbejder.strip().lower()
    ]

# Marker opgave som afsluttet
@app.post("/opgaver/afslut")
def afslut_opgave(data: dict):
    medarbejder = data.get("medarbejder", "").strip().lower()
    opgavenavn = data.get("opgave_navn", "").strip().lower()

    ws = sheet.worksheet("opgaver")
    rows = ws.get_all_values()

    for i, row in enumerate(rows[1:], start=2):
        navn = row[0].strip().lower()
        person = row[1].strip().lower()
        if navn == opgavenavn and person == medarbejder:
            ws.update_cell(i, 3, "færdig")
            return {"status": "opgave opdateret", "række": i}
    return {"status": "opgave ikke fundet"}

# Hent timelog for en medarbejder
@app.get("/timer/{medarbejder}")
def hent_timer(medarbejder: str):
    ws = sheet.worksheet("timer")
    rows = ws.get_all_values()
    headers = rows[0]
    return [
        dict(zip(headers, row))
        for row in rows[1:]
        if row[0].strip().lower() == medarbejder.strip().lower()
    ]

# Hent samlet løn for en medarbejder
@app.get("/løn/{medarbejder}")
def hent_løn(medarbejder: str):
    ws = sheet.worksheet("løn")
    rows = ws.get_all_values()
    total = 0
    for row in rows[1:]:
        if row[0].strip().lower() == medarbejder.strip().lower():
            try:
                total += float(row[2])
            except ValueError:
                continue
    return {"medarbejder": medarbejder, "samlet_løn": total}

# Hent opgaver efter status (aktiv/færdig)
@app.get("/opgaver/{medarbejder}/status/{status}")
def hent_opgaver_efter_status(medarbejder: str, status: str):
    ws = sheet.worksheet("opgaver")
    rows = ws.get_all_values()
    headers = rows[0]
    return [
        dict(zip(headers, row))
        for row in rows[1:]
        if row[1].strip().lower() == medarbejder.strip().lower()
        and row[2].strip().lower() == status.strip().lower()
    ]
