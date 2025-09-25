#!/usr/bin/env bash

# PDF to EPUB Entry Script
# Complete workflow from PDF upload to EPUB creation

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if file exists
file_exists() {
    [ -f "$1" ]
}

# Function to show usage
show_usage() {
    echo "Usage: $0 <pdf_file> [options]"
    echo
    echo "Arguments:"
    echo "  pdf_file    Path to the PDF file to process"
    echo
    echo "Options:"
    echo "  --enhanced  Use enhanced OCR with page breaks and language hints"
    echo "  --stem NAME Use specific volume name (default: auto-detect from filename)"
    echo "  --help      Show this help message"
    echo
    echo "Examples:"
    echo "  $0 book.pdf"
    echo "  $0 book.pdf --enhanced"
    echo "  $0 book.pdf --stem HOL_Vol1"
    echo
    echo "The script will:"
    echo "  1. Check if PDF exists on Google Cloud Storage"
    echo "  2. Upload PDF if not present"
    echo "  3. Run OCR processing"
    echo "  4. Merge OCR results"
    echo "  5. Download processed text"
    echo "  6. Run text cleanup and formatting"
    echo "  7. Create EPUB file"
    echo "  8. Save EPUB to output/ folder"
}

# Parse command line arguments
PDF_FILE=""
ENHANCED_OCR=false
STEM_NAME=""
TEMP_DIR=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --enhanced)
            ENHANCED_OCR=true
            shift
            ;;
        --stem)
            STEM_NAME="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        -*)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            if [ -z "$PDF_FILE" ]; then
                PDF_FILE="$1"
            else
                print_error "Multiple PDF files specified. Only one PDF file is supported."
                exit 1
            fi
            shift
            ;;
    esac
done

# Check if PDF file is provided
if [ -z "$PDF_FILE" ]; then
    print_error "No PDF file specified."
    show_usage
    exit 1
fi

# Check if PDF file exists locally
if [ ! -f "$PDF_FILE" ]; then
    print_error "PDF file not found: $PDF_FILE"
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_error ".env file not found. Please run ./setup_macos.sh first."
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Validate required environment variables
if [ -z "$GOOGLE_CLOUD_PROJECT_ID" ] || [ -z "$INPUT_PREFIX" ] || [ -z "$OUTPUT_PREFIX" ]; then
    print_error "Missing required environment variables in .env file."
    print_error "Please run ./setup_macos.sh to configure your environment."
    exit 1
fi

# Extract filename without extension for volume name
PDF_BASENAME=$(basename "$PDF_FILE" .pdf)
if [ -z "$STEM_NAME" ]; then
    STEM_NAME="$PDF_BASENAME"
fi

# Create temporary directory rooted in project
TEMP_ROOT="$(pwd)/temp"
mkdir -p "$TEMP_ROOT"
TEMP_DIR="$TEMP_ROOT/pdf_to_epub_$(date +%Y%m%d_%H%M%S)_$$"
mkdir -p "$TEMP_DIR"

print_status "Starting PDF to EPUB conversion for: $PDF_FILE"
print_status "Volume name: $STEM_NAME"
print_status "Enhanced OCR: $ENHANCED_OCR"
print_status "Temporary directory: $TEMP_DIR"

# Function to cleanup on exit
cleanup() {
    print_status "Cleaning up temporary files..."
    rm -rf "$TEMP_DIR"
}
# Preserve temp directory on error; clean only on normal exit
trap 'cleanup' EXIT
trap 'print_warning "Error occurred; preserving temp directory at $TEMP_DIR for inspection"; trap - EXIT; exit 1' ERR

# Compute a stable fingerprint of the input PDF for resume detection
PDF_HASH=$(shasum -a 256 "$PDF_FILE" | awk '{print $1}')
print_status "Computed PDF SHA256: $PDF_HASH"

# Try to find prior processing results
DATE_PREFIX=${DATE_PREFIX:-$(date +%Y-%m-%d)}
FOUND_PRIOR=false

