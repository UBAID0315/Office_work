from scripts.cnic_extractor import extract_cnic_fields
from scripts.naf_extractor import extract_naf_fields

from flask import Flask, render_template, request, Response, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from database.connection import create_connection
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

import os
import uuid
import json

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

app = Flask(__name__)
CORS(app)
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



import re


def classify_document(pdf_path, endpoint, key):
    '''Identifies if the given PDF is a CNIC document using the Azure Document Intelligence classifier. 
       Returns (doc_type, confidence) if a document is found, else (None, 0.0).'''
    client = DocumentIntelligenceClient(
        endpoint=AZURE_ENDPOINT,
        credential=AzureKeyCredential(AZURE_KEY),
    )

    with open(pdf_path, "rb") as f:
        poller = client.begin_classify_document(
            classifier_id="cnic_naf_identifier",
            body=f,
        )

    result = poller.result()

    if result.documents:
        doc = result.documents[0]
        return doc.doc_type, doc.confidence
    
    return None, 0.0

def normalize_date_for_db(date_str):
    """Converts DD-MM-YYYY or other formats to standard YYYY-MM-DD for MySQL DATE columns."""
    if not date_str:
        return None
    date_str = str(date_str).strip()
    
    # 1. Already in YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str
        
    # 2. Convert DD-MM-YYYY or DD/MM/YYYY to YYYY-MM-DD
    match = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', date_str)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
    return None

def normalize_enum_for_db(val, allowed_set, fallback=None):
    """Normalizes string inputs to match strict MySQL ENUM sets (case-insensitive checks, whitespace trimming)."""
    if not val:
        return fallback
    
    cleaned = str(val).strip()
    
    # Try direct match
    if cleaned in allowed_set:
        return cleaned
        
    # Try case-insensitive matching
    for option in allowed_set:
        if option.lower() == cleaned.lower():
            return option
            
    # Custom spellfixes for common OCR mistakes
    cleaned_lower = cleaned.lower()
    if "yes" in cleaned_lower:
        cleaned = "Yes"
    elif "no" in cleaned_lower:
        cleaned = "No"
        
    # Re-check direct match after spelling correction
    if cleaned in allowed_set:
        return cleaned
        
    # Return fallback if no match found
    return fallback

@app.route("/")
def home():
    return jsonify({"status": "success", "message": "10Pearls Extractor API is running."})

# ── Helper for 3-way extraction: Azure, GLM, Human ──────────
def extract_triple_field(field_obj):
    """
    Extracts (az_val, az_conf, glm_val, glm_conf, hum_val) for a field node.
    Falls back human_val to az_val if human did not manually edit it.
    """
    if not isinstance(field_obj, dict):
        val = str(field_obj) if field_obj is not None else None
        return val, None, val, None, val

    azure_node = field_obj.get("azure", {})
    glm_node = field_obj.get("glm", {})
    corrected_node = field_obj.get("corrected", {})

    is_option = "selected" in azure_node or "options" in azure_node
    prop = "selected" if is_option else "value"

    az_val = azure_node.get(prop) if isinstance(azure_node, dict) else None
    az_conf = azure_node.get("confidence") if isinstance(azure_node, dict) else None

    glm_val = glm_node.get(prop) if isinstance(glm_node, dict) else None
    glm_conf = glm_node.get("confidence") if isinstance(glm_node, dict) else None

    hum_val = corrected_node.get(prop) if isinstance(corrected_node, dict) else None
    if hum_val is None or hum_val == "":
        hum_val = az_val

    return az_val, az_conf, glm_val, glm_conf, hum_val

