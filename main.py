from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.search import router as search_router

app = FastAPI()

origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the /api/search route
app.include_router(search_router, prefix="/api/search")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
