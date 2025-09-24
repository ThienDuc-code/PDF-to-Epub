#!/usr/bin/env python3
"""
Merge One Book (JSON to TXT)
Merges OCR results from a single volume into a text file
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MergeOneBook:
    def __init__(self, stem=None):
        self.date_prefix = os.getenv('DATE_PREFIX', datetime.now().strftime('%Y-%m-%d'))
        self.output_prefix = os.getenv('OUTPUT_PREFIX', f"gs://pdf-ocr-books/docai-output/{self.date_prefix}/batch_clean")
        self.scratch_dir = Path.home() / f"docai_merge_{self.date_prefix}"
        self.stem = stem or os.getenv('STEM', 'HOL_Vol1')
        
        self.scratch_dir.mkdir(exist_ok=True)
        
    def _ensure_jq(self):
        """Ensure jq is available"""
        try:
            subprocess.run(['jq', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing jq...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'jq'], check=True)
    
    def merge_volume(self):
        """Merge one volume's OCR results"""
        print(f"Merging volume: {self.stem}")
        
        self._ensure_jq()
        
        # Create local directory for this volume
        local_dir = self.scratch_dir / self.stem
        local_dir.mkdir(exist_ok=True)
        
        # Pull all shards for this volume (handles nested shard folders like /0/, /1/, …)
        try:
            subprocess.run(['gsutil', '-m', 'cp', f"{self.output_prefix}/**/{self.stem}-*.json", str(local_dir)], 
                         check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error copying JSON files: {e}")
            return False
        
        # Get all JSON files and sort them naturally
        json_files = sorted(local_dir.glob('*.json'))
        if not json_files:
            print(f"No JSON files found for {self.stem}")
            return False
        
        print(f"Found {len(json_files)} JSON files to merge")
        
        # Merge JSON files to TXT
        output_file = self.scratch_dir / f"{self.stem}_ocr.txt"
        
        with open(output_file, 'w') as f:
            for json_file in json_files:
                try:
                    result = subprocess.run(['jq', '-r', '.text // empty', str(json_file)], 
                                         capture_output=True, text=True, check=True)
                    f.write(result.stdout)
                except subprocess.CalledProcessError as e:
                    print(f"Error processing {json_file}: {e}")
                    continue
        
        # Optional: trim leading blank lines
        clean_file = self.scratch_dir / f"{self.stem}_ocr_clean.txt"
        with open(output_file, 'r') as infile, open(clean_file, 'w') as outfile:
            lines = infile.readlines()
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    start_idx = i
                    break
            outfile.writelines(lines[start_idx:])
        
        # Put the merged TXT next to the batch outputs (easy to find)
        dest_path = f"{self.output_prefix}/{self.stem}_ocr.txt"
        try:
            subprocess.run(['gsutil', 'cp', str(clean_file), dest_path], check=True)
            print(f"-> {dest_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error uploading to GCS: {e}")
            return False
        
        # Clean up local files
        output_file.unlink(missing_ok=True)
        clean_file.unlink(missing_ok=True)
        
        return True
    
    def run(self):
        """Run the merge process for one volume"""
        print(f"Starting merge process for {self.stem}...")
        
        success = self.merge_volume()
        if success:
            print(f"Successfully merged {self.stem}")
        else:
            print(f"Failed to merge {self.stem}")
            return 1
        
        return 0

def main():
    import sys
    
    # Allow stem to be passed as command line argument
    stem = sys.argv[1] if len(sys.argv) > 1 else None
    
    try:
        merger = MergeOneBook(stem)
        return merger.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
