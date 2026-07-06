"""
Streamlit Frontend - Phase 1-4: Text-to-SQL Agent + PDF Upload + PDF Export +
Self-Correction + Query Router + Conversation Memory

How to run:
    streamlit run app.py

The backend (FastAPI) must be running separately at: http://localhost:8000
"""
import streamlit as st
import requests
import pandas as pd

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="SQL Agent Console", page_icon="M", layout="wide")

# =========================================================
# THEME - deep navy console palette with three meaningful
# accent colors: amber (primary / self-correction), blue (SQL),
# violet (documents), coral (off-topic). Space Grotesk for
# display type, Inter for body, IBM Plex Mono for SQL/schema.
# =========================================================
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap');

:root {
    --bg: #0B1220;
    --surface: #131B2E;
    --surface-alt: #1A2338;
    --border: #263252;
    --text: #E8EAF0;
    --text-muted: #8B94A8;
    --amber: #F5A623;
    --blue: #38BDF8;
    --violet: #A78BFA;
    --coral: #F87171;
    --success: #34D399;
}

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

.stApp { background: radial-gradient(circle at 20% 0%, #101A30 0%, var(--bg) 55%); }

/* Constrain and center the main content for a more polished, less "stretched" look */
.block-container {
    max-width: 1100px;
    padding-top: 2.2rem;
}

/* ---- Header brand bar ---- */
.brand-bar {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 20px 0 20px 0;
    border-bottom: 1px solid var(--border);
    margin-bottom: 24px;
}
.brand-mark {
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 700;
    font-size: 1.09rem;
    letter-spacing: 0.02em;
    color: var(--bg);
    background: var(--amber);
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.brand-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 1.65rem;
    color: var(--text);
    line-height: 1.1;
    margin: 0;
}
.brand-tagline {
    color: var(--text-muted);
    font-size: 0.92rem;
    margin-top: 2px;
}

/* ---- Headings ---- */
h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: var(--text) !important; }

/* ---- Expander (used for schema + examples, replacing the sidebar) ---- */
div[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 10px;
}
div[data-testid="stExpander"] summary {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: var(--text);
}
div[data-testid="stExpander"] code {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.82rem !important;
}

/* ---- Tabs styled as a segmented control ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--surface);
    padding: 5px;
    border-radius: 10px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    height: 40px;
    border-radius: 7px;
    color: var(--text-muted);
    font-weight: 500;
    background: transparent;
}
.stTabs [aria-selected="true"] {
    background: var(--surface-alt) !important;
    color: var(--text) !important;
}
.stTabs [data-baseweb="tab-highlight"] { background: transparent !important; }
.stTabs [data-baseweb="tab-border"] { display: none !important; }

/* ---- Buttons ---- */
.stButton > button {
    border-radius: 8px !important;
    font-weight: 500 !important;
    border: 1px solid var(--border) !important;
}
.stButton > button[kind="primary"] {
    background: var(--amber) !important;
    color: #1A1200 !important;
    border: none !important;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.08); }
.stButton > button[kind="secondary"] {
    background: var(--surface-alt) !important;
    color: var(--text) !important;
}
.stDownloadButton > button {
    border-radius: 8px !important;
    background: var(--surface-alt) !important;
    color: var(--text) !important;
    border: 1px solid var(--border) !important;
}

/* ---- Suggestion chips (example questions) ---- */
.stButton > button[kind="secondary"].suggestion-chip { font-size: 0.82rem !important; }

/* ---- Text input ---- */
.stTextInput input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    color: var(--text) !important;
    border-radius: 8px !important;
}
.stTextInput input:focus { border-color: var(--amber) !important; box-shadow: none !important; }

/* ---- Bordered result cards ---- */
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: var(--surface);
    border: 1px solid var(--border) !important;
    border-radius: 12px;
}

/* ---- Mode badges ---- */
.badge {
    display: inline-block;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    padding: 3px 9px;
    border-radius: 5px;
    margin-bottom: 6px;
}
.badge-sql { background: rgba(56, 189, 248, 0.14); color: var(--blue); }
.badge-document { background: rgba(167, 139, 250, 0.14); color: var(--violet); }
.badge-unrelated { background: rgba(248, 113, 113, 0.14); color: var(--coral); }
.badge-retry { background: rgba(245, 166, 35, 0.14); color: var(--amber); margin-left: 6px; }

