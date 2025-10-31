from flask import Flask, request, jsonify, send_file
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import re

app = Flask(__name__)

# -----------------------------
# Google Sheets auth
# -----------------------------
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Buka workbook & worksheets
WB_NAME = "telegrambotdat"
sheet_sentimen = client.open(WB_NAME).worksheet("sentimen")
sheet_calendar = client.open(WB_NAME).worksheet("calendar")
sheet_teknikal = client.open(WB_NAME).worksheet("teknikal analisis")

# -----------------------------
# Helpers (normalisation)
# -----------------------------
NBSP = "\u00A0"
ZWS = "\u200B"
LRM = "\u200E"
RLM = "\u200F"

def norm_pair(s: str) -> str:
    """Normalisasi pair untuk perbandingan: buang ruang eksotik, hilangkan semua whitespace, uppercase, samakan slash."""
    if not s:
        return ""
    s = s.replace(NBSP, " ").replace(ZWS, "").replace(LRM, "").replace(RLM, "")
    s = s.replace("／", "/").replace("\\", "/")
    # buang SEMUA whitespace (space, tab, dll)
    s = re.sub(r"\s+", "", s)
    return s.upper()

def clean_pair_display(s: str) -> str:
    """Nilai cantik untuk dipaparkan/disimpan di kolum A (contoh: EUR/USD)."""
    if not s:
        return ""
    s = s.replace(NBSP, " ").replace(ZWS, "").replace(LRM, "").replace(RLM, "")
    s = s.replace("／", "/").replace("\\", "/")
    s = re.sub(r"\s+", "", s)  # EUR / USD -> EUR/USD
    return s.upper()

def norm_title(s: str) -> str:
    """Untuk calendar: trim & jadikan spasi tunggal + uppercase (kita tak buang spasi di tengah)."""
    if not s:
        return ""
    s = s.replace(NBSP, " ").replace(ZWS, "").replace(LRM, "").replace(RLM, "")
    s = re.sub(r"\s+", " ", s.strip())
    return s.upper()

def ensure_sentimen_header():
    vals = sheet_sentimen.get_all_values()
    if not vals:
        sheet_sentimen.update("A1:B1", [["pair", "sentimen"]])

def ensure_calendar_header():
    vals = sheet_calendar.get_all_values()
    if not vals:
        sheet_calendar.update("A1:B1", [["Title", "calendar"]])

@app.route("/")
def home():
    return "✅ API aktif: sentimen + calendar + teknikal + openapi json"

# -----------------------------
# SENTIMEN
# -----------------------------
@app.route("/get-sentimen", methods=["GET"])
def get_sentimen():
    data = sheet_sentimen.get_all_records()
    return jsonify(data)

@app.route("/update-sentimen", methods=["POST"])
def update_sentimen():
    body = request.get_json(silent=True) or {}
    pair_raw = (body.get("pair") or "").strip()
    sentimen = (body.get("sentimen") or "").strip()
    if not pair_raw or not sentimen:
        return jsonify({"error": "Data 'pair' dan 'sentimen' diperlukan"}), 400

    ensure_sentimen_header()

    pair_key = norm_pair(pair_raw)
    colA = sheet_sentimen.col_values(1)  # termasuk header
    data_pairs_norm = [norm_pair(v) for v in colA[1:]]  # skip header row

    if pair_key in data_pairs_norm:
        row = 2 + data_pairs_norm.index(pair_key)
        # overwrite A & B (A dibersihkan ke format konsisten, B update sentimen)
        sheet_sentimen.batch_update([
            {"range": f"A{row}", "values": [[clean_pair_display(pair_raw)]]},
            {"range": f"B{row}", "values": [[sentimen]]},
        ])
        return jsonify({"status": "updated", "pair": clean_pair_display(pair_raw)})
    else:
        # baris baru (pair betul-betul belum wujud)
        sheet_sentimen.append_row([clean_pair_display(pair_raw), sentimen])
        return jsonify({"status": "inserted", "pair": clean_pair_display(pair_raw)})

@app.route("/dedupe-sentimen", methods=["POST"])
def dedupe_sentimen():
    """Sekali-jalan untuk buang duplikat: kekalkan baris paling bawah (terkini) bagi setiap pair."""
    vals = sheet_sentimen.get_all_values()
    if not vals:
        return jsonify({"status": "ok", "msg": "sheet kosong"})
    header, rows = vals[0], vals[1:]

    latest = {}
    for r in rows:
        p_raw = r[0] if len(r) > 0 else ""
        s_txt = r[1] if len(r) > 1 else ""
        key = norm_pair(p_raw)
        if not key:
            continue
        latest[key] = [clean_pair_display(p_raw), s_txt]  # overwrite => simpan paling bawah

    out = [header]
    for _, rec in sorted(latest.items()):
        out.append(rec)

    sheet_sentimen.clear()
    sheet_sentimen.update(f"A1:B{len(out)}", out)
    return jsonify({"status": "ok", "msg": f"dedupe siap: {len(rows)}→{len(out)-1} baris"})

# -----------------------------
# CALENDAR
# -----------------------------
@app.route("/get-calendar", methods=["GET"])
def get_calendar():
    data = sheet_calendar.get_all_records()
    return jsonify(data)

@app.route("/update-calendar", methods=["POST"])
def update_calendar():
    body = request.get_json(silent=True) or {}
    title_raw = (body.get("title") or "").strip()
    calendar = (body.get("calendar") or "").strip()

    if not title_raw or not calendar:
        return jsonify({"error": "Data 'title' dan 'calendar' diperlukan"}), 400

    ensure_calendar_header()

    key = norm_title(title_raw)
    colA = sheet_calendar.col_values(1)  # termasuk header
    titles_norm = [norm_title(v) for v in colA[1:]]

    if key in titles_norm:
        row = 2 + titles_norm.index(key)
        # kemaskan Title (jadikan spasi tunggal + uppercase)
        sheet_calendar.batch_update([
            {"range": f"A{row}", "values": [[norm_title(title_raw)]]},
            {"range": f"B{row}", "values": [[calendar]]},
        ])
        return jsonify({"status": "updated", "title": title_raw})
    else:
        sheet_calendar.append_row([norm_title(title_raw), calendar])
        return jsonify({"status": "inserted", "title": title_raw})

# -----------------------------
# TEKNIKAL ANALISIS
# -----------------------------
@app.route("/get-teknikal-m15", methods=["GET"])
def get_teknikal_m15():
    data = sheet_teknikal.get_all_records()
    result = [{"pair": row.get("pair"), "analisis": row.get("tf m15")}
              for row in data if row.get("tf m15")]
    return jsonify(result)

@app.route("/get-teknikal-h1", methods=["GET"])
def get_teknikal_h1():
    data = sheet_teknikal.get_all_records()
    result = [{"pair": row.get("pair"), "analisis": row.get("tf h1")}
              for row in data if row.get("tf h1")]
    return jsonify(result)

# -----------------------------
# OPENAPI SCHEMA
# -----------------------------
@app.route("/openapi-calendar.json")
def serve_openapi_calendar():
    return send_file("openapi_gpt_calendar_final.json", mimetype="application/json")

if __name__ == "__main__":
    # Flask default port 3000 (Render)
    app.run(host="0.0.0.0", port=3000)
