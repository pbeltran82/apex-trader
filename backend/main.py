from fastapi import FastAPI

app = FastAPI(title="Apex Trader API")

@app.get("/")
def root():
    return {"status": "Apex Trader is running"}

@app.get("/health")
def health():
    return {"status": "ok"}