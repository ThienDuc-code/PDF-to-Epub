#!/usr/bin/env bash

# macOS Setup Script for PDF to EPUB Project
# This script sets up the complete environment for Google Cloud Document AI OCR processing

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

# Function to prompt for user input
prompt_input() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    if [ -n "$default" ]; then
        read -p "$prompt [$default]: " input
        eval "$var_name=\${input:-$default}"
    else
        read -p "$prompt: " input
        eval "$var_name=\"$input\""
    fi
}

# Function to prompt for yes/no
prompt_yes_no() {
    local prompt="$1"
    local default="$2"
    local var_name="$3"
    
    while true; do
        if [ -n "$default" ]; then
            read -p "$prompt [Y/n]: " yn
            yn=${yn:-$default}
        else
            read -p "$prompt [y/N]: " yn
        fi
        
        case $yn in
            [Yy]* ) eval "$var_name=true"; break;;
            [Nn]* ) eval "$var_name=false"; break;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

echo "=========================================="
echo "PDF to EPUB - macOS Setup Script"
echo "=========================================="
echo

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is designed for macOS only."
    exit 1
fi

print_status "Starting setup process..."

# Step 1: Check and install Homebrew
print_status "Checking for Homebrew..."
if ! command_exists brew; then
    print_warning "Homebrew not found. Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon Macs
    if [[ $(uname -m) == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zshrc
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    
    print_success "Homebrew installed successfully"
else
    print_success "Homebrew is already installed"
fi

# Step 2: Install Python and pip
print_status "Checking Python installation..."
if ! command_exists python3; then
    print_warning "Python 3 not found. Installing Python..."
    brew install python
    print_success "Python installed successfully"
else
    print_success "Python 3 is already installed"
fi

# Step 3: Install Google Cloud SDK
print_status "Checking Google Cloud SDK installation..."
if ! command_exists gcloud; then
    print_warning "Google Cloud SDK not found. Installing..."
    
    # Download and install gcloud
    curl https://sdk.cloud.google.com | bash
    
    # Add gcloud to PATH
    echo 'source ~/google-cloud-sdk/path.bash.inc' >> ~/.zshrc
    echo 'source ~/google-cloud-sdk/completion.bash.inc' >> ~/.zshrc
    source ~/google-cloud-sdk/path.bash.inc
    
    print_success "Google Cloud SDK installed successfully"
else
    print_success "Google Cloud SDK is already installed"
fi

# Step 4: Install Python packages
print_status "Installing Python packages..."
if [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt
    print_success "Python packages installed successfully"
else
    print_error "requirements.txt not found!"
    exit 1
fi

# Step 5: Create .env file
print_status "Setting up environment configuration..."

if [ -f ".env" ]; then
    print_warning ".env file already exists."
    prompt_yes_no "Do you want to overwrite it?" "n" "overwrite_env"
    if [ "$overwrite_env" = false ]; then
        print_status "Using existing .env file"
    else
        cp env.template .env
        print_success "Created new .env file from template"
    fi
else
    cp env.template .env
    print_success "Created .env file from template"
fi

# Load existing .env values to reuse as defaults
if [ -f ".env" ]; then
    # export variables from .env without printing
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

# Derive sensible defaults from existing .env if available
DEFAULT_PROJECT_ID="${GOOGLE_CLOUD_PROJECT_ID:-}"
DEFAULT_PROCESSOR_VERSION="${GOOGLE_CLOUD_PROCESSOR_VERSION:-}"
# Extract processor ID from version path if present
DEFAULT_PROCESSOR_ID=""
if [ -n "$DEFAULT_PROCESSOR_VERSION" ]; then
    DEFAULT_PROCESSOR_ID=$(printf "%s\n" "$DEFAULT_PROCESSOR_VERSION" | sed -n 's#.*/processors/\([^/]*\)/.*#\1#p')
fi

# Location default
DEFAULT_LOCATION="${GOOGLE_CLOUD_LOCATION:-eu}"

# Prefer bucket from INPUT_PREFIX, fallback to OUTPUT_PREFIX
DEFAULT_BUCKET_NAME=""
if [ -n "${INPUT_PREFIX:-}" ]; then
    DEFAULT_BUCKET_NAME=$(printf "%s\n" "$INPUT_PREFIX" | sed -n 's#gs://\([^/]*\).*#\1#p')
fi
if [ -z "$DEFAULT_BUCKET_NAME" ] && [ -n "${OUTPUT_PREFIX:-}" ]; then
    DEFAULT_BUCKET_NAME=$(printf "%s\n" "$OUTPUT_PREFIX" | sed -n 's#gs://\([^/]*\).*#\1#p')
fi

# Step 6: Configure Google Cloud
print_status "Configuring Google Cloud..."

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    print_warning "You are not authenticated with Google Cloud."
    print_status "Please authenticate with Google Cloud..."
    gcloud auth login
    gcloud auth application-default login
    print_success "Google Cloud authentication completed"
else
    print_success "Google Cloud authentication verified"
fi

# Step 7: Get Google Cloud project information
print_status "Getting Google Cloud project information..."

# List available projects
print_status "Available Google Cloud projects:"
gcloud projects list --format="table(projectId,name)"

echo
# Use existing project id as default if present
prompt_input "Enter your Google Cloud Project ID" "$DEFAULT_PROJECT_ID" "PROJECT_ID"

# Set the project
gcloud config set project "$PROJECT_ID"
print_success "Set active project to: $PROJECT_ID"

# Step 8: Enable required APIs
print_status "Enabling required Google Cloud APIs..."
gcloud services enable documentai.googleapis.com
gcloud services enable storage.googleapis.com
print_success "Required APIs enabled"

# Step 9: Create Document AI processor
print_status "Setting up Document AI processor..."

# Check if Document AI API is available
if ! gcloud services list --enabled --filter="name:documentai.googleapis.com" --format="value(name)" | grep -q "documentai.googleapis.com"; then
    print_warning "Document AI API not enabled. Enabling it now..."
    gcloud services enable documentai.googleapis.com
    print_success "Document AI API enabled"
fi

# Document AI processors must be created through the Google Cloud Console
# We'll provide instructions instead of trying to create via CLI
print_warning "Document AI processors must be created through the Google Cloud Console."
print_status "Please follow these steps:"
echo
echo "1. Go to: https://console.cloud.google.com/ai/document-ai/processor-library"
echo "2. Click 'Document OCR'"
echo "3. Give it a name like 'PDF-OCR-Processor'"
echo "4. Choose location: 'eu' (Europe)"
echo "5. Click 'Create'"
echo
echo "After creating the processor, you'll need to:"
echo "- Copy the processor ID from the URL or processor details"
echo "- Update your .env file with the correct processor version"
echo

prompt_input "Enter your Document AI Processor ID (found in the processor URL)" "$DEFAULT_PROCESSOR_ID" "PROCESSOR_ID"

# Location selection (default to existing or eu)
prompt_input "Enter your Document AI Location (eu/us)" "$DEFAULT_LOCATION" "LOCATION"
GOOGLE_CLOUD_LOCATION="$LOCATION"

if [ -z "$PROCESSOR_ID" ]; then
    print_error "Processor ID is required. Please create a processor in the Google Cloud Console first."
    exit 1
fi

# Get project number for the processor version
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
PROCESSOR_VERSION="projects/$PROJECT_NUMBER/locations/$GOOGLE_CLOUD_LOCATION/processors/$PROCESSOR_ID/processorVersions/pretrained-ocr-v2.0-2023-06-02"

print_success "Using processor: $PROCESSOR_ID"
print_status "Processor version: $PROCESSOR_VERSION"

# Step 11: Configure storage bucket
print_status "Setting up Google Cloud Storage..."

prompt_input "Enter your bucket name (will be created if it doesn't exist)" "$DEFAULT_BUCKET_NAME" "BUCKET_NAME"

# Check if bucket exists
if gsutil ls -b "gs://$BUCKET_NAME" >/dev/null 2>&1; then
    print_success "Bucket gs://$BUCKET_NAME already exists"
else
    print_warning "Creating bucket gs://$BUCKET_NAME..."
    gsutil mb "gs://$BUCKET_NAME"
    print_success "Bucket gs://$BUCKET_NAME created successfully"
fi

# Step 12: Configure .env file with user inputs
print_status "Updating .env file with your configuration..."

# Update .env file only where placeholders still exist
# Project ID
if grep -q "^GOOGLE_CLOUD_PROJECT_ID=your-project-id-here" .env; then
    sed -i '' "s/^GOOGLE_CLOUD_PROJECT_ID=.*/GOOGLE_CLOUD_PROJECT_ID=$PROJECT_ID/" .env
else
    print_status "GOOGLE_CLOUD_PROJECT_ID already set; leaving as-is"
fi

# Project Number placeholder (used in processor version path)
if grep -q "YOUR_PROJECT_NUMBER" .env; then
    sed -i '' "s/YOUR_PROJECT_NUMBER/$PROJECT_NUMBER/g" .env
fi

# Processor ID placeholder
if grep -q "YOUR_PROCESSOR_ID" .env; then
    sed -i '' "s/YOUR_PROCESSOR_ID/$PROCESSOR_ID/g" .env
fi

# Processor version alias placeholder
if grep -q "YOUR_VERSION" .env; then
    sed -i '' "s/YOUR_VERSION/pretrained-ocr-v2.0-2023-06-02/g" .env
fi

# Bucket name placeholder
if grep -q "your-bucket-name" .env; then
    sed -i '' "s/your-bucket-name/$BUCKET_NAME/g" .env
fi

# Location value
if grep -q "^GOOGLE_CLOUD_LOCATION=" .env; then
    # If it's placeholder or empty, set it; otherwise leave as-is
    if grep -q "^GOOGLE_CLOUD_LOCATION=eu$" .env || grep -q "^GOOGLE_CLOUD_LOCATION=$" .env; then
        sed -i '' "s/^GOOGLE_CLOUD_LOCATION=.*/GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION/" .env
    fi
else
    echo "GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION" >> .env
fi

# Processor version: if placeholder path remains, replace entirely
if grep -q "^GOOGLE_CLOUD_PROCESSOR_VERSION=projects/" .env; then
    sed -i '' "s#^GOOGLE_CLOUD_PROCESSOR_VERSION=.*#GOOGLE_CLOUD_PROCESSOR_VERSION=$PROCESSOR_VERSION#" .env
fi

# Paths: only replace template paths if still present
if grep -q "^INPUT_PREFIX=gs://your-bucket-name/your-pdf-folder" .env; then
    INPUT_PREFIX="gs://$BUCKET_NAME/pdfs"
    sed -i '' "s|^INPUT_PREFIX=.*|INPUT_PREFIX=$INPUT_PREFIX|" .env
fi
if grep -q "^OUTPUT_PREFIX=gs://your-bucket-name/docai-output" .env; then
    OUTPUT_PREFIX="gs://$BUCKET_NAME/docai-output"
    sed -i '' "s|^OUTPUT_PREFIX=.*|OUTPUT_PREFIX=$OUTPUT_PREFIX|" .env
fi

print_success "Updated .env file with your configuration"

# Step 13: Create input directory structure
print_status "Creating input directory structure..."
gsutil -m mkdir -p "$INPUT_PREFIX" 2>/dev/null || true
print_success "Created input directory: $INPUT_PREFIX"

# Step 14: Test the setup
print_status "Testing the setup..."

# Test Python packages
python3 -c "import requests, dotenv; print('Python packages working')" 2>/dev/null && \
    print_success "Python packages test passed" || \
    print_error "Python packages test failed"

# Test gcloud
gcloud version >/dev/null 2>&1 && \
    print_success "Google Cloud SDK test passed" || \
    print_error "Google Cloud SDK test failed"

# Test Document AI via REST (more reliable than gcloud subcommand)
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null || true)
DOC_AI_LOCATION="${GOOGLE_CLOUD_LOCATION:-eu}"
DOC_AI_PROJECT="${PROJECT_ID:-$GOOGLE_CLOUD_PROJECT_ID}"
if [ -n "$ACCESS_TOKEN" ] && [ -n "$DOC_AI_PROJECT" ]; then
    DOC_AI_URL="https://$DOC_AI_LOCATION-documentai.googleapis.com/v1/projects/$DOC_AI_PROJECT/locations/$DOC_AI_LOCATION/processors"
    DOC_AI_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $ACCESS_TOKEN" "$DOC_AI_URL" || echo "000")
    if [ "$DOC_AI_HTTP_CODE" = "200" ]; then
        print_success "Document AI API test passed"
    else
        print_error "Document AI API test failed (HTTP $DOC_AI_HTTP_CODE)"
        print_status "If you recently enabled the API, wait a minute and retry."
        print_status "Ensure ADC is configured: gcloud auth application-default login"
        print_status "Check that GOOGLE_CLOUD_LOCATION and project are correct in .env"
    fi
else
    print_error "Document AI API test skipped: missing access token or project ID"
fi

# Test Storage
gsutil ls "gs://$BUCKET_NAME" >/dev/null 2>&1 && \
    print_success "Cloud Storage test passed" || \
    print_error "Cloud Storage test failed"

# Step 15: Final instructions
echo
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo
print_success "Your environment is now configured and ready to use!"
echo
echo "Configuration Summary:"
echo "  Project ID: $PROJECT_ID"
echo "  Bucket: gs://$BUCKET_NAME"
echo "  Input Path: $INPUT_PREFIX"
echo "  Output Path: $OUTPUT_PREFIX"
echo "  Processor ID: $PROCESSOR_ID"
echo "  Processor Version: $PROCESSOR_VERSION"
echo
echo "Next steps:"
echo "1. Upload your PDF files to: $INPUT_PREFIX"
echo "   Example: gsutil -m cp *.pdf $INPUT_PREFIX/"
echo
echo "2. Run OCR processing:"
echo "   python3 ocr-processing/batch_ocr_process.py"
echo
echo "3. Or run the enhanced version with page breaks:"
echo "   python3 ocr-processing/batch_ocr_with_page_breaks.py"
echo
echo "4. Merge the results:"
echo "   python3 ocr-processing/merge_all_books.py"
echo
echo "5. Download processed text:"
echo "   python3 ocr-processing/download_txt_files.py"
echo
echo "Your configuration is saved in .env file."
echo "You can modify it anytime to change settings."
echo
print_status "Happy OCR processing! 🚀"
