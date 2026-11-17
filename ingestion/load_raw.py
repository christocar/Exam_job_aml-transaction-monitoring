"""Load raw AML source files into BigQuery using load jobs.

All columns are loaded as STRING to keep an exact copy of the source.
Typing and cleaning happens in the dbt staging layer.
"""

from pathlib import Path

from google.cloud import bigquery

PROJECT_ID = "aml-monitoring-christocar"
DATASET_ID = "aml_raw"
LOCATION = "EU"
DATA_DIR = Path("data/raw")

TRANSACTION_COLUMNS = [
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
]

CSV_TABLES = {
    "transactions": {
        "file": "HI-Small_Trans.csv",
        "columns": TRANSACTION_COLUMNS,
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

PATTERNS_FILE = "HI-Small_Patterns.txt"
PATTERN_COLUMNS = ["attempt_id", "pattern_type", "pattern_detail"] + TRANSACTION_COLUMNS

BEGIN_PREFIX = "BEGIN LAUNDERING ATTEMPT"
END_PREFIX = "END LAUNDERING ATTEMPT"


def string_schema(columns: list[str]) -> list[bigquery.SchemaField]:
    return [bigquery.SchemaField(col, "STRING") for col in columns]


def verify_row_count(client: bigquery.Client, table_ref: str, expected: int) -> None:
    loaded = client.get_table(table_ref).num_rows
    if loaded != expected:
        raise RuntimeError(
            f"Row count mismatch for {table_ref}: expected={expected:,}, bigquery={loaded:,}"
        )
    print(f"OK: {table_ref} loaded with {loaded:,} rows")


def count_data_rows(path: Path) -> int:
    """Count rows in a CSV file, excluding the header."""
    with path.open("rb") as f:
        return sum(1 for _ in f) - 1


def load_csv_table(client: bigquery.Client, table_name: str, spec: dict) -> None:
    path = DATA_DIR / spec["file"]
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=string_schema(spec["columns"]),
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    print(f"Loading {path} -> {table_ref} ...")
    with path.open("rb") as f:
        job = client.load_table_from_file(f, table_ref, job_config=job_config)
    job.result()

    verify_row_count(client, table_ref, count_data_rows(path))


def parse_patterns(path: Path) -> list[dict]:
    """Parse the block-based patterns file into one row per transaction."""
    rows = []
    attempt_id = 0
    pattern_type = None
    pattern_detail = None
    in_block = False

    with path.open(encoding="utf-8") as f:
        for line_no, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith(BEGIN_PREFIX):
                if in_block:
                    raise ValueError(f"Line {line_no}: BEGIN found before previous END")
                attempt_id += 1
                header = line.removeprefix(BEGIN_PREFIX).lstrip(" -")
                type_part, _, detail_part = header.partition(":")
                pattern_type = type_part.strip()
                pattern_detail = detail_part.strip() or None
                in_block = True

            elif line.startswith(END_PREFIX):
                if not in_block:
                    raise ValueError(f"Line {line_no}: END found without BEGIN")
                in_block = False

            else:
                if not in_block:
                    raise ValueError(f"Line {line_no}: transaction found outside a block")
                values = line.split(",")
                if len(values) != len(TRANSACTION_COLUMNS):
                    raise ValueError(
                        f"Line {line_no}: expected {len(TRANSACTION_COLUMNS)} values, got {len(values)}"
                    )
                row = {
                    "attempt_id": str(attempt_id),
                    "pattern_type": pattern_type,
                    "pattern_detail": pattern_detail,
                }
                row.update(zip(TRANSACTION_COLUMNS, values))
                rows.append(row)

    if in_block:
        raise ValueError("File ended inside a block without END")

    print(f"Parsed {attempt_id:,} laundering attempts with {len(rows):,} transactions")
    return rows


def load_patterns(client: bigquery.Client) -> None:
    path = DATA_DIR / PATTERNS_FILE
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.patterns"
    rows = parse_patterns(path)

    job_config = bigquery.LoadJobConfig(
        schema=string_schema(PATTERN_COLUMNS),
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    print(f"Loading {path} -> {table_ref} ...")
    job = client.load_table_from_json(rows, table_ref, job_config=job_config)
    job.result()

    verify_row_count(client, table_ref, len(rows))


def main() -> None:
    client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

    dataset = bigquery.Dataset(f"{PROJECT_ID}.{DATASET_ID}")
    dataset.location = LOCATION
    client.create_dataset(dataset, exists_ok=True)

    for table_name, spec in CSV_TABLES.items():
        load_csv_table(client, table_name, spec)

    load_patterns(client)


if __name__ == "__main__":
    main()