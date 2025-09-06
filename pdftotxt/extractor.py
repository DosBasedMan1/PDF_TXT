import argparse
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

try:
    from PyPDF2 import PdfReader
except Exception as exc:  # pragma: no cover - PyPDF2 may not be installed
    PdfReader = None

try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception:  # pragma: no cover - OCR optional
    convert_from_path = None
    pytesseract = None


@dataclass
class PageSpec:
    pages: Optional[List[int]] = None

    @staticmethod
    def parse(spec: Optional[str]) -> "PageSpec":
        if not spec:
            return PageSpec()
        pages: List[int] = []
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start, end = part.split("-", 1)
                pages.extend(range(int(start), int(end) + 1))
            else:
                pages.append(int(part))
        return PageSpec(sorted(set(pages)))


@dataclass
class ExtractOptions:
    pages: PageSpec = field(default_factory=PageSpec)
    mode: str = "auto"  # auto|text-only|ocr-only
    layout: str = "plain"  # plain|layout-preserve|pages-delimited
    ocr_langs: Optional[str] = None
    normalize: Optional[List[str]] = None
    metadata: bool = False
    page_separator: str = "\n\n===== [Page {page}] =====\n"


@dataclass
class ExtractResult:
    text: str
    pages: List[str]
    metadata: Optional[dict]


def _normalize_text(text: str, opts: ExtractOptions) -> str:
    if not opts.normalize:
        return text
    if "nfkc" in opts.normalize:
        text = unicodedata.normalize("NFKC", text)
    if "nfc" in opts.normalize:
        text = unicodedata.normalize("NFC", text)
    if "dehyphen" in opts.normalize:
        text = re.sub(r"(?<=\w)-\n(?=\w)", "", text)
    if "collapse_ws" in opts.normalize:
        text = re.sub(r"\s+", " ", text)
    return text


def _extract_text_from_page(reader: PdfReader, page_number: int) -> str:
    page = reader.pages[page_number]
    try:
        txt = page.extract_text() or ""
    except Exception:
        txt = ""
    return txt


def _ocr_page(pdf_path: str, page_number: int, opts: ExtractOptions) -> str:
    if convert_from_path is None or pytesseract is None:
        raise RuntimeError("OCR dependencies are missing")
    images = convert_from_path(pdf_path, first_page=page_number + 1, last_page=page_number + 1)
    config = ""
    if opts.ocr_langs:
        config = f"-l {opts.ocr_langs}"
    text = pytesseract.image_to_string(images[0], config=config)
    return text


def extract_pdf(path: str, opts: ExtractOptions, password: Optional[str] = None) -> ExtractResult:
    if PdfReader is None:
        raise RuntimeError("PyPDF2 is not installed")
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    reader = PdfReader(path, password=password) if password else PdfReader(path)
    num_pages = len(reader.pages)

    pages_to_process = opts.pages.pages or list(range(1, num_pages + 1))
    results: List[str] = []
    for p in pages_to_process:
        if p < 1 or p > num_pages:
            continue
        text = ""
        if opts.mode in ("auto", "text-only"):
            text = _extract_text_from_page(reader, p - 1)
        if not text and opts.mode in ("auto", "ocr-only"):
            text = _ocr_page(path, p - 1, opts)
        text = _normalize_text(text, opts)
        if opts.layout == "pages-delimited":
            header = opts.page_separator.format(page=p)
            text = header + text
        results.append(text)

    full_text = "\n".join(results)

    metadata = None
    if opts.metadata:
        info = reader.metadata or {}
        metadata = {
            "title": info.get("/Title"),
            "author": info.get("/Author"),
            "creator": info.get("/Creator"),
            "producer": info.get("/Producer"),
            "page_count": num_pages,
        }

    return ExtractResult(text=full_text, pages=results, metadata=metadata)


def write_output(result: ExtractResult, output_path: str, json_path: Optional[str] = None, force: bool = False) -> None:
    if output_path and os.path.exists(output_path) and not force:
        raise FileExistsError(output_path)

    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.text)

    if json_path:
        data = {
            "text": result.text,
            "pages": result.pages,
        }
        if result.metadata is not None:
            data["metadata"] = result.metadata
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pdftotxt", description="Extract text from PDF files.")
    p.add_argument("input", help="Path to PDF file")
    p.add_argument("--output", "-o", help="Output text file path")
    p.add_argument("--pages", help="Page selection, e.g., '1,3-5'")
    p.add_argument("--mode", choices=["auto", "text-only", "ocr-only"], default="auto")
    p.add_argument("--lang", help="OCR language codes")
    p.add_argument("--layout", choices=["plain", "layout-preserve", "pages-delimited"], default="plain")
    p.add_argument("--normalize", help="Normalization options: dehyphen,collapse_ws,nfkc")
    p.add_argument("--metadata", action="store_true", help="Include metadata in JSON output")
    p.add_argument("--json", help="Optional JSON output path")
    p.add_argument("--force", action="store_true", help="Overwrite existing files")
    p.add_argument("--page-sep", default="\n\n===== [Page {page}] =====\n", help="Page separator template for pages-delimited layout")
    p.add_argument("--password", help="Password for encrypted PDFs")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    opts = ExtractOptions(
        pages=PageSpec.parse(args.pages),
        mode=args.mode,
        layout=args.layout,
        ocr_langs=args.lang,
        normalize=args.normalize.split(",") if args.normalize else None,
        metadata=args.metadata,
        page_separator=args.page_sep,
    )

    result = extract_pdf(args.input, opts, password=args.password)

    output_path = args.output or os.path.splitext(args.input)[0] + ".txt"
    write_output(result, output_path, json_path=args.json, force=args.force)

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
