#!/usr/bin/env python3
"""
Merge All Books (JSON to TXT)
Merges OCR results from multiple volumes into individual text files
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MergeAllBooks:
    def __init__(self):
        self.date_prefix = os.getenv('DATE_PREFIX', datetime.now().strftime('%Y-%m-%d'))
        self.batch_root = os.getenv('BATCH_ROOT', f"gs://pdf-ocr-books/docai-output/{self.date_prefix}/batch_clean")
        self.merged_dir = os.getenv('MERGED_DIR', f"gs://pdf-ocr-books/docai-output/{self.date_prefix}/merged_txt")
        self.tmp_dir = Path(f"/tmp/docai_merge_{self.date_prefix}")
        self.tmp_dir.mkdir(exist_ok=True)
        
    def _ensure_jq(self):
        """Ensure jq is available"""
        try:
            subprocess.run(['jq', '--version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Installing jq...")
            subprocess.run(['sudo', 'apt-get', 'update', '-y'], check=True)
            subprocess.run(['sudo', 'apt-get', 'install', '-y', 'jq'], check=True)
    
    def _ensure_merged_dir(self):
        """Ensure merged directory exists in GCS"""
        try:
            subprocess.run(['gsutil', '-q', 'ls', self.merged_dir], 
                         capture_output=True, check=True)
        except subprocess.CalledProcessError:
            print(f"Creating merged directory: {self.merged_dir}")
            subprocess.run(['gsutil', '-q', 'cp', '/dev/null', f"{self.merged_dir}/.init"], 
                         capture_output=True)
    
    def merge_one_volume(self, stem):
        """Merge one volume's OCR results"""
        tmp_txt = self.tmp_dir / f"{stem}_ocr.txt"
        tmp_txt_clean = self.tmp_dir / f"{stem}_ocr_clean.txt"
        
        # Collect ALL page JSONs for this stem anywhere under batch_clean/
        try:
            result = subprocess.run(['gsutil', 'ls', '-r', f"{self.batch_root}/**/{stem}-*.json"], 
                                 capture_output=True, text=True, check=True)
            objects = sorted([line.strip() for line in result.stdout.split('\n') if line.strip()])
        except subprocess.CalledProcessError:
            objects = []
        
        total = len(objects)
        if total == 0:
            print(f"==> {stem}: no JSON pages found yet, skipping.")
            return
        
        print(f"==> {stem}: merging {total} pages…")
        tmp_txt.write_text('')
        
        for n, obj in enumerate(objects, 1):
            print(f"\r    {stem}  {n}/{total}", end="", flush=True)
            try:
                result = subprocess.run(['gsutil', 'cat', obj], capture_output=True, text=True, check=True)
                text_result = subprocess.run(['jq', '-r', '.text // empty'], 
                                           input=result.stdout, capture_output=True, text=True, check=True)
                with open(tmp_txt, 'a') as f:
                    f.write(text_result.stdout)
            except subprocess.CalledProcessError:
                continue
        
        print()
        
        # Trim leading empties
        with open(tmp_txt, 'r') as infile, open(tmp_txt_clean, 'w') as outfile:
            lines = infile.readlines()
            start_idx = 0
            for i, line in enumerate(lines):
                if line.strip():
                    start_idx = i
                    break
            outfile.writelines(lines[start_idx:])
        
        # Upload to GCS
        subprocess.run(['gsutil', 'cp', str(tmp_txt_clean), f"{self.merged_dir}/{stem}_ocr.txt"], check=True)
        print(f"    → {self.merged_dir}/{stem}_ocr.txt")
        
        # Clean up temp files
        tmp_txt.unlink(missing_ok=True)
        tmp_txt_clean.unlink(missing_ok=True)
        
        # Show /tmp usage
        result = subprocess.run(['df', '-h', '/tmp'], capture_output=True, text=True, check=True)
        lines = result.stdout.split('\n')
        print(lines[0])  # Header
        for line in lines[1:]:
            if '/tmp' in line:
                print(line)
                break
        print()
    
    def run(self):
        """Run the merge process for all volumes"""
        print("Starting merge process for all books...")
        
        self._ensure_jq()
        self._ensure_merged_dir()
        
        # Merge volumes 1-12
        for i in range(1, 13):
            self.merge_one_volume(f"HOL_Vol{i}")
        
        # Remove marker if we created it
        try:
            subprocess.run(['gsutil', '-q', 'rm', f"{self.merged_dir}/.init"], 
                         capture_output=True)
        except subprocess.CalledProcessError:
            pass
        
        print(f"All done. Merged TXTs are in: {self.merged_dir}")

def main():
    try:
        merger = MergeAllBooks()
        merger.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    exit(main())