/* ---- Terminal-style title bar above SQL code blocks ---- */
.term-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    background: var(--surface-alt);
    border: 1px solid var(--border);
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 7px 10px;
}
.term-dot { width: 9px; height: 9px; border-radius: 50%; }
.term-dot.r { background: #F87171; }
.term-dot.y { background: #F5A623; }
.term-dot.g { background: #34D399; }
.term-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-left: 6px;
}
div[data-testid="stCode"] {
    border-radius: 0 0 8px 8px !important;
    margin-top: -1px !important;
}

/* ---- Dataframe ---- */
div[data-testid="stDataFrame"] { border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }

/* ---- Question label on result cards ---- */
.q-label {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    font-size: 1.02rem;
    color: var(--text);
    margin-bottom: 2px;
}

/* ---- Section label ---- */
.section-label {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    color: var(--text-muted);
    margin-bottom: 4px;
}
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

st.markdown("""
<div class="brand-bar">
    <div class="brand-mark">MNA</div>
    <div>
        <p class="brand-title">SQL Agent Console</p>
        <p class="brand-tagline">Ask questions about your data or documents. The agent routes each one and remembers your last few turns.</p>
    </div>
</div>
""", unsafe_allow_html=True)

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_upload" not in st.session_state:
    st.session_state.pending_upload = None
if "question_box" not in st.session_state:
    st.session_state.question_box = ""


def get_schema_text():
    try:
        resp = requests.get(f"{BACKEND_URL}/schema", timeout=5)
        return resp.json()["schema"] if resp.ok else None
    except requests.exceptions.ConnectionError:
        return None


def get_tables_list():
    try:
        resp = requests.get(f"{BACKEND_URL}/tables", timeout=5)
        return resp.json()["tables"] if resp.ok else []
    except requests.exceptions.ConnectionError:
        return []


def mode_badge_html(mode: str) -> str:
    labels = {
        "sql": ("SQL QUERY", "badge-sql"),
        "document": ("DOCUMENT", "badge-document"),
        "unrelated": ("OFF-TOPIC", "badge-unrelated"),
    }
    label, css_class = labels.get(mode, ("SQL QUERY", "badge-sql"))
    return f'<span class="badge {css_class}">{label}</span>'


EXAMPLE_QUESTIONS = [
    "How many employees are in the Sales department?",
    "What is the total sales amount per product?",
    "Who has the highest salary?",
]


def use_example(text: str):
    st.session_state.question_box = text


tab_query, tab_upload = st.tabs(["Ask a Question", "Upload PDF"])

# =========================================================
# TAB 1: Ask a Question
# =========================================================
with tab_query:
    with st.expander("Database schema"):
        schema_text = get_schema_text()
        if schema_text is not None:
            st.code(schema_text, language="text")
        else:
            st.error("Could not connect to the backend server. Start it first: uvicorn main:app --reload")

    st.markdown('<p class="section-label">TRY AN EXAMPLE</p>', unsafe_allow_html=True)
    chip_cols = st.columns(len(EXAMPLE_QUESTIONS))
    for col, example in zip(chip_cols, EXAMPLE_QUESTIONS):
        with col:
            st.button(example, key=f"chip_{example}", use_container_width=True, on_click=use_example, args=(example,))

    question = st.text_input(
        "Type your question here:",
        key="question_box",
        placeholder="e.g. Who has the highest salary in the Engineering department?",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        run_clicked = st.button("Run Query", type="primary", use_container_width=True)

    if run_clicked and question.strip():
        with st.spinner("The agent is thinking..."):
            try:
                # Send recent history so the agent can resolve follow-up references
                history_payload = st.session_state.history[:5]
                resp = requests.post(
                    f"{BACKEND_URL}/query",
                    json={"question": question, "history": history_payload},
                    timeout=30,
                )
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend. Please start the backend server first.")
                resp = None

        if resp is not None:
            if resp.ok:
                st.session_state.history.insert(0, resp.json())
            else:
                st.error(f"Error: {resp.json().get('detail', 'Unknown error')}")
    elif run_clicked:
        st.warning("Please type a question first.")

    for item in st.session_state.history:
        with st.container(border=True):
            badge_html = mode_badge_html(item.get("mode", "sql"))
            if item.get("attempts", 1) > 1:
                badge_html += f'<span class="badge badge-retry">SELF-CORRECTED - {item["attempts"]} TRIES</span>'
            st.markdown(badge_html, unsafe_allow_html=True)
            st.markdown(f'<p class="q-label">{item["question"]}</p>', unsafe_allow_html=True)

            if item.get("mode") == "unrelated":
                st.warning(item.get("answer", "This question doesn't seem related to the available data."))
            elif item.get("mode") == "document":
                st.write(item.get("answer", ""))
                sources = item.get("sources", [])
                if sources:
                    unique_files = sorted({s["filename"] for s in sources})
                    st.caption("Sources: " + ", ".join(unique_files))
            else:
                st.markdown(
                    '<div class="term-bar"><span class="term-dot r"></span>'
                    '<span class="term-dot y"></span><span class="term-dot g"></span>'
                    '<span class="term-label">generated_query.sql</span></div>',
                    unsafe_allow_html=True,
                )
                st.code(item["sql"], language="sql")
                if item["row_count"] > 0:
                    df = pd.DataFrame(item["rows"], columns=item["columns"])
                    st.markdown(f"**Result** &middot; {item['row_count']} rows")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("The query ran successfully, but returned no results.")

            pdf_key = f"pdf_{hash(item['question'] + item.get('sql', '') + item.get('answer', ''))}"
            if st.button("Export as PDF", key=f"btn_{pdf_key}"):
                with st.spinner("Generating PDF report..."):
                    try:
                        pdf_resp = requests.post(f"{BACKEND_URL}/export-pdf", json=item, timeout=30)
                    except requests.exceptions.ConnectionError:
                        pdf_resp = None
                        st.error("Could not connect to the backend.")

                if pdf_resp is not None:
                    if pdf_resp.ok:
                        st.session_state[pdf_key] = pdf_resp.content
                    else:
                        st.error(f"{pdf_resp.json().get('detail', 'Could not generate PDF')}")

            if pdf_key in st.session_state:
                st.download_button(
                    "Download PDF report",
                    data=st.session_state[pdf_key],
                    file_name="query_report.pdf",
                    mime="application/pdf",
                    key=f"dl_{pdf_key}",
                )

# =========================================================
# TAB 2: Upload PDF
# =========================================================
with tab_upload:
    st.markdown("Upload a PDF containing a data table (e.g. an invoice or sales sheet) "
                 "or a narrative document (e.g. a report). The agent detects which kind it is.")

    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    if uploaded_file is not None and st.button("Analyze PDF", type="primary"):
        with st.spinner("Extracting content from the PDF..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                resp = requests.post(f"{BACKEND_URL}/upload-pdf", files=files, timeout=60)
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to the backend. Please start the backend server first.")
                resp = None

        if resp is not None:
            if resp.ok:
                st.session_state.pending_upload = resp.json()
            else:
                st.error(f"Error: {resp.json().get('detail', 'Unknown error')}")
                st.session_state.pending_upload = None

    pending = st.session_state.pending_upload
    if pending is not None:
        st.divider()
        st.markdown(f"#### {pending['filename']}")

        if pending["type"] == "structured":
            st.success(f"Detected {len(pending['tables'])} table(s) in this PDF.")

            for t in pending["tables"]:
                st.markdown(f"**Table {t['table_index'] + 1}** &middot; {t['total_rows']} rows &middot; columns: `{', '.join(t['columns'])}`")
                preview_df = pd.DataFrame(t["preview_rows"], columns=t["columns"])
                st.dataframe(preview_df, use_container_width=True)

                mode = st.radio(
                    "What should we do with this table?",
                    ["Create a new table", "Append to an existing table"],
                    key=f"mode_{t['table_index']}",
                    horizontal=True,
                )

                if mode == "Create a new table":
                    new_name = st.text_input(
                        "New table name:",
                        value=t["suggested_table_name"],
                        key=f"newname_{t['table_index']}",
                    )
                    if st.button("Save as new table", type="primary", key=f"savenew_{t['table_index']}"):
                        r = requests.post(f"{BACKEND_URL}/confirm-upload", json={
                            "upload_id": pending["upload_id"],
                            "table_index": t["table_index"],
                            "mode": "new_table",
                            "table_name": new_name,
                        })
                        if r.ok:
                            data = r.json()
                            st.success(f"Saved {data['rows_added']} rows into new table '{data['table_name']}'.")
                            st.session_state.pending_upload = None
                            st.rerun()
                        else:
                            st.error(f"{r.json().get('detail', 'Unknown error')}")
                else:
                    existing = pending.get("existing_tables", [])
                    if existing:
                        target = st.selectbox("Choose the table to append to:", existing, key=f"target_{t['table_index']}")
                        if st.button("Append to this table", type="primary", key=f"saveappend_{t['table_index']}"):
                            r = requests.post(f"{BACKEND_URL}/confirm-upload", json={
                                "upload_id": pending["upload_id"],
                                "table_index": t["table_index"],
                                "mode": "append",
                                "target_table": target,
                            })
                            if r.ok:
                                data = r.json()
                                st.success(f"Appended {data['rows_added']} rows into '{data['table_name']}'.")
                                st.session_state.pending_upload = None
                                st.rerun()
                            else:
                                st.error(f"{r.json().get('detail', 'Unknown error')}")
                    else:
                        st.info("No existing tables to append to yet. Create a new table instead.")

        else:  # unstructured
            st.info(f"This PDF looks like a narrative document (no tables found). "
                     f"It will be stored as {pending['total_text_chunks']} searchable text chunk(s).")
            st.markdown("**Preview:**")
            st.text(pending["text_preview"] + ("..." if len(pending["text_preview"]) >= 800 else ""))

            if st.button("Save document", type="primary"):
                r = requests.post(f"{BACKEND_URL}/confirm-upload", json={"upload_id": pending["upload_id"]})
                if r.ok:
                    data = r.json()
                    st.success(f"Saved {data['rows_added']} text chunk(s) to the '{data['table_name']}' table.")
                    st.session_state.pending_upload = None
                    st.rerun()
                else:
                    st.error(f"{r.json().get('detail', 'Unknown error')}")