# OCR Pipeline

When research sources are scanned PDFs, images, or chart-heavy documents, the pipeline uses OCR to extract text before creating source notes and feeding extraction.

## When OCR Is Needed

| Source Type | Extraction Method | When |
|-------------|------------------|------|
| Text-rich PDF (<50 pages) | `pdftotext` | Default — fastest, no OCR needed |
| Scanned/image PDF | OCR pipeline | When `pdftotext` returns garbage or <50 chars |
| Chart-heavy PDF | OCR + vision analysis | When charts contain critical data not in text |
| Web page with embedded images | `web_extract` | Default — handles most cases |
| Screenshots / image attachments | OCR pipeline | When user provides image-based sources |

## OCR Pipeline Stages

```
1. Identify source needs OCR
   (pdftotext returns <50 chars, or file is image format)
        ↓
2. Rasterize (if PDF)
   pdftoppm or pymupdf → PNG pages at 300 DPI
        ↓
3. OCR extract
   Option A: Tesseract (open-source, local, fast)
   Option B: Hermes vision model (higher quality, needs API)
   Option C: PageIndex pipeline (for batch PDF processing)
        ↓
4. Post-process
   Clean OCR artifacts, structure into markdown
        ↓
5. Create source note
   frontmatter: extraction_method: ocr, ocr_confidence: <value>
        ↓
6. Stage for PageIndex (if high-value PDF)
   Move to ~/Research/__Inbound/ for full enrichment
```

## Quick OCR Commands

### Tesseract (local, no API needed)

```bash
# Rasterize PDF to images
pdftoppm -png -r 300 input.pdf page

# OCR each page
for img in page-*.png; do
    tesseract "$img" "${img%.png}" --psm 6 2>/dev/null
done

# Combine
cat page-*.txt > extracted_text.txt
```

### pymupdf (Python, handles both text and scanned PDFs)

```python
import fitz  # pymupdf

doc = fitz.open("input.pdf")
text = ""
for page in doc:
    page_text = page.get_text()
    if len(page_text.strip()) < 50:
        # Likely scanned — flag for OCR
        page_text = f"[PAGE {page.number+1}: OCR NEEDED]"
    text += page_text + "\n"
```

### Vision Model OCR (highest quality)

When Tesseract quality is insufficient for charts, tables, or complex layouts, use a vision-capable model:

```python
# Via Hermes delegate_task or direct API call
# Convert page to image, send to vision model with extraction prompt
prompt = "Extract all text, data, and key information from this document page. Preserve table structures."
```

## Source Note Frontmatter for OCR

```yaml
---
recon_id: <parent>-<topic>-<date>
type: report|filing|article
source_url: <original URL>
date: YYYY-MM-DD
tags: [recon, <domain-tags>]
ingestion_status: captured|ocr_extracted|pdf_staged
extraction_method: pdftotext|ocr|vision|web_extract
ocr_confidence: high|medium|low  # only if extraction_method is ocr or vision
pdf_path: <local staged path>    # only if PDF is staged
download_note: <optional, e.g., "manual download, bot-gated">
---
```

## Integration with PageIndex

For high-value PDFs (industry reports, filings, McKinsey/Gartner):

1. **Stage in `~/Research/__Inbound/`** — not in the Spider's `Sources/` folder
2. **Run `process_inbound.py`** to ingest into PageIndex pipeline
3. **PageIndex enrichment** handles OCR, entity extraction, and metric extraction at scale
4. **Registry update** — add to `pageindex_registry.json` for tracking
5. **Move to `Domains/<topic>/`** after processing for proper categorization

### When to use PageIndex vs. quick OCR

| Scenario | Method |
|----------|--------|
| <11 page text-rich PDF | `pdftotext` directly — fastest |
| Scanned PDF, need it now | Tesseract OCR — local, fast |
| 50+ page report with charts | PageIndex pipeline — handles at scale |
| Image-heavy PDF with critical data tables | Vision model OCR — highest quality |
| Batch of 10+ PDFs | PageIndex pipeline — batch processing |

## Pitfalls

- **`pdftotext` returns garbage on scanned PDFs** — always check output length. If <50 chars, the PDF is image-based and needs OCR.
- **Tesseract struggles with tables and charts** — use vision model OCR for complex layouts.
- **OCR confidence matters** — mark low-confidence extractions in the source note. The clerk/analyst stages should treat low-confidence OCR text with skepticism.
- **Don't store raw PDFs in `Sources/`** — Source notes are markdown only. Stage PDFs in the research corpus.
- **PageIndex is async** — don't block the pipeline waiting for PageIndex enrichment. Stage the PDF, note it in the source note, and continue. The enrichment catches up later.
