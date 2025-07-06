from flask import Flask, request, jsonify, send_file
from oauth2client.service_account import ServiceAccountCredentials
import gspread

app = Flask(__name__)

# Setup Google Sheets access
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

# Sheets
sheet_sentimen = client.open("telegrambotdat").worksheet("sentimen")
sheet_calendar = client.open("telegrambotdat").worksheet("calendar")
sheet_teknikal = client.open("telegrambotdat").worksheet("teknikal analisis")

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
    body = request.get_json()
    pair = body.get("pair")
    sentimen = body.get("sentimen")

    if not pair or not sentimen:
        return jsonify({"error": "Data 'pair' dan 'sentimen' diperlukan"}), 400

    records = sheet_sentimen.get_all_records()
    for i, row in enumerate(records):
        if row["pair"].strip().upper() == pair.strip().upper():
            sheet_sentimen.update_cell(i + 2, 2, sentimen)
            return jsonify({"status": "updated", "pair": pair})

    sheet_sentimen.append_row([pair, sentimen])
    return jsonify({"status": "inserted", "pair": pair})

# -----------------------------
# CALENDAR
# -----------------------------
@app.route("/get-calendar", methods=["GET"])
def get_calendar():
    data = sheet_calendar.get_all_records()
    return jsonify(data)

@app.route("/update-calendar", methods=["POST"])
def update_calendar():
    body = request.get_json()
    title = body.get("title")
    calendar = body.get("calendar")

    if not title or not calendar:
        return jsonify({"error": "Data 'title' dan 'calendar' diperlukan"}), 400

    records = sheet_calendar.get_all_records()
    for i, row in enumerate(records):
        if row["Title"].strip().upper() == title.strip().upper():
            sheet_calendar.update_cell(i + 2, 2, calendar)
            return jsonify({"status": "updated", "title": title})

    sheet_calendar.append_row([title, calendar])
    return jsonify({"status": "inserted", "title": title})

# -----------------------------
# TEKNIKAL ANALISIS
# -----------------------------
@app.route("/get-teknikal-m15", methods=["GET"])
def get_teknikal_m15():
    data = sheet_teknikal.get_all_records()
    result = [{"pair": row["pair"], "analisis": row["tf m15"]} for row in data if row.get("tf m15")]
    return jsonify(result)

@app.route("/get-teknikal-h1", methods=["GET"])
def get_teknikal_h1():
    data = sheet_teknikal.get_all_records()
    result = [{"pair": row["pair"], "analisis": row["tf h1"]} for row in data if row.get("tf h1")]
    return jsonify(result)

# -----------------------------
# OPENAPI SCHEMA
# -----------------------------
@app.route("/openapi-calendar.json")
def serve_openapi_calendar():
    return send_file("openapi_gpt_calendar_final.json", mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
