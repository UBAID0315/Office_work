import fitz
import json
import re
import os
import time
import ollama
from pathlib import Path
from PIL import Image, ImageEnhance
import io

MODEL_NAME = "glm-ocr:latest"
CPU_THREADS = os.cpu_count() or 8

DPI = 300
MAX_WIDTH = 1400
SHARPEN_FACTOR = 2.0
CONTRAST_FACTOR = 1.5

# =============================================================================
# IMAGE ENHANCEMENT
# =============================================================================
def enhance_image_for_ocr(raw_bytes: bytes, max_width: int = MAX_WIDTH) -> bytes:
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        if img.width > max_width:
            ratio = max_width / float(img.width)
            img = img.resize((max_width, int(img.height * ratio)), Image.Resampling.LANCZOS)
        img = ImageEnhance.Sharpness(img).enhance(SHARPEN_FACTOR)
        img = ImageEnhance.Contrast(img).enhance(CONTRAST_FACTOR)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        print(f"[WARN] Failed to enhance image: {e}")
        return raw_bytes

def _resize_image_for_fast_ocr(raw_bytes: bytes, max_width: int = 800) -> bytes:
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_height = int((float(img.height) * float(ratio)))
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception as e:
        print(f"[WARN] Failed to resize image: {e}")
        return raw_bytes


# =============================================================================
# NAF PROMPTS (Page-Specific with Anti-Hallucination)
# =============================================================================
NAF_PAGE_1_PROMPT = (
    'Read this form image and extract the text. CRITICAL: If a field is blank, output an empty string "". DO NOT invent, guess, or hallucinate data. Return ONLY valid JSON:\n'
    '{"form_title":"","takaful_of":"","name":"","address":"","phone":"","email":"",'
    '"dob":"","marital":"","health":"","smoker":"",'
    '"num_dep":"","d1n":"","d1r":"","d1a":"","d1h":"","d1o":"",'
    '"d2n":"","d2r":"","d2a":"","d2h":"","d2o":"",'
    '"d3n":"","d3r":"","d3a":"","d3h":"","d3o":"",'
    '"d4n":"","d4r":"","d4a":"","d4h":"","d4o":"",'
    '"family_expand":"","occupation":"","service_yrs":"","income":"","retire_age":"","pension_covered":"",'
    '"savings":"","liabilities":"","inheritance":""}'
)

NAF_PAGE_2_PROMPT = (
    'Read this form image and extract the text. CRITICAL: If a field is blank, output an empty string "". DO NOT invent, guess, or hallucinate data. Return ONLY valid JSON:\n'
    '{"employer_scheme":"","personal_premium":"","retire_age":"","anticipated_val":"",'
    '"edu_saving":"","wedding_saving":"","house_saving":"","other_saving":"",'
    '"p1_company":"","p1_policy":"","p1_sum":"","p1_premium":"","p1_start":"","p1_maturity":"","p1_purpose":"",'
    '"p2_company":"","p2_policy":"","p2_sum":"","p2_premium":"","p2_start":"","p2_maturity":"","p2_purpose":"",'
    '"pri_death":"","pri_illness":"","pri_retire":"","pri_edu":"","pri_wedding":"","pri_capital":"","pri_invest":"",'
    '"invest_horizon":"","invest_knowledge":"","fin_position":""}'
)

NAF_PAGE_3_PROMPT = (
    'Read this form image and extract the text. CRITICAL: If a field is blank, output an empty string "". DO NOT invent, guess, or hallucinate data. Return ONLY valid JSON:\n'
    '{"life_ins":"","sum_covered":"","health_takaful":"","health_limit":"",'
    '"saving_plan":"","returns_pa":"","pension_plan":"","pension_pa":"",'
    '"additional_info":"",'
    '"life_stage":"","protection_needs":"","risk_appetite":"","plan_recommended":"",'
    '"commitment_yrs":"","risks_explained":"","why_suited":"",'
    '"cert_statement":"","cert_date":"","cert_name":"","cert_sig":"",'
    '"ack_statement":"","ack_a":"","ack_b":"","ack_c":"","ack_d":"","ack_e":"","ack_f":"","ack_g":"",'
    '"ack_date":"","ack_sig":""}'
)


