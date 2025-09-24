#!/bin/bash

# Helper script to find Document AI processor ID
# Run this after creating a processor in the Google Cloud Console

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Document AI Processor ID Finder${NC}"
echo "=================================="
echo

# Check if user is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ You are not authenticated with Google Cloud."
    echo "Please run: gcloud auth login"
    exit 1
fi

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "❌ No active Google Cloud project found."
    echo "Please run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "✅ Using project: $PROJECT_ID"
echo

# Try to list processors using REST API
echo "🔍 Looking for Document AI processors..."

# Get access token
ACCESS_TOKEN=$(gcloud auth print-access-token 2>/dev/null)
if [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ Failed to get access token"
    exit 1
fi

# List processors using REST API
RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
    "https://eu-documentai.googleapis.com/v1/projects/$PROJECT_ID/locations/eu/processors" 2>/dev/null)

if echo "$RESPONSE" | grep -q "processors"; then
    echo "✅ Found processors:"
    echo
    echo "$RESPONSE" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if 'processors' in data:
        for proc in data['processors']:
            name = proc.get('name', '')
            display_name = proc.get('displayName', 'Unknown')
            # Extract processor ID from name
            if '/' in name:
                processor_id = name.split('/')[-1]
                print(f'📄 {display_name}')
                print(f'   Processor ID: {processor_id}')
                print(f'   Full name: {name}')
                print()
    else:
        print('No processors found')
except:
    print('Error parsing response')
"
else
    echo "❌ No processors found or API not accessible"
    echo
    echo "Please make sure:"
    echo "1. Document AI API is enabled"
    echo "2. You have created a processor in the Google Cloud Console"
    echo "3. The processor is in the 'eu' location"
    echo
    echo "Create a processor at: https://console.cloud.google.com/ai/document-ai/processors"
fi

echo
echo "💡 To use this processor ID in your .env file:"
echo "   GOOGLE_CLOUD_PROCESSOR_VERSION=projects/YOUR_PROJECT_NUMBER/locations/eu/processors/PROCESSOR_ID/processorVersions/pretrained-ocr-v2.0-2023-06-02"
echo
echo "   You can get your project number with:"
echo "   gcloud projects describe $PROJECT_ID --format='value(projectNumber)'"
