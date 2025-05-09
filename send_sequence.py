import requests
import time

URL = "http://localhost:8000/send"

# 1. OpgaveAgent
r1 = requests.post(URL, json={
    "from_agent": "OpgaveAgent",
    "to_agent": "OpgaveAgent",
    "content": {
        "opgave_navn": "Rengør showroom",
        "medarbejder": "Hamse",
        "status": "aktiv"
    }
})
print("OpgaveAgent:", r1.status_code, r1.text)
time.sleep(1)

# 2. TidsAgent
r2 = requests.post(URL, json={
    "from_agent": "TidsAgent",
    "to_agent": "TidsAgent",
    "content": {
        "medarbejder": "Hamse",
        "opgave": "Rengør showroom",
        "timer": 3.0
    }
})
print("TidsAgent:", r2.status_code, r2.text)
time.sleep(1)

# 3. LønAgent
r3 = requests.post(URL, json={
    "from_agent": "TidsAgent",
    "to_agent": "LønAgent",
    "content": {
        "medarbejder": "Hamse",
        "timer": 3.0
    }
})
print("LønAgent:", r3.status_code, r3.text)