@app.route("/save-to-db/<form_type>", methods=["POST"])
def save_to_db(form_type):
    connection = create_connection()
    if not connection:
        return jsonify({"status": "error", "message": "Failed to connect to the database."}), 500

    cursor = connection.cursor()
    raw_data = request.get_json()

    if raw_data is None:
        return jsonify({"status": "error", "message": "No data provided."}), 400

    try:
        if form_type == "cnic":
            if isinstance(raw_data, list):
                if len(raw_data) == 0:
                    return jsonify({"status": "error", "message": "Empty CNIC data received."}), 400
                raw_data = raw_data[0]

            cursor.execute("SELECT COUNT(*) FROM documents WHERE document_type = 'CNIC'")
            cnic_count = cursor.fetchone()[0]
            doc_id = f"DOC_CNIC_{cnic_count + 1:04d}"

            # Insert parent record
            document_query = """
                INSERT INTO documents (id, document_type, endpoint_url, extraction_status)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(document_query, (doc_id, 'CNIC', os.environ.get("AZURE_DI_ENDPOINT"), 'COMPLETED'))

            row = {"document_id": doc_id}
            cnic_fields = [
                ("Name", "name"), ("Father Name", "father_name"), ("CNIC Number", "cnic"),
                ("Date of Birth", "date_of_birth"), ("Gender", "gender"),
                ("Issue Date", "issue_date"), ("Expiry Date", "expiry_date")
            ]
            for label, col_base in cnic_fields:
                field_obj = raw_data.get(label, {})
                az_val, az_conf, glm_val, glm_conf, hum_val = extract_triple_field(field_obj)
                row[f"{col_base}_azure"] = az_val
                row[f"{col_base}_azure_confidence"] = az_conf
                row[f"{col_base}_glm"] = glm_val
                row[f"{col_base}_glm_confidence"] = glm_conf
                row[f"{col_base}_human"] = hum_val

            columns = ", ".join(row.keys())
            placeholders = ", ".join(["%s"] * len(row))
            cursor.execute(f"INSERT INTO cnic_data ({columns}) VALUES ({placeholders})", tuple(row.values()))
            connection.commit()
            return jsonify({"status": "success", "message": "CNIC data saved to database successfully."}), 200

        elif form_type == "naf":
            if isinstance(raw_data, list):
                if len(raw_data) == 0:
                    return jsonify({"status": "error", "message": "Empty NAF data received."}), 400
                raw_data = raw_data[0]

            # 1. Generate custom Document ID
            cursor.execute("SELECT COUNT(*) FROM documents WHERE document_type = 'NAF'")
            naf_count = cursor.fetchone()[0]
            doc_id = f"DOC_NAF_{naf_count + 1:04d}"

            # 2. Insert parent 'documents' record
            cursor.execute(
                "INSERT INTO documents (id, document_type, endpoint_url, extraction_status) VALUES (%s, %s, %s, %s)",
                (doc_id, 'NAF', os.environ.get("AZURE_DI_ENDPOINT"), 'COMPLETED')
            )

            # 3. Dynamic schema mapping for 1-to-1 sections
            NAF_MAPPING = {
                "naf_basic_information": ("section_1_basic_information", [
                    ("name", "name"), ("address", "address"), ("telephone", "telephone"),
                    ("email", "email"), ("date_of_birth", "date_of_birth"),
                    ("marital_status", "marital_status"), ("state_of_health", "state_of_health"),
                    ("smoker", "smoker")
                ]),
                "naf_employment_details": ("section_3_employment_details", [
                    ("occupation", "occupation"), ("length_of_service", "length_of_service"),
                    ("annual_income", "annual_income"), ("normal_retirement_age", "normal_retirement_age"),
                    ("covered_under_pension_scheme", "covered_under_pension_scheme")
                ]),
                "naf_financial_details": ("section_4_financial_details", [
                    ("value_of_savings_and_assets", "value_of_savings_and_assets"),
                    ("liabilities_outstanding_loans", "liabilities_outstanding_loans"),
                    ("expected_inheritance", "expected_inheritance")
                ]),
                "naf_pension_details": ("section_5_pension_details", [
                    ("employers_scheme_insurance_takaful", "employers_scheme_insurance_takaful"),
                    ("personal_premium_contribution", "personal_premium_contribution"),
                    ("retirement_age", "retirement_age"), ("anticipated_value", "anticipated_value")
                ]),
                "naf_future_saving_needs": ("section_6_future_saving_needs", [
                    ("for_education_of_children", "for_education_of_children"),
                    ("for_wedding", "for_wedding"), ("for_house_purchase", "for_house_purchase"),
                    ("others", "others")
                ]),
                "naf_financial_priorities": ("section_8_financial_priorities", [
                    ("financial_security_event_of_death", "financial_security_event_of_death"),
                    ("financial_security_critical_illness", "financial_security_critical_illness"),
                    ("providing_retirement_income", "providing_retirement_income"),
                    ("planning_childrens_education", "planning_childrens_education"),
                    ("planning_childrens_wedding", "planning_childrens_wedding"),
                    ("building_capital_regular_saving", "building_capital_regular_saving"),
                    ("investing_existing_capital", "investing_existing_capital")
                ]),
                "naf_identified_takaful_needs": ("section_9_identified_takaful_needs", [
                    ("life_takaful_death_maturity", "life_takaful_death_maturity"),
                    ("desirable_sum_covered", "desirable_sum_covered"),
                    ("health_family_takaful", "health_family_takaful"),
                    ("desirable_limit_coverage_annual", "desirable_limit_coverage_annual"),
                    ("saving_investment_planning", "saving_investment_planning"),
                    ("desirable_returns_per_annum", "desirable_returns_per_annum"),
                    ("pension_planning", "pension_planning"),
                    ("desirable_pension_per_annum", "desirable_pension_per_annum")
                ])
            }

            for table, (sec_key, fields_list) in NAF_MAPPING.items():
                sec_data = raw_data.get(sec_key, {})
                row = {"document_id": doc_id}
                for json_key, db_base in fields_list:
                    field_obj = sec_data.get(json_key, {})
                    az_val, az_conf, glm_val, glm_conf, hum_val = extract_triple_field(field_obj)
                    row[f"{db_base}_azure"] = az_val
                    row[f"{db_base}_azure_confidence"] = az_conf
                    row[f"{db_base}_glm"] = glm_val
                    row[f"{db_base}_glm_confidence"] = glm_conf
                    row[f"{db_base}_human"] = hum_val

                if table == "naf_identified_takaful_needs":
                    add_info = raw_data.get("section_10_additional_information", {})
                    az_val, az_conf, glm_val, glm_conf, hum_val = extract_triple_field(add_info)
                    row["additional_information_azure"] = az_val
                    row["additional_information_azure_confidence"] = az_conf
                    row["additional_information_glm"] = glm_val
                    row["additional_information_glm_confidence"] = glm_conf
                    row["additional_information_human"] = hum_val

                columns = ", ".join(row.keys())
                placeholders = ", ".join(["%s"] * len(row))
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values()))

            # 4. Insert Family Details & Dependents
            fam_sec = raw_data.get("section_2_family_details", {})
            fam_row = {"document_id": doc_id}

            num_dep_obj = fam_sec.get("number_of_dependents", {})
            az_v, az_c, glm_v, glm_c, hum_v = extract_triple_field(num_dep_obj)
            fam_row["number_of_dependents_azure"] = az_v
            fam_row["number_of_dependents_azure_confidence"] = az_c
            fam_row["number_of_dependents_glm"] = glm_v
            fam_row["number_of_dependents_glm_confidence"] = glm_c
            fam_row["number_of_dependents_human"] = hum_v

            exp_obj = fam_sec.get("scope_for_family_expansion", {})
            az_v, az_c, glm_v, glm_c, hum_v = extract_triple_field(exp_obj)
            fam_row["scope_for_family_expansion_azure"] = az_v
            fam_row["scope_for_family_expansion_azure_confidence"] = az_c
            fam_row["scope_for_family_expansion_glm"] = glm_v
            fam_row["scope_for_family_expansion_glm_confidence"] = glm_c
            fam_row["scope_for_family_expansion_human"] = hum_v

            fam_cols = ", ".join(fam_row.keys())
            fam_ph = ", ".join(["%s"] * len(fam_row))
            cursor.execute(f"INSERT INTO naf_family_details ({fam_cols}) VALUES ({fam_ph})", tuple(fam_row.values()))
            family_details_id = cursor.lastrowid

            dependents = fam_sec.get("dependents", [])
            for dep in dependents:
                dep_row = {"family_details_id": family_details_id}
                dep_fields = [
                    ("name", "dependent_name"), ("relationship", "relationship"),
                    ("age", "age"), ("state_of_health", "state_of_health"),
                    ("occupation", "occupation")
                ]
                for json_k, db_b in dep_fields:
                    f_obj = dep.get(json_k, {})
                    az_v, az_c, glm_v, glm_c, hum_v = extract_triple_field(f_obj)
                    dep_row[f"{db_b}_azure"] = az_v
                    dep_row[f"{db_b}_azure_confidence"] = az_c
                    dep_row[f"{db_b}_glm"] = glm_v
                    dep_row[f"{db_b}_glm_confidence"] = glm_c
                    dep_row[f"{db_b}_human"] = hum_v

                d_cols = ", ".join(dep_row.keys())
                d_ph = ", ".join(["%s"] * len(dep_row))
                cursor.execute(f"INSERT INTO naf_dependents ({d_cols}) VALUES ({d_ph})", tuple(dep_row.values()))

            # 5. Insert Takaful Plans Array
            plans = raw_data.get("section_7_existing_plans", [])
            for plan in plans:
                plan_row = {"document_id": doc_id}
                plan_fields = [
                    ("company_takaful_operator", "company_takaful_operator"),
                    ("policy_certificate_no", "policy_certificate_no"),
                    ("sum_assured_covered", "sum_assured_covered"),
                    ("premium_contribution", "premium_contribution"),
                    ("start_date", "start_date"),
                    ("maturity_date", "maturity_date"),
                    ("purpose", "purpose")
                ]
                for json_k, db_b in plan_fields:
                    f_obj = plan.get(json_k, {})
                    az_v, az_c, glm_v, glm_c, hum_v = extract_triple_field(f_obj)
                    plan_row[f"{db_b}_azure"] = az_v
                    plan_row[f"{db_b}_azure_confidence"] = az_c
                    plan_row[f"{db_b}_glm"] = glm_v
                    plan_row[f"{db_b}_glm_confidence"] = glm_c
                    plan_row[f"{db_b}_human"] = hum_v

                p_cols = ", ".join(plan_row.keys())
                p_ph = ", ".join(["%s"] * len(plan_row))
                cursor.execute(f"INSERT INTO naf_family_takaful_plans ({p_cols}) VALUES ({p_ph})", tuple(plan_row.values()))

            connection.commit()
            return jsonify({"status": "success", "message": "NAF data saved to database successfully."}), 200
        else:
            return jsonify({"status": "error", "message": f"Form type '{form_type}' not supported."}), 400

    except Exception as e:
        connection.rollback()
        return jsonify({"status": "error", "message": f"Database error: {str(e)}"}), 500

    finally:
        cursor.close()
        connection.close()


import threading

GLM_JOBS = {}

def _run_glm_background(job_id, pdf_path, doc_type="naf"):
    try:
        if doc_type and "cnic" in str(doc_type).lower():
            from scripts.glm_cnic_extractor import extract_glm_cnic_fields
            glm_raw = extract_glm_cnic_fields(pdf_path)
        else:
            from scripts.glm_naf_extractor import extract_glm_naf_fields
            glm_raw = extract_glm_naf_fields(pdf_path)

        print(json.dumps(glm_raw, indent=2))
        GLM_JOBS[job_id] = {
            "status": "completed",
            "glm_data": glm_raw,
            "error": None
        }
    except Exception as e:
        print(f"GLM background job {job_id} error: {e}")
        GLM_JOBS[job_id] = {
            "status": "error",
            "glm_data": None,
            "error": str(e)
        }

@app.route("/glm-status/<job_id>", methods=["GET"])
def get_glm_status(job_id):
    job = GLM_JOBS.get(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Job not found"}), 404
    return jsonify(job)

@app.route("/glm-stream/<job_id>")
def glm_stream(job_id):
    def event_stream():
        import time
        while True:
            job = GLM_JOBS.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                break

            if job["status"] == "completed":
                yield f"data: {json.dumps({'status': 'completed', 'glm_data': job['glm_data']})}\n\n"
                break
            elif job["status"] == "error":
                yield f"data: {json.dumps({'status': 'error', 'message': job['error']})}\n\n"
                break

            yield f"data: {json.dumps({'status': 'processing'})}\n\n"
            time.sleep(1)

    return Response(event_stream(), mimetype="text/event-stream")

def init_async_glm_data(data):
    # Recursively wraps existing flat values into {azure: {...}, glm: {status: "processing"}}
    if isinstance(data, list):
        return [init_async_glm_data(d) for d in data]
    elif isinstance(data, dict):
        if "value" in data or "confidence" in data or "options" in data:
            azure_node = data.copy()
            return {"azure": azure_node, "glm": {"status": "processing"}}
        else:
            new_dict = {}
            for k, v in data.items():
                if k in ["form_title", "family_takaful_need_analysis_of"]:
                    new_dict[k] = v
                else:
                    new_dict[k] = init_async_glm_data(v)
            return new_dict
    return data

@app.route("/upload", methods=["POST"])
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"status": "error", "message": "No files uploaded."}), 400

    # Save the file and make it sure name is unique
    file_paths = [save_uploaded_file(f) for f in files]

    def generate():
        try:
            yield json.dumps({"status": "progress", "message": "Preparing files for classification..."}) + "\n"
            
            pdf_to_process = file_paths[0]
            is_temp_pdf = False
            
            if not file_paths[0].lower().endswith('.pdf'):
                from scripts.cnic_extractor import convert_images_to_pdf
                combined_pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], f"combined_{uuid.uuid4()}.pdf")
                if convert_images_to_pdf(file_paths, combined_pdf_path):
                    pdf_to_process = combined_pdf_path
                    is_temp_pdf = True

            yield json.dumps({"status": "progress", "message": "Classifying document..."}) + "\n"
            
            # 2. Classify based on the single unified PDF
            doc_type, confidence = classify_document(pdf_to_process, AZURE_ENDPOINT, AZURE_KEY)
            
            # 3. Reject invalid or random documents
            if not doc_type or confidence < 0.65:
                raise Exception(f"Error: No CNIC or NAF detected")

            # Start GLM-OCR extraction asynchronously in background thread with form-specific hyperparameters
            job_id = str(uuid.uuid4())
            GLM_JOBS[job_id] = {"status": "processing", "glm_data": None, "error": None}
            threading.Thread(target=_run_glm_background, args=(job_id, pdf_to_process, doc_type), daemon=True).start()
            
            result_data = None
            
            # 4. Extract based on the verified classification (Azure DI)
            if doc_type == "cnic_detected":
                actual_form_type = "cnic"
                yield json.dumps({"status": "progress", "message": f"Classified as CNIC (Confidence: {confidence:.2f}). Extracting..."}) + "\n"
                result_data = extract_cnic_fields(pdf_to_process, AZURE_ENDPOINT, AZURE_KEY)
            elif doc_type == "naf_detected":
                actual_form_type = "naf"
                yield json.dumps({"status": "progress", "message": f"Classified as NAF (Confidence: {confidence:.2f}). Extracting..."}) + "\n"
                result_data = extract_naf_fields(pdf_to_process, AZURE_ENDPOINT, AZURE_KEY, NAF_MODEL_IDS)
            else:
                raise Exception(f"Don't try to be smart! Only accepts CNIC and NAF)")

            wrapped_data = init_async_glm_data(result_data)

            yield json.dumps({
                "status": "success", 
                "classified_type": actual_form_type,
                "glm_job_id": job_id,
                "data": wrapped_data
            }) + "\n"
            
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