<<<<<<< HEAD
# Text-to-SQL Agent — Phase 1 + Phase 2 + Phase 3

- **Phase 1:** Natural language → SQL → Result, with a sample database.
- **Phase 2:** Upload a PDF (table-based or narrative) and turn it into queryable data.
- **Phase 3:** Export any query result as a formatted, downloadable PDF report.

## 📁 Structure
```
text2sql_agent/
├── backend/
│   ├── main.py              # FastAPI app (endpoints)
│   ├── database.py           # SQLite database setup, dynamic schema, table helpers
│   ├── sql_agent.py          # Claude API-based NL -> SQL conversion + safety checks
│   ├── pdf_processor.py       # Extracts tables/text from uploaded PDFs
│   ├── report_generator.py    # Builds formatted PDF reports from query results
│   ├── company.db            # (auto-generated) sample database
│   └── .env.example          # example API key file
├── frontend/
│   └── app.py                 # Streamlit UI (Ask a Question + Upload PDF tabs)
└── requirements.txt
```

## 📄 How PDF Upload Works (Phase 2)
1. Upload a PDF in the **"Upload PDF"** tab.
2. The agent automatically detects if it's:
   - **Structured** (contains a data table, e.g. an invoice) → you'll see a preview and can choose to:
     - **Create a new table** (give it a name), or
     - **Append to an existing table** (columns must match)
   - **Unstructured** (a narrative document/report) → its text is automatically saved into a `documents` table, split into searchable chunks.
3. Once saved, the new data immediately becomes queryable — the schema shown in the sidebar and used by the agent updates automatically, no restart needed.

## ⚙️ Setup

1. **Create a virtual environment (recommended):**
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your API key:**
   Copy `backend/.env.example` to `backend/.env` and add your Anthropic API key:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Then open the `.env` file and add your real key:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
   ```
   (Get a key here: https://console.anthropic.com/)

## ▶️ How to run

**Terminal 1 — Run the backend:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**Terminal 2 — Run the frontend:**
```bash
cd frontend
streamlit run app.py
```

This will open `http://localhost:8501` in your browser.

## 🧪 Example questions to try
- "How many employees are in the Sales department?"
- "What is the total sales amount per product?"
- "Who has the highest salary?"
- "How much revenue was made in February 2024?"

## 🔒 Safety
- The agent can only generate/execute `SELECT` queries.
- `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, etc. are hard-blocked (see the `validate_sql()` function in `sql_agent.py`).

## 📤 How PDF Export Works (Phase 3)
After running any query in the **"Ask a Question"** tab, click **"📄 Export as PDF"** below the result, then **"⬇️ Download PDF Report"**. The report includes the original question, the generated SQL, and a formatted results table (auto-switches to landscape for wide tables).

## 🗺️ Phases
- ✅ **Phase 1:** Core text-to-SQL agent.
- ✅ **Phase 2:** PDF upload — structured (tables) and unstructured (text) PDFs, loading data into the database.
- ✅ **Phase 3:** Exporting query results as a formatted PDF report.
- **Phase 4 (next):** Query router (SQL vs RAG over `documents` table), conversation memory, self-correction.
- **Phase 5:** Deployment.
=======
# Text-to-sql-Agents
>>>>>>> 86e8ecc9d3e3731fcb23060dd1ee5ee9946b5411
