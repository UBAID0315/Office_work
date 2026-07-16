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



import re

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
        
            # 1. Generate custom Document ID
            cursor.execute("SELECT COUNT(*) FROM documents WHERE document_type = 'NAF'")
            naf_count = cursor.fetchone()[0]
            doc_id = f"DOC_NAF_{naf_count + 1:04d}"

            # 2. Insert parent 'documents' record
            document_query = """
                INSERT INTO documents (id, document_type, endpoint_url, extraction_status)
                VALUES (%s, %s, %s, %s)
            """
            doc_values = (
                doc_id,
                'NAF',
                os.environ.get("AZURE_DI_ENDPOINT"),
                'COMPLETED'
            )
            cursor.execute(document_query, doc_values)

            # 3. Dynamic schema mapping for 1-to-1 sections
            NAF_MAPPING = {
                "naf_basic_information": {
                    "section": "section_1_basic_information",
                    "fields": {
                        "applicant_name": ("name", "value"),
                        "applicant_name_confidence": ("name", "confidence"),
                        "address": ("address", "value"),
                        "address_confidence": ("address", "confidence"),
                        "telephone": ("telephone", "value"),
                        "telephone_confidence": ("telephone", "confidence"),
                        "email": ("email", "value"),
                        "email_confidence": ("email", "confidence"),
                        "date_of_birth": ("date_of_birth", "value"),
                        "dob_confidence": ("date_of_birth", "confidence"),
                        "marital_status": ("marital_status", "value"),
                        "marital_status_confidence": ("marital_status", "confidence"),
                        "state_of_health": ("state_of_health", "selected"),
                        "health_confidence": ("state_of_health", "confidence"),
                        "smoker": ("smoker", "selected"),
                        "smoker_confidence": ("smoker", "confidence"),
                    }
                },
                "naf_employment_details": {
                    "section": "section_3_employment_details",
                    "fields": {
                        "occupation": ("occupation", "value"),
                        "occupation_confidence": ("occupation", "confidence"),
                        "length_of_service": ("length_of_service", "value"),
                        "length_of_service_confidence": ("length_of_service", "confidence"),
                        "annual_income": ("annual_income", "value"),
                        "annual_income_confidence": ("annual_income", "confidence"),
                        "normal_retirement_age": ("normal_retirement_age", "value"),
                        "retirement_age_confidence": ("normal_retirement_age", "confidence"),
                        "covered_under_pension_scheme": ("covered_under_pension_scheme", "selected"),
                        "pension_scheme_confidence": ("covered_under_pension_scheme", "confidence"),
                    }
                },
                "naf_financial_details": {
                    "section": "section_4_financial_details",
                    "fields": {
                        "value_of_savings_and_assets": ("value_of_savings_and_assets", "value"),
                        "savings_assets_confidence": ("value_of_savings_and_assets", "confidence"),
                        "liabilities_outstanding_loans": ("liabilities_outstanding_loans", "value"),
                        "liabilities_confidence": ("liabilities_outstanding_loans", "confidence"),
                        "expected_inheritance": ("expected_inheritance", "value"),
                        "inheritance_confidence": ("expected_inheritance", "confidence"),
                    }
                },
                "naf_pension_details": {
                    "section": "section_5_pension_details",
                    "fields": {
                        "employers_scheme_insurance_takaful": ("employers_scheme_insurance_takaful", "value"),
                        "employer_scheme_confidence": ("employers_scheme_insurance_takaful", "confidence"),
                        "personal_premium_contribution": ("personal_premium_contribution", "value"),
                        "premium_contribution_confidence": ("personal_premium_contribution", "confidence"),
                        "retirement_age": ("retirement_age", "value"),
                        "retirement_age_confidence": ("retirement_age", "confidence"),
                        "anticipated_value": ("anticipated_value", "value"),
                        "anticipated_value_confidence": ("anticipated_value", "confidence"),
                    }
                },
                "naf_future_saving_needs": {
                    "section": "section_6_future_saving_needs",
                    "fields": {
                        "for_education_of_children": ("for_education_of_children", "value"),
                        "education_confidence": ("for_education_of_children", "confidence"),
                        "for_wedding": ("for_wedding", "value"),
                        "wedding_confidence": ("for_wedding", "confidence"),
                        "for_house_purchase": ("for_house_purchase", "value"),
                        "house_purchase_confidence": ("for_house_purchase", "confidence"),
                        "others": ("others", "value"),
                        "others_confidence": ("others", "confidence"),
                    }
                },
                "naf_financial_priorities": {
                    "section": "section_8_financial_priorities",
                    "fields": {
                        "financial_security_event_of_death": ("financial_security_event_of_death", "value"),
                        "death_priority_confidence": ("financial_security_event_of_death", "confidence"),
                        "financial_security_critical_illness": ("financial_security_critical_illness", "value"),
                        "illness_priority_confidence": ("financial_security_critical_illness", "confidence"),
                        "providing_retirement_income": ("providing_retirement_income", "value"),
                        "retirement_priority_confidence": ("providing_retirement_income", "confidence"),
                        "planning_childrens_education": ("planning_childrens_education", "value"),
                        "education_priority_confidence": ("planning_childrens_education", "confidence"),
                        "planning_childrens_wedding": ("planning_childrens_wedding", "value"),
                        "wedding_priority_confidence": ("planning_childrens_wedding", "confidence"),
                        "building_capital_regular_saving": ("building_capital_regular_saving", "value"),
                        "saving_priority_confidence": ("building_capital_regular_saving", "confidence"),
                        "investing_capital_better_return": ("investing_capital_better_return", "value"),
                        "investment_priority_confidence": ("investing_capital_better_return", "confidence"),
                        "investment_horizon": ("investment_horizon", "selected"),
                        "horizon_confidence": ("investment_horizon", "confidence"),
                        "investment_knowledge_level": ("investment_knowledge_level", "selected"),
                        "knowledge_confidence": ("investment_knowledge_level", "confidence"),
                        "current_financial_position": ("current_financial_position", "selected"),
                        "financial_position_confidence": ("current_financial_position", "confidence"),
                    }
                },
                "naf_identified_takaful_needs": {
                    "section": "section_9_identified_takaful_needs",
                    "fields": {
                        "life_insurance_death_maturity": ("life_insurance_death_maturity", "value"),
                        "life_insurance_confidence": ("life_insurance_death_maturity", "confidence"),
                        "desirable_sum_covered": ("desirable_sum_covered", "value"),
                        "sum_covered_confidence": ("desirable_sum_covered", "confidence"),
                        "health_family_takaful": ("health_family_takaful", "value"),
                        "health_takaful_confidence": ("health_family_takaful", "confidence"),
                        "desirable_limit_coverage_per_annum": ("desirable_limit_coverage_per_annum", "value"),
                        "coverage_limit_confidence": ("desirable_limit_coverage_per_annum", "confidence"),
                        "saving_investment_planning": ("saving_investment_planning", "value"),
                        "saving_plan_confidence": ("saving_investment_planning", "confidence"),
                        "desirable_returns_per_annum": ("desirable_returns_per_annum", "value"),
                        "return_confidence": ("desirable_returns_per_annum", "confidence"),
                        "pension_planning": ("pension_planning", "selected"),
                        "pension_planning_confidence": ("pension_planning", "confidence"),
                        "desirable_pension_per_annum": ("desirable_pension_per_annum", "value"),
                        "pension_amount_confidence": ("desirable_pension_per_annum", "confidence"),
                    }
                },
                "naf_recommendation": {
                    "section": "section_11_recommendation",
                    "fields": {
                        "life_stage": ("life_stage", "selected"),
                        "life_stage_confidence": ("life_stage", "confidence"),
                        "protection_needs": ("protection_needs", "selected"),
                        "protection_confidence": ("protection_needs", "confidence"),
                        "appetite_for_risk": ("appetite_for_risk", "selected"),
                        "risk_confidence": ("appetite_for_risk", "confidence"),
                        "plan_recommended": ("plan_recommended", "value"),
                        "plan_confidence": ("plan_recommended", "confidence"),
                        "commitment_current_future_years": ("commitment_current_future_years", "value"),
                        "commitment_confidence": ("commitment_current_future_years", "confidence"),
                "all_risks_charges_explained": ("all_risks_charges_explained", "selected"),
                        "risks_explained_confidence": ("all_risks_charges_explained", "confidence"),
                        "why_plan_most_suited": ("why_plan_most_suited", "value"),
                        "suitability_confidence": ("why_plan_most_suited", "confidence"),
                    }
                }
            }

            # Define database ENUM whitelists and fallbacks for safe database insertion
            ENUM_SCHEMAS = {
                "marital_status": {"allowed": {'Single', 'Married', 'Divorced', 'Widowed', 'Separated'}, "fallback": None},
                "state_of_health": {"allowed": {'Excellent', 'Very Good', 'Good', 'Moderate', 'Poor'}, "fallback": None},
                "smoker": {"allowed": {'Yes', 'No'}, "fallback": None},
                "scope_for_family_expansion": {"allowed": {'Yes', 'No'}, "fallback": None},
                "covered_under_pension_scheme": {"allowed": {'Yes', 'No'}, "fallback": None},
                "pension_planning": {"allowed": {'Yes', 'No'}, "fallback": None},
                "all_risks_charges_explained": {"allowed": {'Yes', 'No'}, "fallback": None},
                "investment_horizon": {"allowed": {'Short term (<1 yr)', 'Medium (1-5 yrs)', 'Medium-Long (5-10 yrs)', 'Long term (>10 yrs)'}, "fallback": None},
                "investment_knowledge_level": {"allowed": {'Little knowledge', 'Some knowledge', 'Both knowledge & experienced'}, "fallback": None},
                "current_financial_position": {"allowed": {'Very secure', 'Somewhat secure', 'Not sure', 'Likely worse'}, "fallback": None},
                "life_stage": {"allowed": {'Childhood', 'Young unmarried', 'Young married', 'Young married w/ children', 'Married w/ older children', 'Post-family', 'Pre-retirement', 'Retirement'}, "fallback": None},
                "protection_needs": {"allowed": {'Life & Health', 'Savings & Investment', 'Pension'}, "fallback": None},
                "appetite_for_risk": {"allowed": {'Low', 'Medium', 'High'}, "fallback": None}
            }

            # 4. Insert all mapped 1-to-1 tables
            for table, map_config in NAF_MAPPING.items():
                sec_data = raw_data.get(map_config["section"], {})
                row = {"document_id": doc_id}
                
                for db_col, path in map_config["fields"].items():
                    prop_key, prop_type = path
                    val_obj = sec_data.get(prop_key, {})
                    if isinstance(val_obj, dict):
                        val = val_obj.get(prop_type)
                        # Normalize date formats if destination is a DATE column
                        if db_col == "date_of_birth":
                            val = normalize_date_for_db(val)
                        # Normalize enum values if destination is an ENUM column
                        elif db_col in ENUM_SCHEMAS:
                            val = normalize_enum_for_db(val, ENUM_SCHEMAS[db_col]["allowed"], ENUM_SCHEMAS[db_col]["fallback"])
                        row[db_col] = val
                    else:
                        row[db_col] = None
                
                # identified_takaful_needs table also has root additional_information
                if table == "naf_identified_takaful_needs":
                    add_info = raw_data.get("section_10_additional_information", {})
                    if isinstance(add_info, dict):
                        row["additional_information"] = add_info.get("value")
                        row["additional_information_confidence"] = add_info.get("confidence")

                columns = ", ".join(row.keys())
                placeholders = ", ".join(["%s"] * len(row))
                cursor.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", tuple(row.values()))

            # 5. Insert Family Details & Dependents (1-to-many relationship)
            fam_section = raw_data.get("section_2_family_details", {})
            dependents = fam_section.get("dependents", [])
            
            # Safely parse number of dependents, fallback to list length
            raw_num = fam_section.get("number_of_dependents", {}).get("value")
            try:
                num_dependents = int(raw_num) if raw_num is not None else len(dependents)
            except ValueError:
                num_dependents = len(dependents)

            fam_row = {
                "document_id": doc_id,
                "number_of_dependents": num_dependents,
                "dependents_count_confidence": fam_section.get("number_of_dependents", {}).get("confidence"),
                "scope_for_family_expansion": normalize_enum_for_db(
                    fam_section.get("scope_for_family_expansion", {}).get("selected"),
                    ENUM_SCHEMAS["scope_for_family_expansion"]["allowed"],
                    ENUM_SCHEMAS["scope_for_family_expansion"]["fallback"]
                ),
                "family_expansion_confidence": fam_section.get("scope_for_family_expansion", {}).get("confidence"),
            }
            fam_columns = ", ".join(fam_row.keys())
            fam_placeholders = ", ".join(["%s"] * len(fam_row))
            cursor.execute(f"INSERT INTO naf_family_details ({fam_columns}) VALUES ({fam_placeholders})", tuple(fam_row.values()))
            fam_details_id = cursor.lastrowid

            dependents = fam_section.get("dependents", [])
            for dep in dependents:
                dep_row = {
                    "family_details_id": fam_details_id,
                    "dependent_name": dep.get("name", {}).get("value"),
                    "name_confidence": dep.get("name", {}).get("confidence"),
                    "relationship_confidence": dep.get("relationship", {}).get("confidence"),
                    "age": dep.get("age", {}).get("value"),
                    "age_confidence": dep.get("age", {}).get("confidence"),
                    "state_of_health": normalize_enum_for_db(
                        dep.get("state_of_health", {}).get("value"),
                        ENUM_SCHEMAS["state_of_health"]["allowed"],
                        ENUM_SCHEMAS["state_of_health"]["fallback"]
                    ),
                    "health_confidence": dep.get("state_of_health", {}).get("confidence"),
                    "occupation": dep.get("occupation", {}).get("value"),
                    "occupation_confidence": dep.get("occupation", {}).get("confidence"),
                }
                
                # Normalize relationship field specifically
                rel = dep.get("relationship", {}).get("value")
                if rel:
                    rel = str(rel).strip().title()
                    # Fix spelling mistakes (Normalization rules)
                    if "Daugth" in rel or "Daught" in rel:
                        rel = "Daughter"
                    # Validate against allowed ENUM values
                    allowed_relations = {'Wife', 'Husband', 'Son', 'Daughter', 'Father', 'Mother', 'Brother', 'Sister'}
                    if rel not in allowed_relations:
                        rel = 'Other'
                else:
                    rel = None
                
                dep_row["relationship"] = rel
                
                dep_columns = ", ".join(dep_row.keys())
                dep_placeholders = ", ".join(["%s"] * len(dep_row))
                cursor.execute(f"INSERT INTO naf_dependents ({dep_columns}) VALUES ({dep_placeholders})", tuple(dep_row.values()))

            # 6. Insert Takaful Plans Array
            plans = raw_data.get("section_7_existing_plans", [])
            for plan in plans:
                plan_row = {
                    "document_id": doc_id,
                    "company_takaful_operator": plan.get("company_takaful_operator", {}).get("value"),
                    "company_confidence": plan.get("company_takaful_operator", {}).get("confidence"),
                    "policy_certificate_no": plan.get("policy_certificate_no", {}).get("value"),
                    "policy_no_confidence": plan.get("policy_certificate_no", {}).get("confidence"),
                    "sum_assured_covered": plan.get("sum_assured_covered", {}).get("value"),
                    "sum_assured_confidence": plan.get("sum_assured_covered", {}).get("confidence"),
                    "premium_contribution": plan.get("premium_contribution", {}).get("value"),
                    "premium_confidence": plan.get("premium_contribution", {}).get("confidence"),
                    "start_date": plan.get("start_date", {}).get("value"),
                    "start_date_confidence": plan.get("start_date", {}).get("confidence"),
                    "maturity_date": plan.get("maturity_date", {}).get("value"),
                    "maturity_date_confidence": plan.get("maturity_date", {}).get("confidence"),
                    "purpose": plan.get("purpose", {}).get("value"),
                    "purpose_confidence": plan.get("purpose", {}).get("confidence"),
                }
                plan_columns = ", ".join(plan_row.keys())
                plan_placeholders = ", ".join(["%s"] * len(plan_row))
                cursor.execute(f"INSERT INTO naf_family_takaful_plans ({plan_columns}) VALUES ({plan_placeholders})", tuple(plan_row.values()))

            connection.commit()
            return jsonify({"status": "success", "message": "NAF data saved to database successfully."}), 200
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