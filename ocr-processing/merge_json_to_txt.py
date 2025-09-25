#!/usr/bin/env python3
"""
Merge JSON and Save as TXT
Alternative implementation for merging OCR results with different approach
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MergeJsonToTxt:
    def __init__(self):
        self.date_prefix = os.getenv('DATE_PREFIX', datetime.now().strftime('%Y-%m-%d'))
        self.output_prefix = os.getenv('OUTPUT_PREFIX', f"gs://pdf-ocr-books/docai-output/{self.date_prefix}/batch_clean")
        self.scratch_dir = Path.home() / f"docai_text_{self.date_prefix}"
        self.scratch_dir.mkdir(exist_ok=True)
        
    def _ensure_jq(self):
        """Ensure jq is available"""
        try:
            subprocess.run(['jq', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing jq...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'jq'], check=True)
    
    def merge_volumes(self):
        """Merge all volumes' OCR results"""
        self._ensure_jq()
        
        # Get volume directories
        try:
            result = subprocess.run(['gsutil', 'ls', '-d', f"{self.output_prefix}/*/"], 
                                 capture_output=True, text=True, check=True)
            vol_dirs = [line.strip() for line in result.stdout.split('\n') if line.strip()]
        except subprocess.CalledProcessError:
            print("No volume directories found")
            return False
        
        for vol_dir in vol_dirs:
            stem = vol_dir.rstrip('/').split('/')[-1]
            print(f"==> Merging {stem}")
            
            local_dir = self.scratch_dir / stem
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
            
            output_file = self.scratch_dir / f"{stem}_ocr.txt"
            with open(output_file, 'w') as f:
                for json_file in json_files:
                    try:
                        result = subprocess.run(['jq', '-r', '.text // empty', str(json_file)], 
                                             capture_output=True, text=True, check=True)
                        f.write(result.stdout)
                    except subprocess.CalledProcessError:
                        continue
            
            # Clean up leading blank lines
            clean_file = self.scratch_dir / f"{stem}_ocr_clean.txt"
            with open(output_file, 'r') as infile, open(clean_file, 'w') as outfile:
                lines = infile.readlines()
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
        
        print(f"Merged TXT files are alongside each volume's JSONs under {self.output_prefix}")
        return True
    
    def run(self):
        """Run the merge process"""
        print("Starting JSON to TXT merge process...")
        
        success = self.merge_volumes()
        if success:
            print("Merge process completed successfully")
        else:
            print("Merge process failed")
            return 1
        
        return 0

def main():
    try:
        merger = MergeJsonToTxt()
        return merger.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
