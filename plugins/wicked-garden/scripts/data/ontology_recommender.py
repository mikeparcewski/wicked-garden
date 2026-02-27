#!/usr/bin/env python3
"""Ontology recommender — sample dataset and suggest matching ontologies."""
import json
import re
import sys
from pathlib import Path

# Known ontology catalogs with column name patterns
ONTOLOGIES = {
    "schema.org/Person": {
        "patterns": {
            "name": ["name", "full_name", "fullname", "display_name"],
            "email": ["email", "e_mail", "email_address", "mail"],
            "telephone": ["phone", "telephone", "mobile", "cell", "phone_number"],
            "address": ["address", "street", "city", "state", "zip", "postal", "country"],
            "birthDate": ["birth_date", "dob", "date_of_birth", "birthday"],
            "gender": ["gender", "sex"],
            "jobTitle": ["job_title", "title", "position", "role"],
        },
    },
    "schema.org/Organization": {
        "patterns": {
            "name": ["company", "organization", "org_name", "company_name"],
            "url": ["website", "url", "homepage", "web"],
            "industry": ["industry", "sector", "vertical"],
            "foundingDate": ["founded", "founding_date", "established"],
            "numberOfEmployees": ["employees", "headcount", "team_size"],
        },
    },
    "schema.org/Product": {
        "patterns": {
            "name": ["product", "product_name", "item", "item_name"],
            "price": ["price", "cost", "amount", "unit_price"],
            "sku": ["sku", "product_id", "item_id", "upc", "barcode"],
            "category": ["category", "type", "product_type", "classification"],
            "brand": ["brand", "manufacturer", "vendor"],
            "description": ["description", "desc", "details", "summary"],
        },
    },
    "schema.org/Event": {
        "patterns": {
            "name": ["event", "event_name", "title"],
            "startDate": ["start_date", "start", "begin", "event_date"],
            "endDate": ["end_date", "end", "finish"],
            "location": ["location", "venue", "place"],
            "organizer": ["organizer", "host", "creator"],
        },
    },
    "Dublin Core": {
        "patterns": {
            "title": ["title", "name", "heading", "subject_line"],
            "creator": ["creator", "author", "writer", "created_by"],
            "subject": ["subject", "topic", "category", "tags"],
            "description": ["description", "abstract", "summary", "body"],
            "date": ["date", "created_at", "published", "modified"],
            "format": ["format", "mime_type", "content_type", "file_type"],
            "identifier": ["id", "identifier", "uri", "doi", "isbn"],
            "language": ["language", "lang", "locale"],
            "source": ["source", "origin", "reference"],
        },
    },
    "DCAT": {
        "patterns": {
            "distribution": ["url", "download_url", "access_url", "file_path"],
            "byteSize": ["size", "file_size", "byte_size", "bytes"],
            "mediaType": ["media_type", "mime_type", "content_type"],
            "issued": ["issued", "published", "release_date"],
            "modified": ["modified", "updated", "last_updated"],
            "keyword": ["keyword", "tag", "tags", "label"],
        },
    },
    "FOAF": {
        "patterns": {
            "name": ["name", "display_name", "username"],
            "mbox": ["email", "mail"],
            "knows": ["friend", "connection", "contact", "follows"],
            "interest": ["interest", "hobby", "preference"],
            "account": ["account", "profile", "handle", "screen_name"],
            "img": ["avatar", "photo", "image", "picture", "profile_pic"],
        },
    },
    "GoodRelations": {
        "patterns": {
            "hasCurrencyValue": ["price", "amount", "cost", "value"],
            "hasCurrency": ["currency", "currency_code"],
            "eligibleRegion": ["region", "country", "market"],
            "validFrom": ["valid_from", "start_date", "effective"],
            "validThrough": ["valid_to", "end_date", "expiry", "expires"],
            "condition": ["condition", "status", "state"],
        },
    },
    "SKOS": {
        "patterns": {
            "prefLabel": ["label", "name", "title", "display"],
            "broader": ["parent", "parent_id", "broader", "category"],
            "narrower": ["child", "children", "subcategory", "narrower"],
            "notation": ["code", "notation", "identifier", "abbreviation"],
            "definition": ["definition", "description", "meaning"],
        },
    },
}


def normalize_column(col: str) -> str:
    """Normalize column name for matching."""
    return re.sub(r'[^a-z0-9]', '_', col.lower()).strip('_')


def match_ontologies(columns: list[str]) -> list[dict]:
    """Match columns against known ontology patterns."""
    normalized = [normalize_column(c) for c in columns]
    results = []

    for ontology_name, config in ONTOLOGIES.items():
        matched_cols = []
        mappings = []

        for prop_name, patterns in config["patterns"].items():
            for i, norm_col in enumerate(normalized):
                if norm_col in patterns or any(p in norm_col for p in patterns):
                    matched_cols.append(columns[i])
                    mappings.append({
                        "column": columns[i],
                        "property": f"{ontology_name.split('/')[0].lower()}:{prop_name}",
                        "confidence": "high" if norm_col in patterns else "medium",
                    })
                    break

        if matched_cols and config["patterns"]:
            score = len(matched_cols) / len(config["patterns"])
            results.append({
                "ontology": ontology_name,
                "score": round(score * 100),
                "matched_columns": matched_cols,
                "total_properties": len(config["patterns"]),
                "mappings": mappings,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def profile_dataset(file_path: str) -> dict:
    """Profile a dataset using DuckDB or fallback to csv module."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    try:
        import duckdb
        con = duckdb.connect()

        if suffix == ".csv":
            query = f"SELECT * FROM read_csv_auto('{file_path}') LIMIT 100"
        elif suffix in (".xlsx", ".xls"):
            query = f"SELECT * FROM read_excel('{file_path}') LIMIT 100"
        elif suffix == ".parquet":
            query = f"SELECT * FROM read_parquet('{file_path}') LIMIT 100"
        elif suffix == ".json":
            query = f"SELECT * FROM read_json_auto('{file_path}') LIMIT 100"
        else:
            return {"error": f"Unsupported format: {suffix}"}

        result = con.execute(query)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        types = [desc[1] for desc in result.description]

        return {
            "columns": columns,
            "types": [str(t) for t in types],
            "row_count": len(rows),
            "sample_values": {
                col: [str(rows[i][j]) for i in range(min(5, len(rows))) if rows[i][j] is not None]
                for j, col in enumerate(columns)
            },
        }
    except ImportError:
        # Fallback to csv module
        import csv
        if suffix != ".csv":
            return {"error": "DuckDB not available, only CSV supported in fallback mode"}

        with open(file_path) as f:
            reader = csv.DictReader(f)
            columns = reader.fieldnames or []
            rows = []
            for i, row in enumerate(reader):
                if i >= 100:
                    break
                rows.append(row)

        return {
            "columns": list(columns),
            "types": ["string"] * len(columns),
            "row_count": len(rows),
            "sample_values": {
                col: [rows[i][col] for i in range(min(5, len(rows))) if rows[i].get(col)]
                for col in columns
            },
        }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: ontology_recommender.py <file-path>"}))
        sys.exit(1)

    file_path = sys.argv[1]

    if not Path(file_path).exists():
        print(json.dumps({"error": f"File not found: {file_path}"}))
        sys.exit(1)

    profile = profile_dataset(file_path)
    if "error" in profile:
        print(json.dumps(profile))
        sys.exit(1)

    recommendations = match_ontologies(profile["columns"])

    output = {
        "file": file_path,
        "profile": profile,
        "recommendations": recommendations,
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
