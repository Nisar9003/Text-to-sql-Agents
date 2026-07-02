"""
FastAPI backend - Phase 1 + Phase 2 + Phase 3 + Phase 4: Text-to-SQL Agent + PDF Upload +
PDF Export + Self-Correction + Query Router (SQL vs Document) + Conversation Memory

Endpoints:
  GET  /health           - health check
  GET  /schema            - view the database schema
  GET  /tables             - list existing table names
  POST /query                - natural language question -> routed to SQL or document search
  POST /upload-pdf             - upload a PDF, extract + preview its content
  POST /confirm-upload           - confirm how to save the previewed data
  POST /export-pdf                - export a query result as a formatted PDF report
"""
import os
import uuid
import tempfile

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from dotenv import load_dotenv

from database import (
    init_db, get_connection, get_schema_description, list_tables,
    create_table_from_rows, append_to_table, insert_document_chunks,
)
from sql_agent import generate_sql, correct_sql, SQLGenerationError
from pdf_processor import extract_pdf_content, classify_pdf, chunk_text, sanitize_identifier
from report_generator import generate_report
from router import classify_question
from document_qa import answer_from_documents, documents_table_has_content

load_dotenv()  # Loads ANTHROPIC_API_KEY from the .env file

# In-memory store for PDFs that have been uploaded + extracted, but not yet
# confirmed/saved to the database. Keyed by a random upload_id.
# NOTE: this is fine for a single-user local app; for a multi-user deployment
# this should move to a proper cache (e.g. Redis) or short-lived DB table.
pending_uploads: dict[str, dict] = {}

app = FastAPI(title="Text-to-SQL Agent", version="1.0")

# Allow CORS so the Streamlit frontend can call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    init_db()


class HistoryItem(BaseModel):
    """One previous turn in the conversation, sent by the frontend for memory/context."""
    question: str
    mode: str = "sql"       # "sql" or "document"
    sql: str = ""
    row_count: int = 0
    answer: str = ""


class QueryRequest(BaseModel):
    question: str
    history: list[HistoryItem] = []


class QueryResponse(BaseModel):
    question: str
    mode: str = "sql"        # "sql" or "document"
    sql: str = ""
    columns: list[str] = []
    rows: list[list] = []
    row_count: int = 0
    answer: str = ""          # natural-language answer (used for document mode)
    sources: list[dict] = []   # document sources used (document mode only)
    attempts: int = 1  # how many tries it took the agent to get a working query


class TablePreview(BaseModel):
    table_index: int
    columns: list[str]
    preview_rows: list[list]
    total_rows: int
    suggested_table_name: str


class UploadResponse(BaseModel):
    upload_id: str
    filename: str
    type: str  # "structured" or "unstructured"
    tables: list[TablePreview] = []
    text_preview: str = ""
    total_text_chunks: int = 0
    existing_tables: list[str] = []


class ConfirmUploadRequest(BaseModel):
    upload_id: str
    table_index: int = 0        # which extracted table (for structured PDFs with multiple tables)
    mode: str = "new_table"      # "new_table" or "append"
    table_name: str = ""          # required if mode == "new_table"
    target_table: str = ""         # required if mode == "append"


class ConfirmUploadResponse(BaseModel):
    table_name: str
    rows_added: int
    mode: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/schema")
def schema():
    return {"schema": get_schema_description()}


MAX_SQL_ATTEMPTS = 3
MAX_HISTORY_TURNS = 5  # how many previous turns to include as conversation context


def build_conversation_context(history: list[HistoryItem]) -> str:
    """Turns recent conversation history into a compact text block for the LLM."""
    if not history:
        return ""
    recent = history[-MAX_HISTORY_TURNS:]
    lines = []
    for h in recent:
        if h.mode == "document":
            lines.append(f"Previous Q: {h.question}\nPrevious A: {h.answer[:300]}")
        else:
            lines.append(f"Previous Q: {h.question}\nPrevious SQL: {h.sql}\nRows returned: {h.row_count}")
    return "\n\n".join(lines)


