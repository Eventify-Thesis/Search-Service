from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.getRelatedEvents import router as get_related_events_router
from api.search.semanticSearch import router as search_router
from api.search.searchMetadata import router as search_metadata_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to your gateway's host
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(get_related_events_router, prefix="/api/search")
app.include_router(search_metadata_router, prefix="/api/search")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
