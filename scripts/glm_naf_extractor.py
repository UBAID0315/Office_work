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

# DPI = 300
# MAX_WIDTH = 1400
DPI = 200
MAX_WIDTH = 1000
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

SECTION_PATTERN = re.compile(r'^\d+\.\s+(.+)$')


def parse_ocr_output(text: str):
    """
    Generic parser for OCR/LLM output of forms.
    Handles raw JSON, JSON with form_title text block, and raw text.
    """
    cleaned_text = text.strip()
    cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

    full_text = cleaned_text.replace("\\n", "\n")
    parsed_json = {}

    try:
        obj = json.loads(cleaned_text)
        if isinstance(obj, dict):
            parsed_json = obj
            for val in obj.values():
                if isinstance(val, str) and ("\n" in val or "\\n" in val):
                    full_text += "\n" + val.replace("\\n", "\n")
    except Exception:
        pass

    result = {}

    def set_field(std_name, val_str, extra_keys=[]):
        if not val_str:
            return
        val_cleaned = str(val_str).strip().strip('"').strip("'")
        if std_name in ["smoker", "covered_under_pension_scheme", "scope_for_family_expansion"]:
            val_lower = val_cleaned.lower()
            if "yes" in val_lower and "no" not in val_lower:
                val_cleaned = "Yes"
            elif "no" in val_lower and "yes" not in val_lower:
                val_cleaned = "No"
            elif val_cleaned.startswith("Yes"):
                val_cleaned = "Yes"
            elif val_cleaned.startswith("No"):
                val_cleaned = "No"

        result[std_name] = val_cleaned
        result[std_name.replace("_", " ")] = val_cleaned
        result[std_name.replace("_", " ").title()] = val_cleaned
        for k in extra_keys:
            result[k] = val_cleaned
            result[k.lower()] = val_cleaned

    # Extract directly if dict has key-values
    for k, v in parsed_json.items():
        if isinstance(v, str) and v and k != "form_title":
            set_field(k.lower().replace(" ", "_"), v)

    # Regex patterns for NAF multiline text dump
    patterns = [
        ("family_takaful_need_analysis_of", r"(?:Family Takaful Noed Analysis of|Family Takaful Need Analysis of):\s*(.+)", ["ftn_name", "prospect_name"]),
        ("name", r"(?:^|\n)\s*Name:\s*(.+)", ["applicant_name"]),
        ("address", r"Address:\s*(.+)", []),
        ("telephone", r"Telephone(?:\s*\([^)]*\))?:\s*(.+)", ["phone", "mobile", "contact"]),
        ("email", r"(?:E-mail ID|Email):\s*(.+)", ["e-mail", "e-mail id"]),
        ("date_of_birth", r"Date of Birth:\s*(.+)", ["dob", "date of birth"]),
        ("marital_status", r"Marital Status:\s*(.+)", ["marital status", "marital"]),
        ("state_of_health", r"State of Health:\s*(.+)", ["health"]),
        ("smoker", r"Smoker:\s*(.+)", []),
        ("number_of_dependents", r"Number of Dependents:\s*(.+)", ["num_dep", "no_of_dependents"]),
        ("scope_for_family_expansion", r"Any scope for expansion of family:\s*(.+)", ["family_expansion", "expansion"]),
        ("occupation", r"Occupation:\s*(.+)", []),
        ("length_of_service", r"Length of Service:\s*(.+)", ["service_yrs"]),
        ("annual_income", r"Annual Income:\s*(.+)", ["income"]),
        ("normal_retirement_age", r"Normal Retirement Age:\s*(.+)", ["retire_age", "retirement_age"]),
        ("covered_under_pension_scheme", r"Covered under pension scheme\??\s*(.+)", ["pension_covered", "pension_scheme"]),
        ("value_of_savings_and_assets", r"Value of Savings & Assets:\s*(.+)", ["value_of_assets", "savings"]),
        ("liabilities_outstanding_loans", r"Liabilities / Outstanding Loans:\s*(.+)", ["details_of_liabilities", "liabilities"]),
        ("expected_inheritance", r"Expected Inheritance:\s*(.+)", ["inheritance"]),
    ]

    for std_name, pat, extra_keys in patterns:
        if std_name not in result or not result[std_name]:
            match = re.search(pat, full_text, re.IGNORECASE)
            if match:
                raw_val = match.group(1)
                val_str = re.split(r'[\r\n]+', raw_val)[0].strip()
                set_field(std_name, val_str, extra_keys)

    return result
# =============================================================================
# NAF PROMPTS (Page-Specific with Anti-Hallucination)
# =============================================================================
NAF_PAGE_1_PROMPT = (
    'Extract the requested fields from this document. CRITICAL: If a field is blank or not found, output an empty string "".\n'
    'DO NOT invent, guess, or hallucinate data.\n'
    'Return ONLY valid JSON. Do NOT include any extra text, explanations, or additional keys.\n'
    'You MUST use EXACTLY the following JSON structure. DO NOT duplicate fields or change key names:\n'
    '{\n'
    '  "form_title": "",\n'
    '  "takaful_of": "",\n'
    '  "name": "",\n'
    '  "address": "",\n'
    '  "telephone": "",\n'
    '  "email": "",\n'
    '  "date_of_birth": "",\n'
    '  "marital_status": "",\n'
    '  "state_of_health": "",\n'
    '  "smoker": "",\n'
    '  "number_of_dependents": "",\n'
    '  "scope_for_family_expansion": "",\n'
    '  "occupation": "",\n'
    '  "length_of_service": "",\n'
    '  "annual_income": "",\n'
    '  "normal_retirement_age": "",\n'
    '  "covered_under_pension_scheme": "",\n'
    '  "value_of_savings_and_assets": "",\n'
    '  "liabilities_outstanding_loans": "",\n'
    '  "expected_inheritance": ""\n'
    '}'
)

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
            "num_predict": 1000,
            "num_ctx": 5400,
            "num_thread": CPU_THREADS,
            "keep_alive": "30m"
        },
    )
    print(f"[DEBUG] {label} inference took {time.time() - t0:.2f}s")
    return response["message"]["content"]



# ── NAF Extractor (Replaces Sequential Logic with Hybrid Page-Specific Logic) ──
def extract_glm_naf_fields(pdf_path: str) -> dict:
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File not found: {pdf_file}")

    if pdf_file.suffix.lower() == ".pdf":
        doc = fitz.open(pdf_file)
        page = doc[0]
        pix = page.get_pixmap(dpi=DPI)
        img = enhance_image_for_ocr(pix.tobytes("png"))
        raw_text = run_ocr_naf(img, NAF_PAGE_1_PROMPT, "Page 1")
        structured_json = parse_ocr_output(raw_text)
        
        # Simple deduplication: lowercase and underscore keys
        clean_json = {}
        for k, v in (structured_json or {}).items():
            clean_k = str(k).lower().replace(" ", "_")
            if clean_k not in clean_json or len(str(v).strip()) > len(str(clean_json.get(clean_k, "")).strip()):
                clean_json[clean_k] = v
        structured_json = clean_json
        
        doc.close()
    else:
        print("Error: File should be a pdf!")
        structured_json = {}
        
    return structured_json


