from fastapi import FastAPI

app = FastAPI(title="TODO API - Relay Validation")

@app.get("/")
def read_root():
    return {"message": "Welcome to the TODO API. Database selection is pending."}
