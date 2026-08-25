#!/usr/bin/env python3
import os, json, sqlite3
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

DB_PATH=Path(os.getenv("DB_PATH",Path.home()/"electrical-reading/backend/data/readings.db"))
CREDS=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE","").strip()
SHEET_ID=os.getenv("GOOGLE_SHEET_ID","").strip()
if not CREDS or not Path(CREDS).exists() or not SHEET_ID:
    raise SystemExit("Google Sheet credentials or GOOGLE_SHEET_ID missing")
scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
client=gspread.authorize(Credentials.from_service_account_file(CREDS,scopes=scopes))
book=client.open_by_key(SHEET_ID)
raw=book.worksheet("RAW_READINGS")
fieldmap=book.worksheet("FIELD_MAP")
field_rows=fieldmap.get_all_values()[1:]
field_pairs=[(r[5],f"{r[2]} - {r[4]}") for r in field_rows if len(r)>=6]
con=sqlite3.connect(DB_PATH); con.row_factory=sqlite3.Row
rows=con.execute("SELECT * FROM submissions WHERE sheet_synced=0 ORDER BY submitted_at LIMIT 200").fetchall()
for r in rows:
    values=json.loads(r["values_json"])
    out=[r["id"],r["local_date"],r["local_time"],r["submitted_at"],r["employee_id"],r["electrician_name"],r["shift"],r["device_id"],"YES"]+[values.get(k,"") for k,_ in field_pairs]
    raw.append_row(out,value_input_option="RAW")
    con.execute("UPDATE submissions SET sheet_synced=1 WHERE id=?",(r["id"],)); con.commit()

# Refresh USERS tab from server DB
users=book.worksheet("USERS")
user_rows=con.execute("SELECT employee_id,name,shift,active,created_at,id FROM users WHERE role='electrician' ORDER BY employee_id").fetchall()
all_devices=con.execute("SELECT user_id,device_name,status FROM devices WHERE status='approved' ORDER BY approved_at DESC").fetchall()
latest_device={}
for d in all_devices:
    latest_device.setdefault(d["user_id"],d["device_name"] or "Approved device")
users.clear(); users.update(range_name="A1",values=[["Employee ID","Electrician Name","Shift","Status","Approved Device","Created At","Notes"]]+[[u["employee_id"],u["name"],u["shift"],"ACTIVE" if u["active"] else "DISABLED",latest_device.get(u["id"],""),u["created_at"],""] for u in user_rows])

# Build consumption summaries from MAIN METER KWH in chronological order
subs=con.execute("SELECT submitted_at,values_json FROM submissions ORDER BY submitted_at ASC").fetchall()
series=[]
for r in subs:
    v=json.loads(r["values_json"]).get("main_meter.kwh")
    if v is not None:
        series.append((r["submitted_at"],float(v)))
from datetime import datetime
for sheet_name,period in [("HOURLY_REPORT","hourly"),("DAILY_REPORT","daily"),("MONTHLY_REPORT","monthly"),("YEARLY_REPORT","yearly")]:
    grouped={}; counts={}; prev=None
    for ts,val in series:
        t=datetime.fromisoformat(ts)
        diff=None if prev is None else val-prev
        prev=val
        if diff is None or diff<0: continue
        if period=="hourly": key=t.strftime("%Y-%m-%d %H:00")
        elif period=="daily": key=t.strftime("%Y-%m-%d")
        elif period=="monthly": key=t.strftime("%Y-%m")
        else: key=t.strftime("%Y")
        grouped[key]=grouped.get(key,0)+diff; counts[key]=counts.get(key,0)+1
    ws=book.worksheet(sheet_name)
    header=ws.row_values(1) or [period.title(),"Main Meter KWH Consumption","Reading Count","Notes"]
    ws.clear(); ws.update(range_name="A1",values=[header]+[[k,round(grouped[k],3),counts[k],""] for k in sorted(grouped)])
print(f"Synced {len(rows)} new submission(s)")