# 1) Prefer hash-based index marker if present
HASH_MARKER_GCS="$OUTPUT_PREFIX/index/by-hash/${PDF_HASH}.meta"
if gsutil ls "$HASH_MARKER_GCS" >/dev/null 2>&1; then
    print_success "Found existing processing marker by hash"
    # Marker format: simple KEY=VALUE lines
    gsutil cat "$HASH_MARKER_GCS" > "$TEMP_DIR/hash.meta"
    # shellcheck disable=SC1090
    source "$TEMP_DIR/hash.meta"
    if [ -n "$date_prefix" ]; then
        DATE_PREFIX="$date_prefix"
    fi
    if [ -z "$STEM_NAME" ] && [ -n "$stem" ]; then
        STEM_NAME="$stem"
    fi
    FOUND_PRIOR=true
else
    # 2) Fallback: look for merged TXT by stem across dates
    CANDIDATE_PATHS=$(gsutil ls "$OUTPUT_PREFIX/*/batch_clean/${STEM_NAME}_ocr.txt" 2>/dev/null || true)
    if [ -n "$CANDIDATE_PATHS" ]; then
        # Pick the most recent by lexical order (dates are YYYY-MM-DD)
        PRIOR_PATH=$(printf "%s\n" "$CANDIDATE_PATHS" | sort | tail -n1)
        DATE_PREFIX=$(printf "%s\n" "$PRIOR_PATH" | sed -n 's#.*/docai-output/\([^/]*\)/batch_clean/.*#\1#p')
        print_success "Found existing merged TXT for stem at date $DATE_PREFIX"
        FOUND_PRIOR=true
    fi
fi

# Step 1: Check if PDF exists on bucket and upload if needed
print_status "Step 1: Checking PDF on Google Cloud Storage..."

PDF_GCS_PATH="$INPUT_PREFIX/$(basename "$PDF_FILE")"

if gsutil ls "$PDF_GCS_PATH" >/dev/null 2>&1; then
    print_success "PDF already exists on bucket: $PDF_GCS_PATH"
else
    print_warning "PDF not found on bucket. Uploading..."
    gsutil cp "$PDF_FILE" "$PDF_GCS_PATH"
    print_success "PDF uploaded to: $PDF_GCS_PATH"
fi

# Step 2: Run OCR processing
print_status "Step 2: Running OCR processing..."

# Set STEM environment variable for single book processing
export STEM="$STEM_NAME"

# If we found prior results, ensure the merged TXT exists and skip OCR/merge
MERGED_TXT_GCS="$OUTPUT_PREFIX/$DATE_PREFIX/batch_clean/${STEM_NAME}_ocr.txt"
if [ "$FOUND_PRIOR" = true ] && gsutil ls "$MERGED_TXT_GCS" >/dev/null 2>&1; then
    print_success "Found existing merged TXT: $MERGED_TXT_GCS — skipping OCR and merge"
else

if [ "$ENHANCED_OCR" = true ]; then
    print_status "Using enhanced OCR with page breaks and language hints..."
    python3 ocr-processing/batch_ocr_with_page_breaks.py
else
    print_status "Using basic OCR processing..."
    python3 ocr-processing/batch_ocr_process.py
fi

    if [ $? -ne 0 ]; then
        print_error "OCR processing failed"
        exit 1
    fi

    print_success "OCR processing completed"

# Step 3: Merge OCR results
    print_status "Step 3: Merging OCR results..."

    python3 ocr-processing/merge_one_book.py "$STEM_NAME"

    if [ $? -ne 0 ]; then
        print_error "OCR result merging failed"
        exit 1
    fi

    print_success "OCR results merged"
fi

# Step 4: Download processed text
print_status "Step 4: Downloading processed text..."

# Export env vars for the download script
export DATE_PREFIX
export SRC_PREFIX="$OUTPUT_PREFIX/$DATE_PREFIX/batch_clean/"
export PDF_HASH

# Run download script (it reads env + .env)
python3 ocr-processing/download_txt_files.py

if [ $? -ne 0 ]; then
    print_error "Text download failed"
    exit 1
fi

