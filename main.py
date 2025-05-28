from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.getRelatedEvents import router as get_related_events_router
from api.search.semanticSearch import router as search_router
from api.search.searchMetadata import router as search_metadata_router
from api.search.events_this_month import router as events_this_month_router
from api.search.events_this_week import router as events_this_week_router
from api.search.events_by_categories import router as events_by_categories_router
from api.speech import router as speech_router
from api.chat import router as chat_router

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
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
app.include_router(events_this_month_router, prefix="/api/search")
app.include_router(events_this_week_router, prefix="/api/search")
app.include_router(events_by_categories_router, prefix="/api/search")
app.include_router(speech_router, prefix="/api")
app.include_router(chat_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8003, reload=True)
