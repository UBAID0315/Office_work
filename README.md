# Web Application: Document Intelligence Extractor

This is a Flask-based web application that extracts fields from CNIC (Computerized National Identity Card) and NAF (New Account Form) documents using Azure AI Document Intelligence.

## Requirements

The application requires Python 3.8+ (or compatible) and several dependencies listed in `requirements.txt`.

## Installation

1. **Clone the repository** (or navigate to this folder if already cloned):
   ```bash
   cd "Web Application"
   ```

2. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment**:
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

4. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application uses environment variables for Azure AI configuration. You need to create a `.env` file in the root of the `Web Application` folder.

1. Create a file named `.env`
2. Add the following keys and replace the placeholder values with your actual Azure credentials:

```env
AZURE_DI_ENDPOINT=your_azure_document_intelligence_endpoint
AZURE_DI_KEY=your_azure_document_intelligence_key
AZURE_DI_MODEL_IDS=model_id_1,model_id_2
```
*(Note: `AZURE_DI_MODEL_IDS` should be a comma-separated list of NAF custom model IDs, if applicable).*

## Running the Application

1. Ensure your virtual environment is active.
2. Start the Flask server by running:
   ```bash
   python app.py
   ```
3. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000/
   ```

## Usage

- You can upload PDF files or front/back images for **CNIC**.
- You can upload PDF files for **NAF** documents.
- The application will process the uploaded files securely using Azure Document Intelligence and return the extracted fields in a structured format.

# Office_work
