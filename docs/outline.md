# Overview

The project consists of two main parts:
1. **OCR Processing Scripts** (`scripts/` folder) - Convert scanned PDFs to text using Google Cloud Document AI
2. **Text Processing Scripts** (root folder) - Clean up and format the OCR text, then convert to EPUB

## OCR Processing Scripts

The `scripts/` folder contains Python scripts converted from the original Google Cloud Shell scripts:

### 1. Batch OCR Process
- **`batch_ocr_process.py`** - Basic batch OCR processing
- **`batch_ocr_with_page_breaks.py`** - Enhanced version with page breaks and language hints

### 2. Text Merging Scripts
- **`merge_all_books.py`** - Merge OCR results from all volumes
- **`merge_one_book.py`** - Merge OCR results from a single volume
- **`merge_json_to_txt.py`** - Alternative merging approach

### 3. Download Script
- **`download_txt_files.py`** - Download processed text files and package them


### Advanced Options

**Enhanced OCR with page breaks and language hints:**
```bash
./pdf_to_epub.sh your_book.pdf --enhanced
```

**Specify custom volume name:**
```bash
./pdf_to_epub.sh your_book.pdf --stem HOL_Vol1
```

**Get help:**
```bash
./pdf_to_epub.sh --help
```

## Usage

### Step 1: Upload PDFs to Cloud Storage

Upload your scanned PDF files to the bucket path specified in `INPUT_PREFIX`:
```bash
gsutil -m cp *.pdf gs://your-bucket-name/your-pdf-folder/
```

### Step 2: Run OCR Processing

Choose one of the OCR scripts based on your needs:

**Basic OCR (recommended for most cases)**:
```bash
python3 ocr-processing/batch_ocr_process.py
```

**Enhanced OCR with page breaks and language hints**:
```bash
python3 ocr-processing/batch_ocr_with_page_breaks.py
```

### Step 3: Merge OCR Results

**Merge all volumes**:
```bash
python3 ocr-processing/merge_all_books.py
```

**Merge a specific volume**:
```bash
python3 ocr-processing/merge_one_book.py HOL_Vol1
```

### Step 4: Download Processed Text

```bash
python3 ocr-processing/download_txt_files.py
```

Then download the zip file:
```bash
cloudshell download batch_clean_txts.zip
```

### Step 5: Text Processing and EPUB Creation

Use the existing Python scripts in the root directory:

1. **Clean up OCR text**:
   ```bash
   python3 text-processing/Step1_ocr_cleanup_v6.py
   ```

2. **Format the text**:
   ```bash
   python3 text-processing/Step2_formatting1_v2.py
   ```

3. **Further formatting**:
   ```bash
   python3 text-processing/step3_formating2_v2.py
   ```

4. **Create EPUB**:
   ```bash
   python3 text-processing/Step4_create_epub.py
   ```

## Configuration Options

### Environment Variables

- `GOOGLE_CLOUD_PROJECT_ID` - Your Google Cloud project ID
- `GOOGLE_CLOUD_LOCATION` - Document AI location (default: eu)
- `GOOGLE_CLOUD_PROCESSOR_VERSION` - Full processor version path
- `INPUT_PREFIX` - GCS path to your PDF files
- `OUTPUT_PREFIX` - GCS path for OCR output
- `LANGUAGE_HINTS` - Comma-separated language codes for better OCR
- `DATE_PREFIX` - Override date prefix (defaults to current date)
- `STEM` - Specific volume name for single book operations

### Language Hints

The `LANGUAGE_HINTS` setting helps improve OCR accuracy. Common values:
- `en` - English
- `fr` - French  
- `it` - Italian
- `la` - Latin
- `de` - German
- `es` - Spanish

## Troubleshooting

### Common Issues

1. **Authentication errors**: Make sure you're logged in with `gcloud auth login`
2. **Permission errors**: Ensure your account has Document AI and Cloud Storage permissions
3. **Processor not found**: Verify your processor version path in the `.env` file
4. **No PDFs found**: Check that your `INPUT_PREFIX` path contains PDF files

### Getting Help

- Check Google Cloud Console for Document AI processor status
- Verify Cloud Storage bucket permissions
- Review the script output for specific error messages

## File Structure

```
manjushri/
├── ocr-processing/                   # OCR processing scripts
│   ├── batch_ocr_process.py         # Basic OCR processing
│   ├── batch_ocr_with_page_breaks.py # Enhanced OCR with page breaks
│   ├── merge_all_books.py           # Merge all volumes
│   ├── merge_one_book.py            # Merge single volume
│   ├── merge_json_to_txt.py         # Alternative merge approach
│   └── download_txt_files.py        # Download processed files
├── text-processing/                  # Text cleanup and EPUB creation
│   ├── Step1_ocr_cleanup_v6.py      # Text cleanup
│   ├── Step2_formatting1_v2.py      # Text formatting
│   ├── step3_formating2_v2.py       # Additional formatting
│   └── Step4_create_epub.py         # EPUB creation
├── output/                           # Generated EPUB files
├── pdf_to_epub.sh                    # Main entry script (PDF → EPUB)
├── setup_macos.sh                    # Automated macOS setup script
├── find_processor_id.sh              # Helper to find Document AI processor ID
├── requirements.txt                  # Python dependencies
├── env.template                      # Environment configuration template
└── readme.md                         # This file
```