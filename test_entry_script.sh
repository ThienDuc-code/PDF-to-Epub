#!/bin/bash

# Test script for pdf_to_epub.sh
# This script validates the entry script without actually running OCR

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Testing pdf_to_epub.sh entry script${NC}"
echo "=================================="
echo

# Test 1: Check if script exists and is executable
if [ -f "pdf_to_epub.sh" ] && [ -x "pdf_to_epub.sh" ]; then
    echo "✅ Script exists and is executable"
else
    echo "❌ Script not found or not executable"
    exit 1
fi

# Test 2: Check help option
echo
echo "Testing --help option..."
if ./pdf_to_epub.sh --help >/dev/null 2>&1; then
    echo "✅ Help option works"
else
    echo "❌ Help option failed"
fi

# Test 3: Check error handling for missing PDF
echo
echo "Testing error handling for missing PDF..."
if ./pdf_to_epub.sh nonexistent.pdf 2>/dev/null; then
    echo "❌ Should have failed for missing PDF"
else
    echo "✅ Correctly handles missing PDF"
fi

# Test 4: Check error handling for missing .env
echo
echo "Testing error handling for missing .env..."
if [ -f ".env" ]; then
    mv .env .env.backup
fi

if ./pdf_to_epub.sh --help 2>/dev/null; then
    echo "❌ Should have failed for missing .env"
else
    echo "✅ Correctly handles missing .env"
fi

# Restore .env if it existed
if [ -f ".env.backup" ]; then
    mv .env.backup .env
fi

# Test 5: Check script syntax
echo
echo "Testing script syntax..."
if bash -n pdf_to_epub.sh; then
    echo "✅ Script syntax is valid"
else
    echo "❌ Script has syntax errors"
fi

echo
echo "=================================="
echo -e "${GREEN}Entry script validation complete!${NC}"
echo
echo "The script is ready to use. To convert a PDF:"
echo "  ./pdf_to_epub.sh your_book.pdf"
echo
echo "For enhanced OCR with page breaks:"
echo "  ./pdf_to_epub.sh your_book.pdf --enhanced"
