# PDF to Text Converter

This project provides a minimal `pdftotxt` command line interface for extracting
text from PDF files. The tool supports basic text extraction, optional OCR using
`tesseract`, page selection, and simple normalization options. Output can be
written to plain text or JSON files.

## Features

- Extract text from PDFs with embedded text using PyPDF2.
- Fallback to OCR (Tesseract) for pages without text.
- Page selection using ranges (e.g. `1,3-5`).
- Optional normalization: dehyphenation, whitespace collapsing, Unicode NFKC/NFC.
- Optional metadata export.
- JSON structured output.

## Usage

```bash
pdftotxt <input.pdf> [--output out.txt] [--pages 1-3] [--mode auto|text-only|ocr-only]
          [--lang eng] [--layout plain|pages-delimited]
          [--normalize dehyphen,collapse_ws,nfkc] [--metadata] [--json out.json]
```

Run `pdftotxt --help` for the full list of options.

## Notes

- OCR requires the optional `pdf2image` and `pytesseract` dependencies.
- This implementation is a simplified baseline and does not cover the entire
  specification.
