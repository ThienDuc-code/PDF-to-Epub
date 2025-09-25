#!/usr/bin/env python3
"""
Download TXT Files
Downloads processed text files from Google Cloud Storage and packages them for easy transfer
"""

import os
import subprocess
import zipfile
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class DownloadTxtFiles:
    def __init__(self):
        self.date_prefix = os.getenv('DATE_PREFIX', datetime.now().strftime('%Y-%m-%d'))
        output_prefix = os.getenv('OUTPUT_PREFIX')
        # Prefer OUTPUT_PREFIX if available, otherwise fall back to legacy bucket
        default_src = f"{output_prefix}/{self.date_prefix}/batch_clean/" if output_prefix else f"gs://pdf-ocr-books/docai-output/{self.date_prefix}/batch_clean/"
        self.src_prefix = os.getenv('SRC_PREFIX', default_src)
        self.stem = os.getenv('STEM')
        # Write under project temp folder when available
        project_temp = Path.cwd() / "temp"
        project_temp.mkdir(exist_ok=True)
        self.local_dir = project_temp / "batch_clean_txts"
        
    def download_and_package(self):
        """Download TXT files and package them into a zip file"""
        print(f"==> Copying only TXT files from {self.src_prefix} ...")
        
        # Clean up existing local directory
        if self.local_dir.exists():
            import shutil
            shutil.rmtree(self.local_dir)
        self.local_dir.mkdir(exist_ok=True)
        
        # Copy TXT files from GCS
        try:
            # Batch output stores TXT inside one-level subfolders; copy those
            pattern = f"{self.src_prefix}*/*.txt"
            subprocess.run(['gsutil', '-m', 'cp', pattern, str(self.local_dir)], 
                         check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error copying files: {e}")
            # Do not return here; we might still have a root-level merged TXT

        # Also try to pull a root-level merged TXT for the stem, if known
        if self.stem:
            root_txt = f"{self.src_prefix}{self.stem}_ocr.txt"
            try:
                subprocess.run(['gsutil', 'cp', root_txt, str(self.local_dir)], check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # It's ok if it doesn't exist
                pass
        
        # Count downloaded files
        txt_files = list(self.local_dir.glob('*.txt'))
        print(f"Downloaded {len(txt_files)} TXT files")
        if not txt_files:
            print("No TXT files found to download. Check SRC_PREFIX and date.")
            return False
        
        # Package into zip for easy download
        print("==> Packaging into zip for easy download ...")
        zip_path = Path.home() / "batch_clean_txts.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for txt_file in txt_files:
                zipf.write(txt_file, txt_file.name)
        
        print(f"==> Ready to transfer. Zip file created: {zip_path}")
        print(f"File size: {zip_path.stat().st_size / (1024*1024):.1f} MB")
        
        return True
    
    def run(self):
        """Run the download and packaging process"""
        print("Starting download and packaging process...")
        
        success = self.download_and_package()
        if success:
            print("\nTo download the zip file to your local computer, run:")
            print("cloudshell download batch_clean_txts.zip")
        else:
            print("Download failed")
            return 1
        
        return 0

def main():
    try:
        downloader = DownloadTxtFiles()
        return downloader.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
