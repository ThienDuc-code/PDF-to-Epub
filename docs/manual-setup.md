# Manual Setup

The setup script will:
- Install Homebrew (if not present)
- Install Python 3 and pip
- Install Google Cloud SDK
- Install required Python packages
- Set up Google Cloud authentication
- Guide you through creating a Document AI processor
- Create Google Cloud Storage bucket
- Configure your `.env` file with all settings
- Test your setup

If you prefer manual setup or are not using macOS:

## Prerequisites

1. **Google Cloud Account** with Document AI API enabled
2. **Google Cloud SDK** (`gcloud`) installed and authenticated
3. **Python 3.7+** with pip
4. **jq** (JSON processor) - will be installed automatically if missing

## Google Cloud Setup

1. **Create a Google Cloud Project** and enable the Document AI API
2. **Create a Document AI Processor** (must be done through Google Cloud Console):
   - Go to: https://console.cloud.google.com/ai/document-ai/processor-library
   - Click 'Document OCR'
   - Give it a name like 'PDF-OCR-Processor'
   - Choose location: 'eu' (Europe)
   - Click 'Create'
   - Copy the processor ID from the URL or processor details
3. **Create a Cloud Storage bucket** for your PDFs and output files
4. **Authenticate with Google Cloud**:
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

**Helper Script**: If you need help finding your processor ID after creating it, you can run:
```bash
./find_processor_id.sh
```

## Python Environment Setup

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables**:
   ```bash
   cp env.template .env
   ```
   
   Edit `.env` with your actual values:
   ```bash
   # Required settings
   GOOGLE_CLOUD_PROJECT_ID=your-project-id-here
   GOOGLE_CLOUD_PROCESSOR_VERSION=projects/YOUR_PROJECT_NUMBER/locations/eu/processors/YOUR_PROCESSOR_ID/processorVersions/YOUR_VERSION
   INPUT_PREFIX=gs://your-bucket-name/your-pdf-folder
   OUTPUT_PREFIX=gs://your-bucket-name/docai-output
   
   # Optional settings
   GOOGLE_CLOUD_LOCATION=eu
   LANGUAGE_HINTS=en,fr,it,la
   ```