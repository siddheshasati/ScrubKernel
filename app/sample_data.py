SAMPLE_FILES = {
    "server.log": """2026-05-28 10:14:22,812 ERROR payments-worker-2 request_id=hex-72941
Traceback (most recent call last):
  File "/srv/payments/repository.py", line 88, in open_connection
    pool.acquire(timeout=3.0)
TimeoutError: DB connection timeout after 3000ms

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/srv/payments/app.py", line 144, in process_invoice
    db = open_connection("primary-ledger")
  File "/srv/payments/repository.py", line 92, in open_connection
    raise RuntimeError("Unable to connect to primary-ledger database")
RuntimeError: Unable to connect to primary-ledger database
""",
    "database.config": """[database]
host=ledger-primary.internal.hexaware.demo
port=5432
pool_size=20
connect_timeout_ms=3000
retry_attempts=2
ssl_mode=require

[observability]
latency_slo_ms=250
error_budget_percent=0.1
""",
    "app.py": '''from fastapi import FastAPI

app = FastAPI(title="Invoice Microservice")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "invoice-api"}


@app.post("/invoice/{invoice_id}/process")
def process_invoice(invoice_id: str):
    return {"invoice_id": invoice_id, "state": "queued"}
''',
}


PROJECT_STRUCTURE_GUIDE = """
agentic-os-automation/
  main.py                    # Streamlit entrypoint
  .env                       # GROQ_API_KEY lives here, not in the UI
  app/
    config.py                # constants, paths, environment loading
    auth.py                  # local account creation and sign-in
    agent.py                 # LangChain Groq model and agent runner
    rag.py                   # upload extraction, ChromaDB indexing, retrieval
    project_builder.py       # runnable generated project scaffolds
    tools.py                 # decorated tools exposed to the agent
    security.py              # workspace boundary checks
    audit.py                 # MCP envelopes and audit log updates
    workspace.py             # demo directory reset and seed files
    ui.py                    # Streamlit layout
    sample_data.py           # mock files and project guidance
  demo_workspace/
    archive/
  generated_projects/        # real generated app folders, code, README, IDE tasks
  .app_data/
    users.json               # local salted password hashes
    uploads/                 # uploaded docs and image references
    chromadb/                # persistent local vector store
    run_logs/                # setup/run command logs
  requirements.txt

Simple scaling rule:
Keep UI, tools, security, audit, and agent setup in separate files so each part
can grow without turning the app into one large script. Keep generated apps in
`generated_projects/` so they are easy to open in VS Code, Cursor, or another IDE.
""".strip()
