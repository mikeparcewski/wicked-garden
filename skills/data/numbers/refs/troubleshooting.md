# Troubleshooting and Performance

Performance tips, troubleshooting guides, and dependency information.

## Performance

### Large Files

- Files up to 10GB+ supported
- Never loads full file into memory
- DuckDB streams results efficiently

### Timeouts

- Default query timeout: 60 seconds
- Add LIMIT for faster results
- Use WHERE to filter early

### Tips

1. **Add LIMIT** for exploratory queries
2. **Filter early** in WHERE clause
3. **Use aggregations** instead of fetching all rows
4. **Cache results** for repeated analysis

## Troubleshooting

### File Not Found

Check the path is correct and file exists.

### Encoding Error

The plugin tries multiple encodings. If issues persist:
- Check file encoding: `file -I <path>`
- Convert to UTF-8: `iconv -f ORIGINAL -t UTF-8 file.csv > new.csv`

### Query Timeout

Queries timeout after 60 seconds. Solutions:
- Add `LIMIT N` to your query
- Add `WHERE` clause to filter data
- Reduce columns selected

### Memory Issues

For very large files:
- Use aggregations instead of SELECT *
- Add LIMIT clause
- Filter with WHERE

### Excel Issues

If Excel files fail to load:
- Ensure the file isn't password protected
- Check for corrupted workbooks
- Try saving as CSV from Excel first

### CSV Delimiter Issues

If columns aren't detected properly:
- Check the delimiter (comma, tab, semicolon)
- Verify there are no embedded delimiters in values
- Check for proper quoting of text fields

## Dependencies

Requires Python packages:
- `duckdb>=1.0.0` - SQL query engine
- `openpyxl>=3.1.0` - Excel file support
- `chardet>=5.0.0` - Encoding detection

Install all:
```bash
pip install duckdb openpyxl chardet
```

## Supported File Types

| Type | Extensions | Status |
|------|------------|--------|
| CSV | `.csv`, `.tsv` | Full support |
| Excel | `.xlsx`, `.xls` | Full support |
| JSON | `.json`, `.jsonl` | Coming soon |
| XML | `.xml` | Coming soon |
| Parquet | `.parquet` | Coming soon |
