import sys
import time
import json
from pathlib import Path
from glm_cnic_extractor import extract_glm_cnic_fields
from glm_naf_extractor import extract_glm_naf_fields

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_glm_cli.py <path_to_pdf_or_image> [doc_type: naf|cnic]")
        print("Example: python scripts/test_glm_cli.py \"C:\\Users\\Ubaid Ur Rehman\\Downloads\\1-1-4.pdf\" naf")
        sys.exit(1)

    file_path = sys.argv[1]
    doc_type = sys.argv[2].lower() if len(sys.argv) > 2 else "naf"

    print("=" * 60)
    print(f"Parallel Multithreaded GLM-OCR CLI Test Runner")
    print(f"Target File : {file_path}")
    print(f"Doc Type    : {doc_type.upper()}")
    print("=" * 60)

    start_time = time.time()
    try:
        if "cnic" in doc_type:
            print("[INFO] Spawning parallel threads for CNIC GLM-OCR extraction (num_predict=140)...")
            result = extract_glm_cnic_fields(file_path)
        else:
            print("[INFO] Spawning parallel threads for multi-page NAF GLM-OCR extraction (num_predict=800)...")
            result = extract_glm_naf_fields(file_path)

        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"[SUCCESS] Parallel Multithreaded GLM-OCR Completed in {elapsed:.2f} seconds!")
        print("=" * 60)
        print(json.dumps(result, indent=2))

        out_path = Path("glm_test_output.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        print(f"\n[INFO] Output saved to: {out_path.resolve()}")

    except Exception as e:
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print(f"[ERROR] Multithreaded GLM-OCR Failed after {elapsed:.2f} seconds!")
        print(f"Error Details: {e}")
        print("=" * 60)

if __name__ == "__main__":
    main()