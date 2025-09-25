#!/usr/bin/env python3
"""
Batch OCR Process using Google Cloud Document AI API
Converts scanned PDFs to text using Google's OCR service
"""

import os
import json
import time
import requests
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DocumentAIOCR:
    def __init__(self):
        self.project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
        self.location = os.getenv('GOOGLE_CLOUD_LOCATION', 'eu')
        self.processor_version = os.getenv('GOOGLE_CLOUD_PROCESSOR_VERSION')
        self.input_prefix = os.getenv('INPUT_PREFIX')
        self.output_prefix = os.getenv('OUTPUT_PREFIX')
        
        if not all([self.project_id, self.processor_version, self.input_prefix, self.output_prefix]):
            raise ValueError("Missing required environment variables. Check your .env file.")
        
        self.access_token = self._get_access_token()
        self.date_prefix = datetime.now().strftime('%Y-%m-%d')
        
    def _get_access_token(self):
        """Get Google Cloud access token"""
        try:
            result = subprocess.run(['gcloud', 'auth', 'print-access-token'], 
                                 capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to get access token: {e}")
    
    def _get_pdf_files(self):
        """Get list of PDF files from input prefix"""
        try:
            result = subprocess.run(['gsutil', 'ls', f"{self.input_prefix}/*.pdf"], 
                                 capture_output=True, text=True, check=True)
            pdfs = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            if not pdfs:
                raise ValueError(f"No PDFs found at {self.input_prefix}")
            # If STEM is set, filter to just that file name
            stem = os.getenv('STEM')
            if stem:
                filtered = []
                for uri in pdfs:
                    base = os.path.basename(uri).rsplit('.pdf', 1)[0]
                    if base == stem:
                        filtered.append(uri)
                if not filtered:
                    raise ValueError(f"No PDF found for STEM={stem} under {self.input_prefix}")
                pdfs = filtered
            return pdfs
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to list PDFs: {e}")
    
    def _create_batch_request(self, pdfs):
        """Create JSON payload for batch processing"""
        documents = []
        for pdf in pdfs:
            documents.append({
                "gcsUri": pdf,
                "mimeType": "application/pdf"
            })
        
        request_data = {
            "inputDocuments": {
                "gcsDocuments": {
                    "documents": documents
                }
            },
            "documentOutputConfig": {
                "gcsOutputConfig": {
                    "gcsUri": f"{self.output_prefix}/{self.date_prefix}/batch_clean"
                }
            }
        }
        
        return request_data
    
    def _start_batch_process(self, request_data):
        """Start the batch processing operation"""
        url = f"https://{self.location}-documentai.googleapis.com/v1/{self.processor_version}:batchProcess"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "X-Goog-User-Project": self.project_id
        }
        
        response = requests.post(url, headers=headers, json=request_data)
        response.raise_for_status()
        
        result = response.json()
        operation_name = result.get('name')
        if not operation_name:
            raise RuntimeError(f"Failed to start batch: {result}")
        
        return operation_name
    
    def _wait_for_completion(self, operation_name):
        """Wait for batch processing to complete"""
        url = f"https://{self.location}-documentai.googleapis.com/v1/{operation_name}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Goog-User-Project": self.project_id
        }
        
        print(f"Batch started: {operation_name}")
        print("Waiting for completion", end="", flush=True)
        
        while True:
            time.sleep(5)
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            if result.get('done', False):
                break
            
            print(".", end="", flush=True)
        
        print("\nBatch finished.")
    
    def _merge_json_to_txt(self):
        """Merge per-volume JSON files to TXT"""
        scratch_dir = Path.home() / f"docai_text_{self.date_prefix}"
        scratch_dir.mkdir(exist_ok=True)
        
        # Ensure jq is available
        try:
            subprocess.run(['jq', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing jq...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'jq'], check=True)
        
        # Get volume directories
        try:
            result = subprocess.run(['gsutil', 'ls', '-d', f"{self.output_prefix}/{self.date_prefix}/batch_clean/*/"], 
                                 capture_output=True, text=True, check=True)
            vol_dirs = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        except subprocess.CalledProcessError:
            print("No volume directories found")
            return
        
        for vol_dir in vol_dirs:
            stem = vol_dir.rstrip('/').split('/')[-1]
            print(f"==> Merging text for {stem}")
            
            local_dir = scratch_dir / stem
            local_dir.mkdir(exist_ok=True)
            
            # Copy JSON files
            try:
                subprocess.run(['gsutil', '-m', 'cp', f"{vol_dir}**/*.json", str(local_dir)], 
                             check=True, capture_output=True)
            except subprocess.CalledProcessError:
                print("   (no JSONs)")
                continue
            
            # Merge JSON files to TXT
            json_files = sorted(local_dir.glob('*.json'))
            if not json_files:
                continue
            
            output_file = scratch_dir / f"{stem}_ocr.txt"
            with open(output_file, 'w') as f:
                for json_file in json_files:
                    try:
                        result = subprocess.run(['jq', '-r', '.text // empty', str(json_file)], 
                                             capture_output=True, text=True, check=True)
                        f.write(result.stdout)
                    except subprocess.CalledProcessError:
                        continue
            
            # Clean up leading blank lines
            clean_file = scratch_dir / f"{stem}_ocr_clean.txt"
            with open(output_file, 'r') as infile, open(clean_file, 'w') as outfile:
                lines = infile.readlines()
                # Remove leading empty lines
                start_idx = 0
                for i, line in enumerate(lines):
                    if line.strip():
                        start_idx = i
                        break
                outfile.writelines(lines[start_idx:])
            
            # Upload to GCS
            dest_path = f"{vol_dir.rstrip('/')}/{stem}_ocr.txt"
            subprocess.run(['gsutil', 'cp', str(clean_file), dest_path], check=True)
            print(f"   -> {dest_path}")
        
        print(f"All done. Output under: {self.output_prefix}/{self.date_prefix}/batch_clean")
    
    def run(self):
        """Run the complete OCR batch process"""
        print("Starting batch OCR process...")
        
        # Get PDF files
        pdfs = self._get_pdf_files()
        print(f"Found {len(pdfs)} PDF files to process")
        
        # If merged TXT already exists for STEM (for requested date or latest), skip
        stem = os.getenv('STEM')
        if stem:
            # 1) Date-specific path
            merged_txt_gcs = f"{self.output_prefix}/{self.date_prefix}/batch_clean/{stem}_ocr.txt"
            exists = subprocess.run(['gsutil', 'ls', merged_txt_gcs], capture_output=True).returncode == 0
            # 2) If not found, search latest by date
            if not exists:
                try:
                    result = subprocess.run(['bash', '-lc', f"gsutil ls '{self.output_prefix}/*/batch_clean/{stem}_ocr.txt' 2>/dev/null | sort | tail -n1"], capture_output=True, text=True, check=True)
                    latest = result.stdout.strip()
                    if latest:
                        print(f"Merged TXT already exists: {latest} — skipping OCR")
                        return
                except subprocess.CalledProcessError:
                    pass

        # Create batch request
        request_data = self._create_batch_request(pdfs)
        
        # Start batch processing
        operation_name = self._start_batch_process(request_data)
        
        # Wait for completion
        self._wait_for_completion(operation_name)
        
        # Merge JSON to TXT
        self._merge_json_to_txt()

def main():
    try:
        ocr = DocumentAIOCR()
        ocr.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