# NAF extractor file


# =============================================================================
# INFERENCE HELPERS
# =============================================================================
def run_ocr_naf(image_bytes: bytes, prompt: str, label: str) -> str:
    """NAF OCR inference."""
    t0 = time.time()
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt, "images": [image_bytes]}],
        format="json",
        options={
            "temperature": 0,
            "num_predict": 2048, # Increased to prevent truncation of full page JSON
            "num_ctx": 8192,
            "num_thread": CPU_THREADS,
            "keep_alive": "30m"
        },
    )
    print(f"[DEBUG] {label} inference took {time.time() - t0:.2f}s")
    return response["message"]["content"]


def clean_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"```(?:json)?", "", text)
    text = re.sub(r"```", "", text)
    return text.strip()

def extract_json(raw_text: str):
    if not raw_text: return {}
    text = clean_output(raw_text)
    text = re.sub(r'[\x00-\x1F\x7F]', ' ', text)
    try:
        return json.loads(text)
    except:
        start = text.find('{')
        if start != -1:
            c = text[start:]
            c = re.sub(r'",?\s*"[^"]*$', '"', c)
            c = re.sub(r",\s*([\}\]])", r"\1", c)
            if c.count('"') % 2 != 0: c += '"'
            c += "]" * max(0, c.count("[") - c.count("]"))
            c += "}" * max(0, c.count("{") - c.count("}"))
            try: return json.loads(c)
            except: pass
    return {}


# =============================================================================
# HYBRID NAF PARSER (JSON + Regex Fallback)
# =============================================================================
def get_val(parsed: dict, key: str, regex: str, raw_text: str) -> dict:
    val = parsed.get(key, "")
    
    if isinstance(val, str) and val.strip() and len(val) < 150 and "\n" not in val.strip():
        return {"value": val.strip(), "confidence": 0.0}
    
    if regex and raw_text:
        search_text = raw_text.replace('\\n', '\n')
        m = re.search(regex, search_text, re.IGNORECASE)
        if m:
            extracted = m.group(1).strip()
            extracted = extracted.split('\n')[0].strip()
            if '","' in extracted or '":"' in extracted or '": "' in extracted:
                return {"value": "", "confidence": 0.0}
            extracted = re.sub(r'["\}\]]+$', '', extracted).strip()
            return {"value": extracted, "confidence": 0.0}
            
    return {"value": "", "confidence": 0.0}

def get_mcq(parsed: dict, key: str, regex: str, raw_text: str, options: list) -> dict:
    raw_val = get_val(parsed, key, regex, raw_text)["value"].strip()
    selected = ""
    
    if not raw_val:
        return {"selected": "", "options": options}
        
    for opt in options:
        if raw_val.lower() == opt.lower():
            selected = opt
            break
            
    if not selected:
        sorted_opts = sorted(options, key=len, reverse=True)
        found_opts = []
        temp_val = raw_val.lower()
        
        for opt in sorted_opts:
            opt_lower = opt.lower()
            if opt_lower in temp_val:
                found_opts.append(opt)
                temp_val = temp_val.replace(opt_lower, ' ')
                
        if len(found_opts) == 1:
            selected = found_opts[0]
        else:
            selected = ""
            
    return {
        "selected": selected,
        "options": options
    }

