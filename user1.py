from fastapi import FastAPI

app = FastAPI()

@app.get("/profile")
def profile():
    return {
        "server": "User Service 1",
        "message": "Profile Data"
    }