"""
Streamlit Frontend - Phase 1 + Phase 2: Text-to-SQL Agent + PDF Upload

How to run:
    streamlit run app.py

The backend (FastAPI) must be running separately at: http://localhost:8000
"""
import streamlit as st
import requests
import pandas as pd

BACKEND_URL = "http://localhost:8000"

st.set_page_config(page_title="Text-to-SQL Agent", page_icon="🗂️", layout="wide")

st.title("🗂️ Text-to-SQL Agent")
st.caption("Ask questions about your data (SQL) or about uploaded documents (Q&A) — the agent figures out which one to use, and remembers your last few questions.")

if "history" not in st.session_state:
    st.session_state.history = []
if "pending_upload" not in st.session_state:
    st.session_state.pending_upload = None


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


# --- Sidebar: show the database schema ---
with st.sidebar:
    st.header("📋 Database Schema")
    schema_text = get_schema_text()
    if schema_text is not None:
        st.code(schema_text, language="text")
    else:
        st.error("⚠️ Could not connect to the backend server. Start it first:\n\n`uvicorn main:app --reload`")

    st.divider()
    st.subheader("💡 Example Questions")
    st.markdown("""
    **Data questions (SQL):**
    - How many employees are in the Sales department?
    - What is the total sales amount per product?
    - Who has the highest salary?

    **Follow-up (uses memory):**
    - And what about Marketing?

    **Document questions** (after uploading a narrative PDF):
    - What does the report say about revenue growth?
    - Summarize the uploaded document.
    """)

tab_query, tab_upload = st.tabs(["💬 Ask a Question", "📄 Upload PDF"])

# =========================================================
# TAB 1: Ask a Question
# =========================================================
with tab_query:
    question = st.text_input(
        "Type your question here:",
        placeholder="e.g. Who has the highest salary in the Engineering department?",
    )

    col1, col2 = st.columns([1, 5])
    with col1:
        run_clicked = st.button("🚀 Run Query", type="primary", use_container_width=True)

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
                st.error("⚠️ Could not connect to the backend. Please start the backend server first.")
                resp = None

        if resp is not None:
            if resp.ok:
                st.session_state.history.insert(0, resp.json())
            else:
                st.error(f"❌ Error: {resp.json().get('detail', 'Unknown error')}")
    elif run_clicked:
        st.warning("Please type a question first.")

    for item in st.session_state.history:
        with st.container(border=True):
            st.markdown(f"**❓ Question:** {item['question']}")

            if item.get("mode") == "document":
                # --- Document Q&A result ---
                st.markdown("**📚 Answer** (from uploaded documents):")
                st.write(item.get("answer", ""))
                sources = item.get("sources", [])
                if sources:
                    unique_files = sorted({s["filename"] for s in sources})
                    st.caption("Sources: " + ", ".join(unique_files))
            else:
                # --- SQL result ---
                st.markdown("**🧠 Generated SQL:**")
                if item.get("attempts", 1) > 1:
                    st.caption(f"🔄 The agent self-corrected its query ({item['attempts']} attempts before it worked).")
                st.code(item["sql"], language="sql")
                if item["row_count"] > 0:
                    df = pd.DataFrame(item["rows"], columns=item["columns"])
                    st.markdown(f"**📊 Result** ({item['row_count']} rows):")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info("The query ran successfully, but returned no results.")

            # --- PDF export (works for both modes) ---
            pdf_key = f"pdf_{hash(item['question'] + item.get('sql', '') + item.get('answer', ''))}"
            if st.button("📄 Export as PDF", key=f"btn_{pdf_key}"):
                with st.spinner("Generating PDF report..."):
                    try:
                        pdf_resp = requests.post(f"{BACKEND_URL}/export-pdf", json=item, timeout=30)
                    except requests.exceptions.ConnectionError:
                        pdf_resp = None
                        st.error("⚠️ Could not connect to the backend.")

                if pdf_resp is not None:
                    if pdf_resp.ok:
                        st.session_state[pdf_key] = pdf_resp.content
                    else:
                        st.error(f"❌ {pdf_resp.json().get('detail', 'Could not generate PDF')}")

            if pdf_key in st.session_state:
                st.download_button(
                    "⬇️ Download PDF Report",
                    data=st.session_state[pdf_key],
                    file_name="query_report.pdf",
                    mime="application/pdf",
                    key=f"dl_{pdf_key}",
                )