def get_dependents(parsed: dict, raw_text: str) -> list:
    deps = []
    for i in range(1, 5):
        n = parsed.get(f"d{i}n", "")
        if n and len(n) < 100 and "\n" not in n:
            deps.append({
                "name": {"value": n, "confidence": 0.0},
                "relationship": {"value": parsed.get(f"d{i}r", ""), "confidence": 0.0},
                "age": {"value": parsed.get(f"d{i}a", ""), "confidence": 0.0},
                "state_of_health": {"value": parsed.get(f"d{i}h", ""), "confidence": 0.0},
                "occupation": {"value": parsed.get(f"d{i}o", ""), "confidence": 0.0},
            })
    if deps: return deps

    search_text = raw_text.replace('\\n', '\n')
    m = re.search(r"S#\s*Name\s*Relationship\s*Age.*?\n(.*?)(?:Any scope|3\. Employment)", search_text, re.DOTALL | re.IGNORECASE)
    if m:
        for line in m.group(1).strip().split('\n'):
            line = line.strip()
            if not line: continue
            row_pattern = r"^(?:\d+\s+)?(.+?)\s+(Wife|Husband|Son|Daughter|Mother|Father|Brother|Sister|Self)\s+(\d{1,2})\s+(Excellent|V\.\s*Good|V-Good|Very Good|Good|Moderate|Poor)\s+(.+)$"
            row_m = re.search(row_pattern, line, re.IGNORECASE)
            if row_m:
                deps.append({
                    "name": {"value": row_m.group(1).strip(), "confidence": 0.0},
                    "relationship": {"value": row_m.group(2).strip().capitalize(), "confidence": 0.0},
                    "age": {"value": row_m.group(3).strip(), "confidence": 0.0},
                    "state_of_health": {"value": row_m.group(4).strip().title(), "confidence": 0.0},
                    "occupation": {"value": row_m.group(5).strip(), "confidence": 0.0},
                })
            else:
                parts = line.split()
                if len(parts) >= 5 and re.match(r"^\d+$", parts[-3]):
                    o, h, a, r = parts[-1], parts[-2], parts[-3], parts[-4]
                    n = " ".join(parts[:-4])
                    if re.match(r"^\d+$", n.split()[0]): 
                        n = " ".join(n.split()[1:])
                    deps.append({
                        "name": {"value": n, "confidence": 0.0},
                        "relationship": {"value": r, "confidence": 0.0},
                        "age": {"value": a, "confidence": 0.0},
                        "state_of_health": {"value": h, "confidence": 0.0},
                        "occupation": {"value": o, "confidence": 0.0},
                    })
    return deps

def get_plans(parsed: dict, raw_text: str) -> list:
    plans = []
    for prefix in ["p1_", "p2_"]:
        c = parsed.get(f"{prefix}company", "")
        if c and len(c) < 100 and "\n" not in c:
            plans.append({
                "company_takaful_operator": {"value": c, "confidence": 0.0},
                "policy_certificate_no":    {"value": parsed.get(f"{prefix}policy", ""), "confidence": 0.0},
                "sum_assured_covered":      {"value": parsed.get(f"{prefix}sum", ""), "confidence": 0.0},
                "premium_contribution":     {"value": parsed.get(f"{prefix}premium", ""), "confidence": 0.0},
                "start_date":               {"value": parsed.get(f"{prefix}start", ""), "confidence": 0.0},
                "maturity_date":            {"value": parsed.get(f"{prefix}maturity", ""), "confidence": 0.0},
                "purpose":                  {"value": parsed.get(f"{prefix}purpose", ""), "confidence": 0.0},
            })
    return plans