@app.post("/query", response_model=QueryResponse)
def run_query(request: QueryRequest):
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    schema_context = get_schema_description()
    conversation_context = build_conversation_context(request.history)

    conn = get_connection()
    has_docs = documents_table_has_content(conn)
    conn.close()

    mode = classify_question(question, schema_context, has_documents=has_docs, conversation_context=conversation_context)

    # --- DOCUMENT PATH: answer using text extracted from uploaded PDFs ---
    if mode == "document":
        conn = get_connection()
        answer, sources = answer_from_documents(question, conn, conversation_context=conversation_context)
        conn.close()
        return QueryResponse(
            question=question,
            mode="document",
            answer=answer,
            sources=sources,
            attempts=1,
        )

    # --- SQL PATH: generate + self-correct + execute ---
    sql = None
    last_error = None

    for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
        try:
            if attempt == 1:
                sql = generate_sql(question, schema_context, conversation_context=conversation_context)
            else:
                sql = correct_sql(
                    question, schema_context, previous_sql=sql, error_message=last_error,
                    conversation_context=conversation_context,
                )
        except SQLGenerationError as e:
            last_error = str(e)
            if attempt == MAX_SQL_ATTEMPTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not generate a valid query after {attempt} attempts. Last error: {last_error}",
                )
            continue

        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql)
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [list(row) for row in cur.fetchall()]
            conn.close()

            return QueryResponse(
                question=question,
                mode="sql",
                sql=sql,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                attempts=attempt,
            )
        except Exception as e:
            last_error = str(e)
            if attempt == MAX_SQL_ATTEMPTS:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"SQL execution failed after {attempt} attempts. "
                        f"Last error: {last_error} | Last SQL tried: {sql}"
                    ),
                )


@app.get("/tables")
def tables():
    return {"tables": list_tables()}


@app.post("/upload-pdf", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    # Save the uploaded file to a temp path so pdfplumber can open it
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        extracted = extract_pdf_content(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read the PDF: {str(e)}")
    finally:
        os.remove(tmp_path)

    pdf_type = classify_pdf(extracted)
    upload_id = str(uuid.uuid4())
    base_name = sanitize_identifier(os.path.splitext(file.filename)[0])

    if pdf_type == "structured":
        pending_uploads[upload_id] = {"type": "structured", "tables": extracted["tables"], "filename": file.filename}
        table_previews = []
        for i, t in enumerate(extracted["tables"]):
            suggested_name = base_name if i == 0 else f"{base_name}_{i}"
            table_previews.append(TablePreview(
                table_index=i,
                columns=t["columns"],
                preview_rows=t["rows"][:5],
                total_rows=len(t["rows"]),
                suggested_table_name=suggested_name,
            ))
        return UploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            type="structured",
            tables=table_previews,
            existing_tables=list_tables(),
        )
    else:
        chunks = chunk_text(extracted["text"])
        pending_uploads[upload_id] = {"type": "unstructured", "chunks": chunks, "filename": file.filename}
        return UploadResponse(
            upload_id=upload_id,
            filename=file.filename,
            type="unstructured",
            text_preview=extracted["text"][:800],
            total_text_chunks=len(chunks),
        )


@app.post("/confirm-upload", response_model=ConfirmUploadResponse)
def confirm_upload(request: ConfirmUploadRequest):
    pending = pending_uploads.get(request.upload_id)
    if not pending:
        raise HTTPException(status_code=404, detail="Upload not found or already confirmed. Please upload the file again.")

    if pending["type"] == "unstructured":
        rows_added = insert_document_chunks(pending["filename"], pending["chunks"])
        del pending_uploads[request.upload_id]
        return ConfirmUploadResponse(table_name="documents", rows_added=rows_added, mode="append")

    # structured PDF
    table_data = pending["tables"][request.table_index]
    columns, rows = table_data["columns"], table_data["rows"]

    if request.mode == "new_table":
        table_name = sanitize_identifier(request.table_name or "uploaded_table")
        if table_name in list_tables():
            raise HTTPException(status_code=400, detail=f"A table named '{table_name}' already exists. Choose a different name or use 'append' instead.")
        rows_added = create_table_from_rows(table_name, columns, rows)
    elif request.mode == "append":
        if not request.target_table:
            raise HTTPException(status_code=400, detail="target_table is required when mode is 'append'.")
        try:
            rows_added = append_to_table(request.target_table, columns, rows)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        table_name = request.target_table
    else:
        raise HTTPException(status_code=400, detail="mode must be 'new_table' or 'append'.")

    del pending_uploads[request.upload_id]
    return ConfirmUploadResponse(table_name=table_name, rows_added=rows_added, mode=request.mode)


@app.post("/export-pdf")
def export_pdf(request: QueryResponse):
    """
    Takes a previously fetched query result (same shape as /query's response)
    and returns it as a downloadable, formatted PDF report.
    """
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(tmp_fd)

    try:
        generate_report(
            output_path=tmp_path,
            question=request.question,
            sql=request.sql,
            columns=request.columns,
            rows=request.rows,
            mode=request.mode,
            answer=request.answer,
            sources=request.sources,
        )
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=500, detail=f"Could not generate PDF: {str(e)}")

    return FileResponse(
        tmp_path,
        media_type="application/pdf",
        filename="query_report.pdf",
        background=BackgroundTask(lambda: os.remove(tmp_path)),
    )