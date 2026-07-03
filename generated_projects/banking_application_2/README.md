# Banking Application

This project was generated from the prompt:

> banking application

## What It Does

The app is a local Streamlit banking dashboard. It manages demo customers,
accounts, balances, deposits, withdrawals, and a simple transaction ledger.

## Files

- `app.py` contains the Streamlit UI.
- `src/banking_store.py` contains local data and transaction helpers.
- `data/banking_data.json` is created automatically on first run and stores local demo data.
- `docs/ARCHITECTURE.md` explains the generated app layout.
- `requirements.txt` lists the Python packages needed by the project.
- `.vscode/tasks.json` gives VS Code setup and run tasks.

## Run

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The app stores data locally in this project folder. It is a demo scaffold, not
production banking software.
