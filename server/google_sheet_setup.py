#!/usr/bin/env python3
import os, json, urllib.request
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

API_URL=os.getenv("ELECTRICAL_API_URL","http://127.0.0.1:8790").rstrip("/")
CREDS=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE","").strip()
SHEET_ID=os.getenv("GOOGLE_SHEET_ID","").strip()
SHARE_EMAIL=os.getenv("GOOGLE_SHARE_EMAIL","").strip()
TITLE=os.getenv("GOOGLE_SHEET_TITLE","Electrical Reading Logbook")
if not CREDS or not Path(CREDS).exists():
    raise SystemExit("GOOGLE_SERVICE_ACCOUNT_FILE is missing")
with urllib.request.urlopen(API_URL+"/api/config",timeout=15) as r:
    config=json.load(r)
sections=config["sections"]
flat=[]
for s in sections:
    for fid,label in s["fields"]:
        flat.append((s["id"],s["title"],fid,label))
scopes=["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]
client=gspread.authorize(Credentials.from_service_account_file(CREDS,scopes=scopes))
if SHEET_ID:
    book=client.open_by_key(SHEET_ID)
else:
    book=client.create(TITLE)
    SHEET_ID=book.id
    if SHARE_EMAIL:
        book.share(SHARE_EMAIL,perm_type="user",role="writer",notify=True)

def ws(name,rows=1000,cols=30):
    try:
        return book.worksheet(name)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=name,rows=rows,cols=cols)

raw=ws("RAW_READINGS",5000,len(flat)+9)
headers=["Submission ID","Date","Time","Submitted At","Electrician ID","Electrician Name","Shift","Device ID","Sheet Sync"]+[f"{section} - {label}" for _,section,_,label in flat]
raw.update(range_name="A1",values=[headers])
end=rowcol_to_a1(1,len(headers))
raw.format(f"A1:{end}",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True},"horizontalAlignment":"CENTER","wrapStrategy":"WRAP"})
try: raw.freeze(rows=1,cols=9)
except Exception: pass

fieldmap=ws("FIELD_MAP",200,6)
rows=[["No.","Section ID","Section","Field ID","Field Name","API Key"]]
for i,(sid,section,fid,label) in enumerate(flat,1): rows.append([i,sid,section,fid,label,f"{sid}.{fid}"])
fieldmap.clear(); fieldmap.update(range_name="A1",values=rows)
fieldmap.format("A1:F1",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True}})

users=ws("USERS",1000,7)
users.update(range_name="A1",values=[["Employee ID","Electrician Name","Shift","Status","Approved Device","Created At","Notes"]])
users.format("A1:G1",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True}})

for name,label in [("HOURLY_REPORT","Hour"),("DAILY_REPORT","Date"),("MONTHLY_REPORT","Month"),("YEARLY_REPORT","Year")]:
    sh=ws(name,1000,4)
    sh.update(range_name="A1",values=[[label,"Main Meter KWH Consumption","Reading Count","Notes"]])
    sh.format("A1:D1",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True}})

dash=ws("DASHBOARD",100,8)
dash.clear(); dash.update(range_name="A1",values=[["ELECTRICAL READING LOGBOOK - REPORT DASHBOARD"]]); dash.merge_cells("A1:H1")
dash.format("A1:H1",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True,"fontSize":14},"horizontalAlignment":"CENTER"})
dash.update(range_name="A3",values=[["KPI","Value"],["Required Fields",len(flat)],["Raw Reading Rows","=MAX(0,COUNTA(RAW_READINGS!A:A)-1)"],["Electricians","=MAX(0,COUNTA(USERS!A:A)-1)"],["Last Submission","=IFERROR(MAX(RAW_READINGS!D:D),\"\")"]],raw=False)

setup=ws("SETUP",50,2)
setup.clear(); setup.update(range_name="A1",values=[["Electrical Reading Google Sheet Setup",""],["Purpose","App submissions mirror to RAW_READINGS."],["Primary database","Server database remains source of truth."],["Backup","Daily server database backups retained 30 days."],["Required fields",len(flat)],["Important","Do not reorder RAW_READINGS columns after live sync starts."]])
setup.format("A1:B1",{"backgroundColor":{"red":0.082,"green":0.239,"blue":0.435},"textFormat":{"foregroundColor":{"red":1,"green":1,"blue":1},"bold":True}})
print("GOOGLE_SHEET_ID="+SHEET_ID)
print("GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/"+SHEET_ID)
print("FIELDS="+str(len(flat)))