# =========================================================
# TAB 2: Upload PDF
# =========================================================
with tab_upload:
    st.markdown("Upload a PDF containing a **data table** (e.g. an invoice or sales sheet) "
                 "or a **narrative document** (e.g. a report) — the agent will detect which kind it is.")

    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    if uploaded_file is not None and st.button("🔍 Analyze PDF"):
        with st.spinner("Extracting content from the PDF..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                resp = requests.post(f"{BACKEND_URL}/upload-pdf", files=files, timeout=60)
            except requests.exceptions.ConnectionError:
                st.error("⚠️ Could not connect to the backend. Please start the backend server first.")
                resp = None

        if resp is not None:
            if resp.ok:
                st.session_state.pending_upload = resp.json()
            else:
                st.error(f"❌ Error: {resp.json().get('detail', 'Unknown error')}")
                st.session_state.pending_upload = None

    pending = st.session_state.pending_upload
    if pending is not None:
        st.divider()
        st.subheader(f"📎 {pending['filename']}")

        if pending["type"] == "structured":
            st.success(f"Detected **{len(pending['tables'])} table(s)** in this PDF.")

            for t in pending["tables"]:
                st.markdown(f"**Table {t['table_index'] + 1}** — {t['total_rows']} rows, columns: `{', '.join(t['columns'])}`")
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
                    if st.button("✅ Save as new table", key=f"savenew_{t['table_index']}"):
                        r = requests.post(f"{BACKEND_URL}/confirm-upload", json={
                            "upload_id": pending["upload_id"],
                            "table_index": t["table_index"],
                            "mode": "new_table",
                            "table_name": new_name,
                        })
                        if r.ok:
                            data = r.json()
                            st.success(f"✅ Saved {data['rows_added']} rows into new table '{data['table_name']}'.")
                            st.session_state.pending_upload = None
                            st.rerun()
                        else:
                            st.error(f"❌ {r.json().get('detail', 'Unknown error')}")
                else:
                    existing = pending.get("existing_tables", [])
                    if existing:
                        target = st.selectbox("Choose the table to append to:", existing, key=f"target_{t['table_index']}")
                        if st.button("✅ Append to this table", key=f"saveappend_{t['table_index']}"):
                            r = requests.post(f"{BACKEND_URL}/confirm-upload", json={
                                "upload_id": pending["upload_id"],
                                "table_index": t["table_index"],
                                "mode": "append",
                                "target_table": target,
                            })
                            if r.ok:
                                data = r.json()
                                st.success(f"✅ Appended {data['rows_added']} rows into '{data['table_name']}'.")
                                st.session_state.pending_upload = None
                                st.rerun()
                            else:
                                st.error(f"❌ {r.json().get('detail', 'Unknown error')}")
                    else:
                        st.info("No existing tables to append to yet — create a new table instead.")

        else:  # unstructured
            st.info(f"This PDF looks like a **narrative document** (no tables found). "
                     f"It will be stored as {pending['total_text_chunks']} searchable text chunk(s).")
            st.markdown("**Preview:**")
            st.text(pending["text_preview"] + ("..." if len(pending["text_preview"]) >= 800 else ""))

            if st.button("✅ Save document"):
                r = requests.post(f"{BACKEND_URL}/confirm-upload", json={"upload_id": pending["upload_id"]})
                if r.ok:
                    data = r.json()
                    st.success(f"✅ Saved {data['rows_added']} text chunk(s) to the '{data['table_name']}' table.")
                    st.session_state.pending_upload = None
                    st.rerun()
                else:
                    st.error(f"❌ {r.json().get('detail', 'Unknown error')}")