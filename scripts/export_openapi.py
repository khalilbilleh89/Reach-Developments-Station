"""
Export OpenAPI schema to a JSON file.

Usage: python scripts/export_openapi.py
"""
import json
from app.main import app

schema = app.openapi()
with open("openapi.json", "w") as f:
    json.dump(schema, f, indent=2)

print("OpenAPI schema exported to openapi.json")
