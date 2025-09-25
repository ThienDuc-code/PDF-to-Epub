# PDF to EPUB

Make the wisdom of the world readable.

This is a set of Python scripts to convert scanned PDF books to EPUB. It uses the [Google's Document AI](https://cloud.google.com/document-ai) to convert scanned PDFs to text and then performs cleanup and enhancements in Python.

## Install

For macOS users, we provide an automated setup script that handles everything:

```bash
chmod +x *.sh
./setup_macos.sh
```

If you're not on macOS or don't want to use Homebrew, please see [manual setup](docs/manual-setup.md).

## Quick Start

After running the setup script, you can convert any PDF to EPUB with this command:

```bash
./pdf_to_epub.sh your_book.pdf
```

This will:
1. Check if the PDF exists on Google Cloud Storage (upload if needed)
2. Run OCR processing using Google Cloud Document AI
3. Merge OCR results into text files
4. Download processed text
5. Clean up and format the text
6. Create an EPUB file
7. Save the EPUB in the `output/` folder

For a detailed description of the different parts of this project and what they do, see [this overview](docs/overview.md).

## Contributors
Totally vibe coded by [br Thien Duc](https://github.com/ThienDuc-code) and [br Duc Pho](https://github.com/ducpho).