def restructure(p1_raw: str, p1: dict, p2_raw: str, p2: dict, p3_raw: str, p3: dict) -> dict:
    r_takaful_of = r"Analysis of:\s*(.*)"
    r_name       = r"Name:\s*(.*)"
    r_address    = r"Address:\s*(.*)"
    r_phone      = r"Telephone.*?:\s*(.*)"
    r_email      = r"E-mail ID:\s*(.*)"
    r_dob        = r"Date of Birth:\s*(.*)"
    r_marital    = r"Marital Status:\s*(.*)"
    r_health     = r"State of Health:\s*(.*)"
    r_smoker     = r"Smoker:\s*(.*)"
    r_num_dep    = r"Number of Dependents:\s*(.*)"
    r_f_expand   = r"Any scope for expansion of family:\s*(.*)"
    r_occ        = r"3\. Employment Details.*?Occupation:\s*(.*)"
    r_service    = r"Length of Service:\s*(.*)"
    r_income     = r"Annual Income:\s*(.*)"
    r_ret_age    = r"Normal Retirement Age:\s*(.*)"
    r_pen_cov    = r"Covered under pension scheme\??:\s*(.*)"
    r_savings    = r"Value of Savings & Assets:\s*(.*)"
    r_liab       = r"Liabilities / Outstanding Loans:\s*(.*)"
    r_inherit    = r"Expected Inheritance:\s*(.*)"
    r_emp_sch    = r"employer scheme.*?:\s*(.*)"
    r_per_pre    = r"personal premium.*?:\s*(.*)"
    r_life_ins   = r"Life Insurance.*?:\s*(.*)"
    r_sum_cov    = r"Desirable Sum Covered:\s*(.*)"
    r_health_tak = r"Health Family Takaful:\s*(.*)"
    r_limit_cov  = r"Desirable limit.*?:\s*(.*)"
    r_saving_inv = r"Saving and Investment.*?:\s*(.*)"
    r_returns    = r"Desirable returns.*?:\s*(.*)"
    r_pen_plan   = r"Pension Planning:\s*(.*)"
    r_pen_pa     = r"Desirable pension.*?:\s*(.*)"
    r_add_info   = r"10\. Any Additional Information\s*(.*?)(?:11\. Recommendation|$)"
    r_life_stg   = r"Life Stage:\s*(.*)"
    r_pro_needs  = r"Protection Needs:\s*(.*)"
    r_app_risk   = r"Appetite for Risk:\s*(.*)"
    r_plan_rec   = r"Plan Recommended.*?:\s*(.*)"
    r_commit     = r"Commitment.*?:\s*(.*)"
    r_risks_exp  = r"All risks and charges explained\??\s*(.*)"
    r_why_suit   = r"Why this plan is most suited:\s*(.*)"
    r_cert_date  = r"Date:\s*(.*)"
    r_cert_name  = r"Name:\s*(.*)"

    return {
        "form_title":                      {"value": "Adamjee Life Assurance Co. Ltd - Window Takaful Operations - Needs Analysis Form", "confidence": 1.0},
        "family_takaful_need_analysis_of": get_val(p1, "takaful_of", r_takaful_of, p1_raw),
        "section_1_basic_information": {
            "name":            get_val(p1, "name", r_name, p1_raw),
            "address":         get_val(p1, "address", r_address, p1_raw),
            "telephone":       get_val(p1, "phone", r_phone, p1_raw),
            "email":           get_val(p1, "email", r_email, p1_raw),
            "date_of_birth":   get_val(p1, "dob", r_dob, p1_raw),
            "marital_status":  get_mcq(p1, "marital", r_marital, p1_raw, ["Single", "Married", "Widowed", "Divorced"]),
            "state_of_health": get_mcq(p1, "health", r_health, p1_raw, ["Excellent", "Very Good", "Good", "Moderate", "Poor"]),
            "smoker":          get_mcq(p1, "smoker", r_smoker, p1_raw, ["Yes", "No"]),
        },
        "section_2_family_details": {
            "number_of_dependents":       get_val(p1, "num_dep", r_num_dep, p1_raw),
            "dependents":                 get_dependents(p1, p1_raw),
            "scope_for_family_expansion": get_mcq(p1, "family_expand", r_f_expand, p1_raw, ["Yes", "No"]),
        },
        "section_3_employment_details": {
            "occupation":                   get_val(p1, "occupation", r_occ, p1_raw),
            "length_of_service":            get_val(p1, "service_yrs", r_service, p1_raw),
            "annual_income":                get_val(p1, "income", r_income, p1_raw),
            "normal_retirement_age":        get_val(p1, "retire_age", r_ret_age, p1_raw),
            "covered_under_pension_scheme": get_mcq(p1, "pension_covered", r_pen_cov, p1_raw, ["Yes", "No"]),
        },
        "section_4_financial_details": {
            "value_of_savings_and_assets":   get_val(p1, "savings", r_savings, p1_raw),
            "liabilities_outstanding_loans": get_val(p1, "liabilities", r_liab, p1_raw),
            "expected_inheritance":          get_val(p1, "inheritance", r_inherit, p1_raw),
        },
        "section_5_pension_details": {
            "employers_scheme_insurance_takaful": get_val(p2, "employer_scheme", r_emp_sch, p2_raw),
            "personal_premium_contribution":      get_val(p2, "personal_premium", r_per_pre, p2_raw),
            "retirement_age":                     get_val(p2, "retire_age", r"retire_age.*?:\s*(.*)", p2_raw),
            "anticipated_value":                  get_val(p2, "anticipated_val", r"anticipated_val.*?:\s*(.*)", p2_raw),
        },
        "section_6_future_saving_needs": {
            "for_education_of_children": get_val(p2, "edu_saving", r"edu_saving.*?:\s*(.*)", p2_raw),
            "for_wedding":               get_val(p2, "wedding_saving", r"wedding_saving.*?:\s*(.*)", p2_raw),
            "for_house_purchase":        get_val(p2, "house_saving", r"house_saving.*?:\s*(.*)", p2_raw),
            "others":                    get_val(p2, "other_saving", r"other_saving.*?:\s*(.*)", p2_raw),
        },
        "section_7_existing_plans": get_plans(p2, p2_raw),
        "section_8_financial_priorities": {
            "financial_security_event_of_death":   get_val(p2, "pri_death", "", p2_raw),
            "financial_security_critical_illness": get_val(p2, "pri_illness", "", p2_raw),
            "providing_retirement_income":         get_val(p2, "pri_retire", "", p2_raw),
            "planning_childrens_education":        get_val(p2, "pri_edu", "", p2_raw),
            "planning_childrens_wedding":          get_val(p2, "pri_wedding", "", p2_raw),
            "building_capital_regular_saving":     get_val(p2, "pri_capital", "", p2_raw),
            "investing_capital_better_return":     get_val(p2, "pri_invest", "", p2_raw),
            "investment_horizon":                  get_mcq(p2, "invest_horizon", "", p2_raw, ["Short term (<1 yr)", "Medium term (1-5 yrs)", "Long term (>5 yrs)"]),
            "investment_knowledge_level":          get_mcq(p2, "invest_knowledge", "", p2_raw, ["Little knowledge", "Some knowledge", "Both knowledge & experienced"]),
            "current_financial_position":          get_mcq(p2, "fin_position", "", p2_raw, ["Very secure", "Somewhat secure", "Not sure", "Likely worse"]),
        },
        "section_9_identified_takaful_needs": {
            "life_insurance_death_maturity":      get_val(p3, "life_ins", r_life_ins, p3_raw),
            "desirable_sum_covered":              get_val(p3, "sum_covered", r_sum_cov, p3_raw),
            "health_family_takaful":              get_val(p3, "health_takaful", r_health_tak, p3_raw),
            "desirable_limit_coverage_per_annum": get_val(p3, "health_limit", r_limit_cov, p3_raw),
            "saving_investment_planning":         get_val(p3, "saving_plan", r_saving_inv, p3_raw),
            "desirable_returns_per_annum":        get_val(p3, "returns_pa", r_returns, p3_raw),
            "pension_planning":                   get_mcq(p3, "pension_plan", r_pen_plan, p3_raw, ["Yes", "No"]),
            "desirable_pension_per_annum":        get_val(p3, "pension_pa", r_pen_pa, p3_raw),
        },
        "section_10_additional_information": get_val(p3, "additional_info", r_add_info, p3_raw),
        "section_11_recommendation": {
            "life_stage":                      get_mcq(p3, "life_stage", r_life_stg, p3_raw, ["Childhood", "Young unmarried", "Young married", "Young married w/ children", "Married w/ older children", "Post-family", "Pre-retirement", "Retirement"]),
            "protection_needs":                get_mcq(p3, "protection_needs", r_pro_needs, p3_raw, ["Life & Health", "Savings & Investment", "Pension"]),
            "appetite_for_risk":               get_mcq(p3, "risk_appetite", r_app_risk, p3_raw, ["Low", "Medium", "High"]),
            "plan_recommended":                get_val(p3, "plan_recommended", r_plan_rec, p3_raw),
            "commitment_current_future_years": get_val(p3, "commitment_yrs", r_commit, p3_raw),
            "all_risks_charges_explained":     get_mcq(p3, "risks_explained", r_risks_exp, p3_raw, ["Yes", "No"]),
            "why_plan_most_suited":            get_val(p3, "why_suited", r_why_suit, p3_raw),
        },
        "sales_officer_certification": {
            "statement": {"value": "", "confidence": 0.0},
            "date":      get_val(p3, "cert_date", r_cert_date, p3_raw),
            "name":      get_val(p3, "cert_name", r_cert_name, p3_raw),
            "signature": {"value": "", "confidence": 0.0},
        },
        "prospect_acknowledgement": {
            "statement": {"value": "", "confidence": 0.0},
            "acknowledgements": {
                "a": {"value": "", "confidence": 0.0}, "b": {"value": "", "confidence": 0.0},
                "c": {"value": "", "confidence": 0.0}, "d": {"value": "", "confidence": 0.0},
                "e": {"value": "", "confidence": 0.0}, "f": {"value": "", "confidence": 0.0},
                "g": {"value": "", "confidence": 0.0},
            },
            "date":      {"value": "", "confidence": 0.0},
            "signature": {"value": "", "confidence": 0.0},
        },
    }

