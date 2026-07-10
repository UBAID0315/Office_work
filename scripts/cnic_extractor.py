from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from pypdf import PdfReader
from PIL import Image
import os


def is_valid_pdf(path):
    '''Checks if the given path is a valid PDF file.'''
    try:
        PdfReader(path)
        return True
    except:
        return False

def convert_images_to_pdf(image_paths, output_pdf_path):
    '''Converts a list of image paths to a single PDF file. Returns True if successful, False otherwise.'''
    images = []
    for path in image_paths:
        img = Image.open(path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        images.append(img)
    
    if images:
        images[0].save(output_pdf_path, save_all=True, append_images=images[1:])
        return True
    return False

def identify_cnic(pdf_path, endpoint, key):
    '''Identifies if the given PDF is a CNIC document using the Azure Document Intelligence classifier. 
       Returns (doc_type, confidence) if a document is found, else (None, 0.0).'''
    client = DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key),
    )

    with open(pdf_path, "rb") as f:
        poller = client.begin_classify_document(
            classifier_id="cnic_identifier_1.1",
            body=f,
        )

    result = poller.result()

    if result.documents:
        doc = result.documents[0]
        return doc.doc_type, doc.confidence
    return None, 0.0

def extract_cnic_fields(file_input, endpoint, key):
    '''Extracts fields from a CNIC document. The input can be a PDF path or a list of image paths.
       Returns a list of dictionaries containing the extracted fields.'''

    MODEL_ID = "cnic_extraction_model_1.2"

    pdf_to_process = None
    temp_pdf = False
    
    # Check if input is a single string (PDF path) or a list (image paths)
    if isinstance(file_input, str):
        if not is_valid_pdf(file_input):
            raise ValueError("The provided file is not a valid PDF.")
        pdf_to_process = file_input
    elif isinstance(file_input, list):
        # We assume they are image paths. Convert to a single PDF
        output_pdf = "temp_cnic_combined.pdf"
        if convert_images_to_pdf(file_input, output_pdf):
            pdf_to_process = output_pdf
            temp_pdf = True
        else:
            raise ValueError("Failed to convert images to PDF.")
    else:
        raise ValueError("Invalid file input type.")

    try:
        # This function is calling classifier to identify the document type and confidence
        doc_type, confidence = identify_cnic(pdf_to_process, endpoint, key)

        if not doc_type:
            raise ValueError("Classifier returned no result. The document could not be identified.")

        if doc_type == "Cnic_doc" and confidence >= 0.85:
            client = DocumentIntelligenceClient(
                endpoint=endpoint,
                credential=AzureKeyCredential(key)
            )

            try:
                with open(pdf_to_process, "rb") as f:
                    poller = client.begin_analyze_document(
                        model_id=MODEL_ID,
                        body=f
                    )

                result = poller.result()
                output_documents = []

                for doc_idx, document in enumerate(result.documents):
                    document_data = {}
                    for field_name, field in document.fields.items():
                        document_data[field_name] = {
                            "value": field.content,
                            "confidence": getattr(field, "confidence", None)
                        }
                    output_documents.append(document_data)
                return output_documents

            except Exception as e:
                raise RuntimeError(f"Azure extraction failed: {str(e)}")
        else:
            raise ValueError(
                f"Document rejected. Expected 'Cnic_doc' with confidence >= 0.85, "
                f"but got '{doc_type}' with confidence {confidence:.2f}."
            )

    finally:
        # Always clean up the temp PDF if it was created from images
        if temp_pdf and os.path.exists(pdf_to_process):
            os.remove(pdf_to_process)
