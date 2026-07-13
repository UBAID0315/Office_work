from scripts.cnic_extractor import extract_cnic_fields

from flask import Flask, render_template, request, Response
from dotenv import load_dotenv
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


def extract_fields(file_input, form_type):
    print(f"\nProcessing {form_type}")

    try:
        if form_type == "cnic":
            result = extract_cnic_fields(
                file_input,
                AZURE_ENDPOINT,
                AZURE_KEY
            )

            return {
                "status": "success",
                "message": "CNIC processed successfully.",
                "data": result
            }

        elif form_type == "naf":
            result = extract_naf_fields(
                file_input,
                AZURE_ENDPOINT,
                AZURE_KEY,
                NAF_MODEL_IDS
            )

            return {
                "status": "success",
                "message": "NAF processed successfully.",
                "data": result
            }

        return {
            "status": "error",
            "message": f"Unsupported form type: {form_type}"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.route("/")
def home():
    return render_template("index.html")


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
                result = extract_fields(cnic_file_input, "cnic")
                if result.get("status") == "success":
                    yield json.dumps({"status": "success", "data": result.get("data")}) + "\n"
                else:
                    yield json.dumps({"status": "error", "message": result.get("message", "Extraction failed")}) + "\n"

            # ---------------- NAF ----------------
            elif form_type == "naf":
                yield json.dumps({"status": "progress", "message": "Analyzing structure..."}) + "\n"
                
                from scripts.naf_extractor import identify_naf, extract_with_azure, build, extract_naf_fields
                verified_naf = identify_naf(naf_filepath, AZURE_ENDPOINT, AZURE_KEY)
                doc_type, confidence = verified_naf
                if doc_type != "naf_detected" and confidence < 0.85:
                    raise ValueError("Facing difficulty in identifying NAF document (!Use clear image). Extraction aborted.")
                
                yield json.dumps({"status": "progress", "message": "Extracting fields..."}) + "\n"
                data = extract_with_azure(naf_filepath, AZURE_ENDPOINT, AZURE_KEY, NAF_MODEL_IDS)
                
                yield json.dumps({"status": "progress", "message": "Finalizing..."}) + "\n"
                result_data = build(data)
                
                yield json.dumps({"status": "success", "data": result_data}) + "\n"

        except Exception as e:
            yield json.dumps({"status": "error", "message": str(e)}) + "\n"

    return Response(generate(), mimetype='application/x-ndjson')


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True,port=int(os.getenv('PORT', 5000)))