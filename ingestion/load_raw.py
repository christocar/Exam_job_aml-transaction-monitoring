"""Load raw AML CSV files into BigQuery using load jobs.

All columns are loaded as STRING to keep an exact copy of the source.
Typing and cleaning happens in the dbt staging layer.
"""

from pathlib import Path

from google.cloud import bigquery

PROJECT_ID = "aml-monitoring-christocar"
DATASET_ID = "aml_raw"
LOCATION = "EU"
DATA_DIR = Path("data/raw")

TABLES = {
    "transactions": {
        "file": "HI-Small_Trans.csv",
        "columns": [
            "timestamp",
            "from_bank",
            "from_account",
            "to_bank",
            "to_account",
            "amount_received",
            "receiving_currency",
            "amount_paid",
            "payment_currency",
            "payment_format",
            "is_laundering",
        ],
    },
    "accounts": {
        "file": "HI-Small_accounts.csv",
        "columns": [
            "bank_name",
            "bank_id",
            "account_number",
            "entity_id",
            "entity_name",
        ],
    },
}


def count_data_rows(path: Path) -> int:
    """Count rows in the file, excluding the header."""
    with path.open("rb") as f:
        return sum(1 for _ in f) - 1


def load_table(client: bigquery.Client, table_name: str, spec: dict) -> None:
    path = DATA_DIR / spec["file"]
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=[bigquery.SchemaField(col, "STRING") for col in spec["columns"]],
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    print(f"Loading {path} -> {table_ref} ...")
    with path.open("rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)
    job.result()

    expected = count_data_rows(path)
    loaded = client.get_table(table_ref).num_rows
    if loaded != expected:
        raise RuntimeError(
            f"Row count mismatch for {table_name}: file={expected:,}, bigquery={loaded:,}"
        )
    print(f"OK: {table_name} loaded with {loaded:,} rows")


def main() -> None:
    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

    dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset.location = LOCATION
    client.create_dataset(dataset, exists_ok=True)

    for table_name, spec in TABLES.items():
        load_table(client, table_name, spec)


if __name__ == "__main__":
    main()