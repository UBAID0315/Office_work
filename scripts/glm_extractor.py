import fitz
import json
import re
import os
import ollama
from pathlib import Path

MODEL_NAME = "glm-ocr:latest"

# ── NAF Configuration ────────────────────────────────────────────────────────
NAF_PROMPT = """Extract all field labels and their values from the picture. Output in Json format"""

# ── CNIC Configuration ───────────────────────────────────────────────────────
CNIC_PROMPT = """
Extract the following fields from this Pakistani CNIC.

Return ONLY valid JSON.
Do NOT include markdown, explanations, or additional text.

{
  "name": "",
  "father_name": "",
  "gender": "",
  "country_of_stay": "",
  "identity_number": "",
  "date_of_birth": "",
  "date_of_issue": "",
  "date_of_expiry": ""
}

If any field is unreadable, use "unreadable".
Do not repeat fields.
""".strip()

CNIC_EXPECTED_FIELDS = [
    "name",
    "father_name",
    "gender",
    "country_of_stay",
    "identity_number",
    "date_of_birth",
    "date_of_issue",
    "date_of_expiry",
]

# ── Inference Helper ──────────────────────────────────────────────────────────
def run_ocr(model_name: str, image_bytes: bytes, prompt: str, num_predict: int = 800) -> str:
    response = ollama.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt, "images": [image_bytes]}],
        options={"temperature": 0, "num_predict": num_predict, "num_ctx": 16384, "keep_alive": "30m"},
    )
    return response["message"]["content"]

def clean_output(text: str) -> str:
    match = re.search(r"\{.*?\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    pattern = re.compile(r"(.{15,}?)\1{2,}", re.DOTALL)
    collapsed = pattern.sub(r"\1", text)
    return collapsed.strip()

def extract_json(raw_text: str):
    text = raw_text.strip()
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(1))
        except json.JSONDecodeError:
            pass
    return None

def merge_page_results(page_results: list) -> dict:
    combined: dict = {}
    unparsed = []
    for page_num, result in page_results:
        if isinstance(result, dict):
            for key, value in result.items():
                if key not in combined:
                    combined[key] = value
                elif combined[key] == value:
                    continue
                else:
                    existing = combined[key]
                    if isinstance(existing, list):
                        if value not in existing:
                            existing.append(value)
                    else:
                        combined[key] = [existing, value]
        else:
            unparsed.append({"page": page_num, "raw": result})

    if unparsed:
        combined["_unparsed_pages"] = unparsed

    return combined

# ── NAF Extractor ─────────────────────────────────────────────────────────────
def extract_glm_naf_fields(pdf_path: str) -> dict:
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"File not found: {pdf_file}")

    page_results = []
    if pdf_file.suffix.lower() == ".pdf":
        doc = fitz.open(pdf_file)
        for i, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=300)
            image_bytes = pix.tobytes("png")
            try:
                raw_output = run_ocr(MODEL_NAME, image_bytes, NAF_PROMPT, num_predict=800)
                parsed = extract_json(raw_output)
            except Exception as err:
                print(f"GLM-OCR error on page {i}: {err}")
                parsed = None
            page_results.append((i, parsed))
        doc.close()
    else:
        with open(pdf_file, "rb") as f:
            image_bytes = f.read()
        try:
            raw_output = run_ocr(MODEL_NAME, image_bytes, NAF_PROMPT, num_predict=800)
            parsed = extract_json(raw_output)
        except Exception as err:
            print(f"GLM-OCR error on image: {err}")
            parsed = None
        page_results.append((1, parsed))

    return merge_page_results(page_results)

# ── CNIC Extractor (Hyperparameters tuned for CNIC) ─────────────────────────
def extract_glm_cnic_fields(image_or_pdf_path: str) -> dict:
    path = Path(image_or_pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() == ".pdf":
        doc = fitz.open(path)
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        image_bytes = pix.tobytes("png")
        doc.close()
    else:
        with open(path, "rb") as f:
            image_bytes = f.read()

    # Run GLM-OCR with CNIC specific num_predict=140
    raw_output = run_ocr(MODEL_NAME, image_bytes, CNIC_PROMPT, num_predict=140)
    cleaned = clean_output(raw_output)
    parsed_json = extract_json(cleaned)

    # Standardize result keys for CNIC
    result = {}
    if isinstance(parsed_json, dict):
        # Display label mapping matching React UI
        cnic_map = {
            "name": "Name",
            "father_name": "Father Name",
            "identity_number": "CNIC Number",
            "date_of_birth": "Date of Birth",
            "gender": "Gender",
            "date_of_issue": "Issue Date",
            "date_of_expiry": "Expiry Date",
        }
        for json_k, ui_label in cnic_map.items():
            val = parsed_json.get(json_k, "unreadable")
            result[ui_label] = val.strip() if isinstance(val, str) else val

    return result
