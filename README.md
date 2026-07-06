# Text-to-SQL Agent — Phase 1 + Phase 2 + Phase 3 + Phase 4

- **Phase 1:** Natural language → SQL → Result, with a sample database.
- **Phase 2:** Upload a PDF (table-based or narrative) and turn it into queryable data.
- **Phase 3:** Export any query result as a formatted, downloadable PDF report.
- **Phase 4:** Self-correcting SQL, a query router (SQL vs Document Q&A), and conversation memory.

## 📁 Structure
```
text2sql_agent/
├── backend/
│   ├── main.py              # FastAPI app (endpoints, routing, retry loop, memory)
│   ├── database.py           # SQLite database setup, dynamic schema, table helpers
│   ├── llm_client.py          # Shared Anthropic client setup
│   ├── sql_agent.py           # NL -> SQL conversion, self-correction, safety checks
│   ├── router.py               # Decides: SQL query or document search?
│   ├── document_qa.py           # RAG-lite: answers questions from uploaded document text
│   ├── pdf_processor.py          # Extracts tables/text from uploaded PDFs
│   ├── report_generator.py        # Builds formatted PDF reports (SQL results or document answers)
│   ├── company.db                # (auto-generated) sample database
│   └── .env.example               # example API key file
├── frontend/
│   └── app.py                      # Streamlit UI (Ask a Question + Upload PDF tabs)
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

## 🔄 How Self-Correction Works (Phase 4)
When you ask a question, the agent:
1. Generates a SQL query and tries to run it.
2. If it fails (e.g. wrong column name, syntax error), the actual database error is sent back to the LLM along with the failed query, asking it to fix it.
3. This repeats up to **3 attempts total**. If it still fails, you get a clear error message instead of a cryptic one.
4. If it took more than 1 attempt, the UI shows a small note: *"🔄 The agent self-corrected its query."*

## 🔀 How the Query Router Works (Phase 4)
Every question first goes through a router:
- If you haven't uploaded any narrative (unstructured) PDFs yet, it always goes to the **SQL path** — no extra API call.
- If you have, the router decides: does this question need structured data (SQL) or does it need the *content* of an uploaded document (e.g. "what does the contract say about late payment fees?")? The document path searches the `documents` table content and has the LLM answer using only that text, citing the source filename.

## 🧠 How Conversation Memory Works (Phase 4)
The last 5 questions (and their SQL/answers) are sent along with each new question, so follow-ups work naturally:
> "Which employees are in Engineering?" → "And what's their total salary?" (the agent resolves "their" from the previous turn)

## 🎨 UI
The Streamlit UI uses a custom dark "console" theme (navy background, amber/blue/violet accents) with mode badges (SQL / DOCUMENT / OFF-TOPIC) on each result so it's clear how the agent routed your question. Theme lives in `frontend/.streamlit/config.toml` plus custom CSS injected in `app.py`.

## 🛡️ Off-Topic Question Handling
If you type something unrelated to your data or documents (e.g. a pasted paragraph, a message, a random question), the router now catches this and responds with a clear "this isn't related to your data" message **instead of forcing a hallucinated SQL query**. This is handled by `router.py`'s three-way classification (SQL / DOCUMENT / UNRELATED).

## 🗺️ Phases
- ✅ **Phase 1:** Core text-to-SQL agent.
- ✅ **Phase 2:** PDF upload — structured (tables) and unstructured (text) PDFs, loading data into the database.
- ✅ **Phase 3:** Exporting query results as a formatted PDF report.
- ✅ **Phase 4:** Self-correcting SQL, query router (SQL vs Document Q&A), and conversation memory.
- **Phase 5 (next):** Deployment (so the app isn't only accessible on your own machine).
