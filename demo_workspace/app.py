from fastapi import FastAPI

app = FastAPI(title="Invoice Microservice")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "invoice-api"}


@app.post("/invoice/{invoice_id}/process")
def process_invoice(invoice_id: str):
    return {"invoice_id": invoice_id, "state": "queued"}