# ── NAF Extractor (Replaces Sequential Logic with Hybrid Page-Specific Logic) ──
def extract_glm_naf_fields(pdf_path: str) -> dict:
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File not found: {pdf_file}")

    page_prompts = [NAF_PAGE_1_PROMPT, NAF_PAGE_2_PROMPT, NAF_PAGE_3_PROMPT]
    raw_outputs = []
    parsed_outputs = []

    if pdf_file.suffix.lower() == ".pdf":
        doc = fitz.open(pdf_file)
        print(f"\n[INFO] 📄 NAF Extraction: {len(doc)} pages | DPI={DPI} | Sharpen={SHARPEN_FACTOR}x | Contrast={CONTRAST_FACTOR}x")
        for i, page in enumerate(doc, start=1):
            print(f"[INFO] ▶ Processing Page {i}/{len(doc)}...")
            pix    = page.get_pixmap(dpi=DPI)
            img    = enhance_image_for_ocr(pix.tobytes("png"))
            prompt = page_prompts[i - 1] if i <= 3 else NAF_PAGE_3_PROMPT
            
            raw_text = run_ocr_naf(img, prompt, f"Page {i}")
            raw_outputs.append(raw_text)
            parsed_outputs.append(extract_json(raw_text))
            
        doc.close()
    else:
        with open(pdf_file, "rb") as f:
            raw_bytes = f.read()
        img = enhance_image_for_ocr(raw_bytes)
        raw_text = run_ocr_naf(img, NAF_PAGE_1_PROMPT, "Page 1")
        raw_outputs.append(raw_text)
        parsed_outputs.append(extract_json(raw_text))

    while len(raw_outputs) < 3:
        raw_outputs.append("")
        parsed_outputs.append({})

    return restructure(
        raw_outputs[0], parsed_outputs[0],
        raw_outputs[1], parsed_outputs[1],
        raw_outputs[2], parsed_outputs[2]
    )


