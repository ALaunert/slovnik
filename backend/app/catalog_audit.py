import json

from app.db import SessionLocal, load_model_registry
from app.services.catalog_mapping_service import audit_catalog_mappings


def main() -> None:
    load_model_registry()
    with SessionLocal() as session:
        audit = audit_catalog_mappings(session)
    print(
        json.dumps(
            {
                "missing": audit.missing,
                "stale": audit.stale,
                "ambiguous": audit.ambiguous,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
