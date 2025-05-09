import os
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Literal
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- Servér alt i static/ som filer og HTML (index.html som default) ---
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# --- CORS (så dine web-clients kan ramme API’et) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Google Sheets opsætning med Secret File eller ENV fallback ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]

def load_credentials():
    secret_path = "/etc/secrets/credentials.json"
    if os.path.exists(secret_path):
        print(f"[INFO] Loader credentials fra Secret File: {secret_path}")
        return Credentials.from_service_account_file(secret_path, scopes=SCOPE)
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if raw:
        print("[INFO] Loader credentials fra env GOOGLE_CREDENTIALS")
        info = json.loads(raw)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n")
        return Credentials.from_service_account_info(info, scopes=SCOPE)
    raise RuntimeError("Ingen Google credentials fundet (fil eller env var).")

creds = load_credentials()
client = gspread.authorize(creds)

SPREADSHEET_ID = "1vxXhq155OQEC-4ZsfqFmPJG1V8K8azA6eGRkt7WBMyI"
sheet = client.open_by_key(SPREADSHEET_ID)

# --- Models & agent-funktioner ---
class Message(BaseModel):
    from_agent: Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    to_agent:   Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    content:    dict

def opgave_agent(content):
    ws = sheet.worksheet("opgaver")
    ws.append_row([
        content.get("opgave_navn","Ukendt"),
        content.get("medarbejder","Ukendt"),
        content.get("status","aktiv"),
        datetime.now().isoformat()
    ])

def tids_agent(content):
    ws = sheet.worksheet("timer")
    ws.append_row([
        content.get("medarbejder","Ukendt"),
        content.get("opgave","Ukendt"),
        content.get("timer",0),
        datetime.now().isoformat()
    ])
    return {
        "from_agent":"TidsAgent",
        "to_agent":"LønAgent",
        "content":{"medarbejder":content["medarbejder"],"timer":content["timer"]}
    }

def lon_agent(content):
    belob = content["timer"]*150
    ws = sheet.worksheet("løn")
    ws.append_row([
        content.get("medarbejder","Ukendt"),
        content.get("timer",0),
        belob,
        datetime.now().isoformat()
    ])
    return {"lønbeløb":belob}

# --- API endpoints ---
@app.post("/send")
async def send_message(message: Message):
    if message.to_agent=="OpgaveAgent":
        opgave_agent(message.content)
        return {"status":"opgave tilføjet"}
    if message.to_agent=="TidsAgent":
        return tids_agent(message.content)
    if message.to_agent=="LønAgent":
        return lon_agent(message.content)
    return {"status":"ukendt agent"}

@app.get("/opgaver/{medarbejder}")
def hent_opgaver(medarbejder:str):
    ws = sheet.worksheet("opgaver"); rows=ws.get_all_values(); headers=rows[0]
    return [
        dict(zip(headers,row))
        for row in rows[1:]
        if row[1].strip().lower()==medarbejder.strip().lower()
    ]

@app.post("/opgaver/afslut")
def afslut_opgave(data:dict):
    medarbejder=data.get("medarbejder","").strip().lower()
    opgavenavn=data.get("opgave_navn","").strip().lower()
    ws=sheet.worksheet("opgaver"); rows=ws.get_all_values()
    for i,row in enumerate(rows[1:],start=2):
        if row[0].strip().lower()==opgavenavn and row[1].strip().lower()==medarbejder:
            ws.update_cell(i,3,"færdig")
            return {"status":"opgave opdateret","række":i}
    return {"status":"opgave ikke fundet"}

@app.get("/timer/{medarbejder}")
def hent_timer(medarbejder:str):
    ws=sheet.worksheet("timer"); rows=ws.get_all_values(); headers=rows[0]
    return [
        dict(zip(headers,row))
        for row in rows[1:]
        if row[0].strip().lower()==medarbejder.strip().lower()
    ]

@app.get("/løn/{medarbejder}")
def hent_løn(medarbejder:str):
    ws=sheet.worksheet("løn"); rows=ws.get_all_values()
    total=0
    for row in rows[1:]:
        if row[0].strip().lower()==medarbejder.strip().lower():
            try: total+=float(row[2])
            except: pass
    return {"medarbejder":medarbejder,"samlet_løn":total}

@app.get("/opgaver/{medarbejder}/status/{status}")
def hent_opgaver_efter_status(medarbejder:str,status:str):
    ws=sheet.worksheet("opgaver"); rows=ws.get_all_values(); headers=rows[0]
    return [
        dict(zip(headers,row))
        for row in rows[1:]
        if row[1].strip().lower()==medarbejder.strip().lower() and row[2].strip().lower()==status.strip().lower()
    ]
