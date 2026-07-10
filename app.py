from scripts.cnic_extractor import extract_cnic_fields
from scripts.naf_extractor import extract_naf_fields

from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

import os
import uuid

load_dotenv()

app = Flask(__name__)

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

    # ---------------- CNIC ----------------
    if form_type == "cnic":

        # PDF upload path
        pdf = request.files.get("pdf")

        if pdf and pdf.filename:

            if not pdf.filename.lower().endswith(".pdf"):
                return jsonify({
                    "error": "Only PDF files are allowed."
                }), 400

            filepath = save_uploaded_file(pdf)
            result = extract_fields(filepath, "cnic")

        # Front/back image upload path
        else:
            front = request.files.get("front_image")
            back = request.files.get("back_image")

            if (
                not front or not front.filename or
                not back or not back.filename
            ):
                return jsonify({
                    "error": "Upload either a PDF or both front and back images."
                }), 400

            front_path = save_uploaded_file(front)
            back_path = save_uploaded_file(back)

            result = extract_fields(
                [front_path, back_path],
                "cnic"
            )

    # ---------------- NAF ----------------
    elif form_type == "naf":

        pdf = request.files.get("pdf")

        if not pdf or not pdf.filename:
            return jsonify({
                "error": "No PDF uploaded."
            }), 400

        if not pdf.filename.lower().endswith(".pdf"):
            return jsonify({
                "error": "Only PDF files are allowed."
            }), 400

        filepath = save_uploaded_file(pdf)

        result = extract_fields(
            filepath,
            "naf"
        )

    else:
        return jsonify({
            "error": f"Unsupported form type: {form_type}"
        }), 400

    status_code = 200 if result["status"] == "success" else 500

    return jsonify(result), status_code


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))