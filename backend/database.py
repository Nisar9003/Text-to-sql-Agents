"""
Database setup module.
Creates a sample SQLite database (if it doesn't exist yet) and
inserts schema + sample data.

Later (Phase 2) this file will be updated so that data extracted
from uploaded PDFs can also be added here.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "company.db")


def get_connection():
    """Returns a new SQLite connection."""
    return sqlite3.connect(DB_PATH)


def init_db():
    """Creates the database and sample tables (if they don't already exist)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT NOT NULL,
            salary REAL NOT NULL,
            hire_date TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY,
            employee_id INTEGER,
            product TEXT NOT NULL,
            amount REAL NOT NULL,
            sale_date TEXT NOT NULL,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        )
    """)

    # Only insert data if the tables are empty (so re-running doesn't duplicate rows)
    cur.execute("SELECT COUNT(*) FROM employees")
    if cur.fetchone()[0] == 0:
        employees = [
            (1, "Ali Raza", "Sales", 85000, "2021-03-15"),
            (2, "Sana Khan", "Sales", 92000, "2020-07-01"),
            (3, "Bilal Ahmed", "Marketing", 78000, "2022-01-10"),
            (4, "Ayesha Malik", "Engineering", 120000, "2019-11-20"),
            (5, "Usman Tariq", "Engineering", 115000, "2021-06-05"),
            (6, "Zara Sheikh", "Marketing", 81000, "2023-02-14"),
        ]
        cur.executemany(
            "INSERT INTO employees (id, name, department, salary, hire_date) VALUES (?, ?, ?, ?, ?)",
            employees,
        )

    cur.execute("SELECT COUNT(*) FROM sales")
    if cur.fetchone()[0] == 0:
        sales = [
            (1, 1, "Laptop", 150000, "2024-01-05"),
            (2, 1, "Monitor", 45000, "2024-02-10"),
            (3, 2, "Laptop", 300000, "2024-01-20"),
            (4, 2, "Keyboard", 12000, "2024-03-01"),
            (5, 3, "Ad Campaign", 200000, "2024-02-15"),
            (6, 3, "Ad Campaign", 175000, "2024-03-10"),
            (7, 4, "Server", 500000, "2024-01-30"),
            (8, 5, "Server", 450000, "2024-02-28"),
            (9, 6, "Social Media Package", 90000, "2024-03-15"),
            (10, 2, "Laptop", 280000, "2024-04-02"),
        ]
        cur.executemany(
            "INSERT INTO sales (id, employee_id, product, amount, sale_date) VALUES (?, ?, ?, ?, ?)",
            sales,
        )

    conn.commit()
    conn.close()


def get_schema_description() -> str:
    """
    Returns the CURRENT database schema as text, read directly from
    SQLite's own metadata (sqlite_master + PRAGMA table_info).

    This is dynamic on purpose: as soon as a new table is created
    (e.g. from an uploaded PDF), it will automatically show up here,
    so the LLM always sees an up-to-date schema without any code change.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    table_names = [row[0] for row in cur.fetchall()]

    lines = []
    for table_name in table_names:
        cur.execute(f"PRAGMA table_info('{table_name}')")
        columns = cur.fetchall()  # (cid, name, type, notnull, dflt_value, pk)
        lines.append(f"Table: {table_name}")
        for col in columns:
            col_name, col_type, is_pk = col[1], col[2], col[5]
            pk_note = ", primary key" if is_pk else ""
            lines.append(f"  - {col_name} ({col_type or 'TEXT'}{pk_note})")
        lines.append("")

    conn.close()
    return "\n".join(lines).strip()


def list_tables() -> list[str]:
    """Returns the list of all user table names currently in the database."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables


def get_table_columns(table_name: str) -> list[str]:
    """Returns the column names of a given table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info('{table_name}')")
    columns = [row[1] for row in cur.fetchall()]
    conn.close()
    return columns


def create_table_from_rows(table_name: str, columns: list[str], rows: list[list]) -> int:
    """
    Creates a brand-new table (all columns as TEXT, simplest/safest option
    for arbitrary PDF data) and inserts the given rows.

    Returns the number of rows inserted.
    """
    conn = get_connection()
    cur = conn.cursor()

    col_defs = ", ".join(f'"{c}" TEXT' for c in columns)
    cur.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs})')

    placeholders = ", ".join("?" for _ in columns)
    col_names = ", ".join(f'"{c}"' for c in columns)
    cur.executemany(
        f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})',
        [[str(cell) if cell is not None else "" for cell in row] for row in rows],
    )

    conn.commit()
    conn.close()
    return len(rows)


def append_to_table(table_name: str, columns: list[str], rows: list[list]) -> int:
    """
    Appends rows to an EXISTING table. The number of incoming columns
    must match the number of existing (non-id) columns in the target table.

    Returns the number of rows inserted.
    """
    existing_columns = [c for c in get_table_columns(table_name) if c.lower() != "id"]
    if len(existing_columns) != len(columns):
        raise ValueError(
            f"Column count mismatch: table '{table_name}' has {len(existing_columns)} columns "
            f"({existing_columns}), but the uploaded data has {len(columns)} columns ({columns})."
        )

    conn = get_connection()
    cur = conn.cursor()
    placeholders = ", ".join("?" for _ in existing_columns)
    col_names = ", ".join(f'"{c}"' for c in existing_columns)
    cur.executemany(
        f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})',
        [[str(cell) if cell is not None else "" for cell in row] for row in rows],
    )
    conn.commit()
    conn.close()
    return len(rows)


def init_documents_table():
    """Creates the 'documents' table used to store text from unstructured PDFs."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def insert_document_chunks(filename: str, chunks: list[str]) -> int:
    """Stores extracted text chunks from an unstructured PDF into the documents table."""
    init_documents_table()
    conn = get_connection()
    cur = conn.cursor()
    cur.executemany(
        "INSERT INTO documents (filename, chunk_index, content) VALUES (?, ?, ?)",
        [(filename, i, chunk) for i, chunk in enumerate(chunks)],
    )
    conn.commit()
    conn.close()
    return len(chunks)


if __name__ == "__main__":
    init_db()
    print(f"Database ready at: {DB_PATH}")
