import fitz
import json
import re
import os
import time
import ollama
from pathlib import Path
from PIL import Image
import io

MODEL_NAME = "glm-ocr:latest"
CPU_THREADS = os.cpu_count() or 8

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

ALWAYS REMEMBER:
- Don't repeat the fields.
- Don't add any field from yourself. Just focus on demanding ones.
""".strip()

def run_ocr_cnic(image_bytes: bytes) -> str:
    """Ultra-fast single page CNIC OCR inference."""
    t0 = time.time()
    response = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": CNIC_PROMPT, "images": [image_bytes]}],
        format="json",
        options={
            "temperature": 0,
            "num_predict": 350,
            "num_ctx": 2048,
            "num_thread": CPU_THREADS,
            "keep_alive": "30m"
        },
    )
    print(f"[DEBUG] CNIC Ollama inference took {time.time() - t0:.2f}s")
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

def extract_glm_cnic_fields(image_or_pdf_path: str) -> dict:
    t_start = time.time()
    path = Path(image_or_pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if path.suffix.lower() == ".pdf":
        doc = fitz.open(path)
        page = doc[0]  # Process single page 1 only
        pix = page.get_pixmap(dpi=150)
        raw_bytes = pix.tobytes("png")
        doc.close()
    else:
        with open(path, "rb") as f:
            raw_bytes = f.read()

    image_bytes = _resize_image_for_fast_ocr(raw_bytes, max_width=800)
    print(f"[DEBUG] Image prepared ({len(image_bytes)} bytes) in {time.time() - t_start:.2f}s")

    raw_output = run_ocr_cnic(image_bytes)
    cleaned = clean_output(raw_output)
    parsed_json = extract_json(cleaned)

    cnic_map = {
        "name": "Name",
        "father_name": "Father Name",
        "identity_number": "CNIC Number",
        "date_of_birth": "Date of Birth",
        "gender": "Gender",
        "date_of_issue": "Issue Date",
        "date_of_expiry": "Expiry Date"
    }

    result = {}
    if isinstance(parsed_json, dict):
        for json_k, ui_label in cnic_map.items():
            val = parsed_json.get(json_k, "unreadable")
            result[ui_label] = val.strip() if isinstance(val, str) else val
    else:
        for _, ui_label in cnic_map.items():
            result[ui_label] = "unreadable"

    return result
