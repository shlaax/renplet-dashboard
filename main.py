from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Literal
import gspread
from google.oauth2.service_account import Credentials  # <- Dette var manglende
from datetime import datetime

app = FastAPI()

from fastapi.staticfiles import StaticFiles

# Mount statiske filer under / (så dashboard.html osv. serveres)
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# --- CORS setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve static files under /static ---
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

# --- Google Sheets setup ---
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPE)
client = gspread.authorize(creds)
SPREADSHEET_ID = "1vxXhq155OQEC-4ZsfqFmPJG1V8K8azA6eGRkt7WBMyI"
sheet = client.open_by_key(SPREADSHEET_ID)

# --- Pydantic models ---
class Bruger(BaseModel):
    navn: str
    kodeord: str
    rolle: Literal["medarbejder", "admin"]

class PlanEntry(BaseModel):
    opgave_navn: str
    medarbejder: str
    dato: str
    klokkeslæt: str
    varevogn: str
    status: Optional[str] = "i gang"
    notat: Optional[str] = ""

class PlanUpdate(BaseModel):
    opgave_navn: str
    medarbejder: str
    status: Optional[str] = None
    notat: Optional[str] = None
    klokkeslæt: Optional[str] = None

class Message(BaseModel):
    from_agent: Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    to_agent: Literal["TidsAgent", "OpgaveAgent", "LønAgent"]
    content: dict

# --- Agent logic ---
def opgave_agent(content):
    ws = sheet.worksheet("opgaver")
    ws.append_row([
        content["opgave_navn"],
        content["medarbejder"],
        content.get("status", "aktiv"),
        datetime.now().isoformat()
    ])

def tids_agent(content):
    ws = sheet.worksheet("timer")
    ws.append_row([
        content["medarbejder"],
        content["opgave"],
        content["timer"],
        datetime.now().isoformat()
    ])
    return {
        "from_agent": "TidsAgent",
        "to_agent": "LønAgent",
        "content": {"medarbejder": content["medarbejder"], "timer": content["timer"]}
    }

def lon_agent(content):
    belob = content["timer"] * 150
    ws = sheet.worksheet("løn")
    ws.append_row([
        content["medarbejder"],
        content["timer"],
        belob,
        datetime.now().isoformat()
    ])
    return {"lønbeløb": belob}

@app.post("/send")
async def send_message(message: Message):
    if message.to_agent == "OpgaveAgent":
        opgave_agent(message.content)
        return {"status": "oprettet"}
    elif message.to_agent == "TidsAgent":
        return tids_agent(message.content)
    elif message.to_agent == "LønAgent":
        return lon_agent(message.content)
    return {"status": "ok"}

# --- Bruger endpoints ---
@app.get("/brugere")
def hent_brugere():
    ws = sheet.worksheet("brugere")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    return [dict(zip(headers, row)) for row in rows]

@app.post("/brugere")
def opret_bruger(b: Bruger):
    ws = sheet.worksheet("brugere")
    ws.append_row([b.navn, b.kodeord, b.rolle])
    return {"status": "oprettet"}

@app.put("/brugere")
def opdater_bruger(b: Bruger):
    ws = sheet.worksheet("brugere")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    for idx, row in enumerate(rows, start=2):
        if row[0] == b.navn:
            ws.update_cell(idx, headers.index("kodeord") + 1, b.kodeord)
            ws.update_cell(idx, headers.index("rolle") + 1, b.rolle)
            return {"status": "opdateret"}
    raise HTTPException(status_code=404, detail="Bruger ikke fundet")

@app.delete("/brugere/{navn}")
def slet_bruger(navn: str):
    ws = sheet.worksheet("brugere")
    rows = ws.get_all_values()
    for idx, row in enumerate(rows[1:], start=2):
        if row[0] == navn:
            ws.delete_row(idx)
            return {"status": "slettet"}
    raise HTTPException(status_code=404, detail="Bruger ikke fundet")

# --- Plan endpoints ---
@app.get("/plan")
def hent_plan():
    ws = sheet.worksheet("plan")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    return [dict(zip(headers, row)) for row in rows]

@app.post("/plan")
def opret_plan(p: PlanEntry):
    ws = sheet.worksheet("plan")
    ws.append_row([
        p.opgave_navn, p.medarbejder, p.dato, p.klokkeslæt,
        p.varevogn, p.status, p.notat, datetime.now().isoformat()
    ])
    return {"status": "oprettet"}

@app.post("/plan/opdater")
def opdater_plan(u: PlanUpdate):
    ws = sheet.worksheet("plan")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    for idx, row in enumerate(rows, start=2):
        if row[0] == u.opgave_navn and row[1] == u.medarbejder:
            for key in ("status", "notat", "klokkeslæt"):
                val = getattr(u, key)
                if val is not None:
                    ws.update_cell(idx, headers.index(key) + 1, val)
            return {"status": "opdateret"}
    raise HTTPException(status_code=404, detail="Opgave ikke fundet")

# --- Medarbejder read-only endpoints ---
@app.get("/opgaver/{medarbejder}/status/{status}")
def hent_opgaver_status(medarbejder: str, status: str):
    ws = sheet.worksheet("opgaver")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    return [
        dict(zip(headers, row))
        for row in rows
        if row[1].strip().lower() == medarbejder.strip().lower()
        and row[2].strip().lower() == status.strip().lower()
    ]

@app.get("/timer/{medarbejder}")
def hent_timer(medarbejder: str):
    ws = sheet.worksheet("timer")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    return [
        dict(zip(headers, row))
        for row in rows
        if row[0].strip().lower() == medarbejder.strip().lower()
    ]

@app.get("/løn/{medarbejder}")
def hent_løn(medarbejder: str):
    ws = sheet.worksheet("løn")
    total = sum(float(r[2]) for r in ws.get_all_values()[1:] if r[0].strip().lower() == medarbejder.strip().lower())
    return {"medarbejder": medarbejder, "samlet_løn": total}

from pydantic import BaseModel
class Order(BaseModel):
    ordre_id: str
    kunde: str
    type: Literal["ve2", "own"]
    belob: float
    dato: str

@app.get("/orders")
def get_orders(type: Optional[str] = None):
    ws = sheet.worksheet("orders")
    rows = ws.get_all_values()
    headers = rows.pop(0)
    orders = [dict(zip(headers, r)) for r in rows]
    return [o for o in orders if type is None or o["type"] == type]

@app.post("/orders")
def create_order(o: Order):
    ws = sheet.worksheet("orders")
    ws.append_row([o.ordre_id, o.kunde, o.type, o.belob, o.dato, datetime.now().isoformat()])
    return {"status":"oprettet"}

