from scripts.cnic_extractor import extract_cnic_fields

from flask import Flask, render_template, request, Response, jsonify
from dotenv import load_dotenv
from database.connection import create_connection
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

import os
import uuid
import json

load_dotenv()

app = Flask(__name__)
app.json.sort_keys = False

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

AZURE_ENDPOINT = os.environ.get("AZURE_DI_ENDPOINT")
AZURE_KEY = os.environ.get("AZURE_DI_KEY")

MODEL_IDS_ENV = os.environ.get("AZURE_DI_MODEL_IDS", "")
NAF_MODEL_IDS = [m.strip() for m in MODEL_IDS_ENV.split(",") if m.strip()]

@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    return jsonify({
        "status": "error",
        "message": "File size exceeds the 10 MB limit."
    }), 413

def save_uploaded_file(file):
    """Save file safely with unique name."""
    original_name = secure_filename(file.filename)
    extension = os.path.splitext(original_name)[1]

    filename = f"{uuid.uuid4()}{extension}"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    file.save(filepath)

    return filepath



@app.route("/")
def home():
    return render_template("index.html")

# ── Key mapping: frontend display labels → database column names ──────────
CNIC_KEY_MAP = {
    "Name": "name",
    "Father Name": "father_name",
    "CNIC Number": "cnic",
    "Date of Birth": "date_of_birth",
    "Gender": "gender",
    "Issue Date": "issue_date",
    "Expiry Date": "expiry_date",
    "QR Code": "qr_code",
    "CLI": "cli",
}

@app.route("/save-to-db/<form_type>", methods=["POST"])
def save_to_db(form_type):
    connection = create_connection()
    if not connection:
        return jsonify({"status": "error", "message": "Failed to connect to the database."}), 500

    cursor = connection.cursor()
    raw_data = request.get_json()

    if(raw_data is None):
        return jsonify({"status": "error", "message": "No data provided."}), 400
    
    try:
        if form_type == "cnic":

            # CNIC extraction returns an array [{ ... }] — unwrap it
            if isinstance(raw_data, list):
                if len(raw_data) == 0:
                    return jsonify({"status": "error", "message": "Empty CNIC data received."}), 400
                raw_data = raw_data[0]

            # Map display labels → DB columns and extract .value from each field
            row = {}
            for display_key, db_column in CNIC_KEY_MAP.items():
                field = raw_data.get(display_key, {})
                if isinstance(field, dict):
                    row[db_column] = field.get("value")
                else:
                    row[db_column] = field  # fallback if value is already flat

            # Get persistent count of existing CNIC records from the database
            cursor.execute("SELECT COUNT(*) FROM documents WHERE document_type = 'CNIC'")
            cnic_count = cursor.fetchone()[0]
            doc_id = f"DOC_CNIC_{cnic_count + 1:04d}"

            # Insert parent record
            document_query = """
                INSERT INTO documents (id, document_type, endpoint_url, extraction_status)
                VALUES (%s, %s, %s, %s)
            """
            doc_values = (
                doc_id,
                'CNIC',
                os.environ.get("AZURE_DI_ENDPOINT"),
                'COMPLETED'
            )
            cursor.execute(document_query, doc_values)

            # Map the generated document_id into the cnic row values
            row["document_id"] = doc_id

            columns = ", ".join(row.keys())
            placeholders = ", ".join(["%s"] * len(row))
            values = tuple(row.values())

            query = f"INSERT INTO cnic_data ({columns}) VALUES ({placeholders})"
            cursor.execute(query, values)
            connection.commit()

            return jsonify({"status": "success", "message": "CNIC data saved to database."}), 200

        elif form_type == "naf":
            if isinstance(raw_data, list):
                if len(raw_data) == 0:
                    return jsonify({"status": "error", "message": "Empty NAF data received."}), 400
                raw_data = raw_data[0]
        

            
        else:
            return jsonify({"status": "error", "message": f"Saving '{form_type}' to database is not yet supported."}), 400

    except Exception as e:
        connection.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()


@app.route("/upload/<form_type>", methods=["POST"])
def upload(form_type):
    import time
    import json

    # ── Read ALL request data here, inside request context ──────────────────
    if form_type == "cnic":
        pdf_file      = request.files.get("pdf")
        front_file    = request.files.get("front_image")
        back_file     = request.files.get("back_image")

        # Validate and save files immediately while request context is active
        if pdf_file and pdf_file.filename:
            if not pdf_file.filename.lower().endswith(".pdf"):
                return jsonify({"status": "error", "message": "Only PDF files are allowed."}), 400
            cnic_file_input = save_uploaded_file(pdf_file)
        elif front_file and front_file.filename and back_file and back_file.filename:
            front_path = save_uploaded_file(front_file)
            back_path  = save_uploaded_file(back_file)
            cnic_file_input = [front_path, back_path]
        else:
            return jsonify({"status": "error", "message": "Upload either a PDF or both front and back images."}), 400

    elif form_type == "naf":
        pdf_file = request.files.get("pdf")
        if not pdf_file or not pdf_file.filename:
            return jsonify({"status": "error", "message": "No PDF uploaded."}), 400
        if not pdf_file.filename.lower().endswith(".pdf"):
            return jsonify({"status": "error", "message": "Only PDF files are allowed."}), 400
        naf_filepath = save_uploaded_file(pdf_file)

    else:
        return jsonify({"status": "error", "message": f"Unsupported form type: {form_type}"}), 400
    # ────────────────────────────────────────────────────────────────────────

    def generate():
        try:
            # ---------------- CNIC ----------------
            if form_type == "cnic":
                yield json.dumps({"status": "progress", "message": "Analyzing structure..."}) + "\n"
                result_data = extract_cnic_fields(cnic_file_input, AZURE_ENDPOINT, AZURE_KEY)
                yield json.dumps({"status": "success", "data": result_data}) + "\n"

            # ---------------- NAF ----------------
            elif form_type == "naf":
                yield json.dumps({"status": "progress", "message": "Analyzing structure..."}) + "\n"
                
                from scripts.naf_extractor import extract_naf_fields
                result_data = extract_naf_fields(naf_filepath, AZURE_ENDPOINT, AZURE_KEY, NAF_MODEL_IDS)
                
                yield json.dumps({"status": "success", "data": result_data}) + "\n"

        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return Response(generate(), mimetype='application/x-ndjson')


@app.route("/testdb", methods=["GET"])
def test_db_connection():
    """Get a database connection."""
    connection = create_connection()
    if connection:
        connection.close()
        return jsonify({"status": "success", "message": "Database connection successful."}), 200
    return jsonify({"status": "error", "message": "Failed to connect to the database."}), 500

@app.route("/download-json", methods=["POST"])
def download_json():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    
    from flask import jsonify
    response = jsonify(data)
    response.headers["Content-Disposition"] = "attachment; filename=extracted_data.json"
    response.headers["Content-Type"] = "application/json"
    return response


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True,port=int(os.getenv('PORT', 5000)))