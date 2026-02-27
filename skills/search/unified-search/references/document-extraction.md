# Document Extraction

How documents are extracted and stored for searching.

## Extraction Process

1. **Kreuzberg** extracts text from binary formats (PDF, Office docs)
2. Text is parsed into **sections** based on headings
3. Full text cached as `.txt` file
4. Sections added to graph as `doc_section` nodes

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| PDF | .pdf | Text extraction, no OCR by default |
| Word | .docx, .doc | Full text + headings |
| Excel | .xlsx, .xls | Cell contents as text |
| PowerPoint | .pptx, .ppt | Slide text |
| Markdown | .md | Native support |
| HTML | .html, .htm | Text extracted |
| Plain text | .txt | Direct indexing |
| Rich Text | .rtf | Text extracted |
| OpenDocument | .odt, .odp, .ods | Full support |
| EPUB | .epub | eBook text |

## Section Detection

Headings are detected via:

1. **Markdown headings**: `# Heading`, `## Subheading`
2. **ALL CAPS lines**: `REQUIREMENTS OVERVIEW`
3. **Document styles**: Word heading styles

Each detected heading becomes a `doc_section` node.

## Cached Files

Extracted text is stored at:
```
~/.something-wicked/search/extracted/
├── requirements_docx.txt
├── api-spec_pdf.txt
├── design_pptx.txt
└── ...
```

## Reading Full Document Content

To get full context from a document:

```python
# Path to extracted text
extracted_path = "~/.something-wicked/search/extracted/requirements_docx.txt"

# Read it
cat ~/.something-wicked/search/extracted/requirements_docx.txt
```

## Indexing Tips

1. **Re-index on changes**: Run `/wicked-garden:search:index --force` after doc updates
2. **Check extraction**: Read cached `.txt` to verify extraction quality
3. **Large docs**: May take a few seconds to extract
4. **Binary formats**: Require Kreuzberg installed