# Extract downloaded text files from project temp folder
if [ -d "temp/batch_clean_txts" ]; then
    # Ensure target folder exists under this run's temp
    mkdir -p "$TEMP_DIR/batch_clean_txts"
    cp temp/batch_clean_txts/*.txt "$TEMP_DIR/batch_clean_txts/" 2>/dev/null || true
    print_success "Text files downloaded into temp/batch_clean_txts"
else
    print_error "Downloaded text files not found in temp/batch_clean_txts"
    exit 1
fi

# Step 5: Run text processing pipeline
print_status "Step 5: Running text processing pipeline..."

# Find or synthesize the downloaded text file
TEXT_DIR="$TEMP_DIR/batch_clean_txts"
TEXT_FILE="$TEXT_DIR/${STEM_NAME}_ocr.txt"

if [ ! -f "$TEXT_FILE" ]; then
    # If per-shard numeric files exist, concatenate them into the expected stem file
    SHARD_COUNT=$(ls -1 "$TEXT_DIR"/*.txt 2>/dev/null | wc -l | tr -d ' ')
    if [ "$SHARD_COUNT" -gt 0 ]; then
        print_status "Composing merged text from $SHARD_COUNT shard file(s) ..."
        # Natural sort to keep order stable
        ls -1 "$TEXT_DIR"/*.txt | sort | xargs cat > "$TEXT_FILE"
    fi
fi

if [ ! -f "$TEXT_FILE" ]; then
    print_error "Text file not found: $TEXT_FILE"
    print_error "Available files:"
    ls -la "$TEXT_DIR" 2>/dev/null || echo "No files found"
    exit 1
fi

print_status "Processing text file: $TEXT_FILE"

# Copy text file to current directory for processing scripts
cp "$TEXT_FILE" "$TEMP_DIR/input.txt"

# Step 5a: Clean up OCR text
print_status "Step 5a: Cleaning up OCR text..."
python3 text-processing/Step1_ocr_cleanup_v11.py "$TEMP_DIR/input.txt" "$TEMP_DIR/step1_output.txt"

if [ $? -ne 0 ]; then
    print_error "Text cleanup failed"
    exit 1
fi

# Step 5b: Format the text
print_status "Step 5b: Formatting text..."
python3 text-processing/Step2_formatting_v14.py "$TEMP_DIR/step1_output.txt" "$TEMP_DIR/step2_output.txt"

if [ $? -ne 0 ]; then
    print_error "Text formatting failed"
    exit 1
fi

# Step 5c: Structure chapters and insert HR
print_status "Step 5c: Structuring text..."
python3 text-processing/Step3_structuring_v1.py "$TEMP_DIR/step2_output.txt" "$TEMP_DIR/step3_output.txt"

if [ $? -ne 0 ]; then
    print_error "Additional formatting failed"
    exit 1
fi

print_success "Text processing completed"

# Step 6: Create EPUB
print_status "Step 6: Creating EPUB file..."

# Ensure output directory exists
mkdir -p output

# Create EPUB filename
EPUB_FILENAME="output/${STEM_NAME}.epub"

# Check if we need a template EPUB (Step4_create_epub.py might need one)
TEMPLATE_EPUB=""
if [ -f "template.epub" ]; then
    TEMPLATE_EPUB="template.epub"
else
    print_warning "No template.epub found. Creating a basic EPUB..."
    # Create a minimal template EPUB if none exists
    TEMPLATE_EPUB="$TEMP_DIR/template.epub"
    python3 -c "
import zipfile, os
from pathlib import Path

# Create a minimal EPUB template
template_dir = Path('$TEMP_DIR/epub_template')
template_dir.mkdir(exist_ok=True)

# Create META-INF directory
meta_inf = template_dir / 'META-INF'
meta_inf.mkdir(exist_ok=True)

# Create container.xml
with open(meta_inf / 'container.xml', 'w') as f:
    f.write('''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<container version=\"1.0\" xmlns=\"urn:oasis:names:tc:opendocument:xmlns:container\">
  <rootfiles>
    <rootfile full-path=\"OEBPS/content.opf\" media-type=\"application/oebps-package+xml\"/>
  </rootfiles>
</container>''')

# Create OEBPS directory
oebps = template_dir / 'OEBPS'
oebps.mkdir(exist_ok=True)

# Create mimetype file
with open(template_dir / 'mimetype', 'w') as f:
    f.write('application/epub+zip')

# Create basic content.opf
with open(oebps / 'content.opf', 'w') as f:
    f.write('''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<package xmlns=\"http://www.idpf.org/2007/opf\" unique-identifier=\"BookId\" version=\"2.0\">
  <metadata xmlns:dc=\"http://purl.org/dc/elements/1.1/\">
    <dc:title>Book Title</dc:title>
    <dc:creator>Unknown Author</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id=\"BookId\">book-id</dc:identifier>
  </metadata>
  <manifest>
    <item id=\"ncx\" href=\"toc.ncx\" media-type=\"application/x-dtbncx+xml\"/>
    <item id=\"content\" href=\"content.html\" media-type=\"application/xhtml+xml\"/>
  </manifest>
  <spine toc=\"ncx\">
    <itemref idref=\"content\"/>
  </spine>
</package>''')

# Create basic content.html
with open(oebps / 'content.html', 'w') as f:
    f.write('''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE html PUBLIC \"-//W3C//DTD XHTML 1.1//EN\" \"http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd\">
<html xmlns=\"http://www.w3.org/1999/xhtml\">
<head>
  <title>Book Content</title>
</head>
<body>
  <h1>Book Content</h1>
  <p>Content will be added here.</p>
</body>
</html>''')

# Create basic toc.ncx
with open(oebps / 'toc.ncx', 'w') as f:
    f.write('''<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<!DOCTYPE ncx PUBLIC \"-//NISO//DTD ncx 2005-1//EN\" \"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd\">
<ncx xmlns=\"http://www.daisy.org/z3986/2005/ncx/\" version=\"2005-1\">
  <head>
    <meta name=\"dtb:uid\" content=\"book-id\"/>
    <meta name=\"dtb:depth\" content=\"1\"/>
    <meta name=\"dtb:totalPageCount\" content=\"0\"/>
    <meta name=\"dtb:maxPageNumber\" content=\"0\"/>
  </head>
  <docTitle>
    <text>Book Title</text>
  </docTitle>
  <navMap>
    <navPoint id=\"navpoint-1\" playOrder=\"1\">
      <navLabel>
        <text>Chapter 1</text>
      </navLabel>
      <content src=\"content.html\"/>
    </navPoint>
  </navMap>
</ncx>''')

# Create EPUB file
with zipfile.ZipFile('$TEMPLATE_EPUB', 'w', zipfile.ZIP_DEFLATED) as epub:
    # Add mimetype first (uncompressed)
    epub.write(template_dir / 'mimetype', 'mimetype', compress_type=zipfile.ZIP_STORED)
    
    # Add all other files
    for root, dirs, files in os.walk(template_dir):
        for file in files:
            if file != 'mimetype':
                file_path = Path(root) / file
                arc_path = file_path.relative_to(template_dir)
                epub.write(file_path, arc_path)

print('Template EPUB created: $TEMPLATE_EPUB')
"
fi

# Run EPUB creation
python3 text-processing/Step4_epub_v10.py "$TEMP_DIR/step3_output.txt" "$EPUB_FILENAME"

if [ $? -ne 0 ]; then
    print_error "EPUB creation failed"
    exit 1
fi

# Step 7: Verify and report results
print_status "Step 7: Verifying results..."

if [ -f "$EPUB_FILENAME" ]; then
    EPUB_SIZE=$(du -h "$EPUB_FILENAME" | cut -f1)
    print_success "EPUB file created successfully!"
    print_success "File: $EPUB_FILENAME"
    print_success "Size: $EPUB_SIZE"
    
    # Show file details
    echo
    echo "=========================================="
    echo "Conversion Complete!"
    echo "=========================================="
    echo "Input PDF: $PDF_FILE"
    echo "Output EPUB: $EPUB_FILENAME"
    echo "File size: $EPUB_SIZE"
    echo "Processing time: $(date)"
    echo "=========================================="
    
else
    print_error "EPUB file was not created"
    exit 1
fi

print_success "PDF to EPUB conversion completed successfully! 🎉"
