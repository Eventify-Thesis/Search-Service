# Search Service Setup Guide

## Environment Variables

Create a `.env` file in the Search-Service directory with the following variables:

```bash
# Qdrant Cloud Configuration
QDRANT_URL=your_qdrant_cloud_url_here
QDRANT_API_KEY=your_qdrant_api_key_here

# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Google Cloud Speech-to-Text (if using service account file)
GOOGLE_APPLICATION_CREDENTIALS=config/gcloud/service-account.json
```

## Required API Keys

### 1. Qdrant Cloud

1. Go to [Qdrant Cloud Console](https://cloud.qdrant.io/)
2. Create a cluster or use existing one
3. Get your cluster URL and API key
4. Add them to your `.env` file as `QDRANT_URL` and `QDRANT_API_KEY`

### 2. Google Gemini API Key

1. Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Add it to your `.env` file as `GEMINI_API_KEY`

### 3. Google Cloud Speech-to-Text

- Ensure your service account JSON file is in `config/gcloud/service-account.json`
- Or set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable

## Installation

1. Install new dependencies:

```bash
pip install sentence-transformers==3.3.1 google-generativeai==0.8.3 python-dotenv
```

2. Ensure your Qdrant Cloud cluster is running and accessible

## New Endpoints

### POST /api/chat

Process natural language queries and return AI-generated responses with relevant events.

**Request:**

```json
{
  "query": "What music events are happening this weekend?",
  "user_id": "optional_user_id",
  "language": "en",
  "max_results": 5
}
```

**Response:**

```json
{
  "text": "I found some great music events for this weekend! Here are the top recommendations...",
  "events": [
    {
      "id": "123",
      "title": "Jazz Night at Blue Note",
      "description": "An evening of smooth jazz...",
      "city": "Hanoi",
      "start_time": "2024-01-20T19:00:00",
      "end_time": "2024-01-20T23:00:00",
      "category": "music",
      "score": 0.95
    }
  ],
  "query_embedding_time": 0.0,
  "search_time": 0.045,
  "generation_time": 1.234
}
```

## Features

- **Semantic Search**: Uses Qdrant Cloud's query method with the same embedding model (all-MiniLM-L6-v2) as your existing collection
- **Hybrid Search**: Leverages both dense and sparse models for better search results
- **AI Responses**: Generates natural language responses using Google Gemini
- **Event Context**: Provides relevant event details in responses
- **Performance Metrics**: Returns timing information for each step
- **Fallback Handling**: Graceful error handling with fallback responses

## Notes

- The chat endpoint uses the same Qdrant configuration as your existing `hybrid_searcher.py`
- Embedding is handled internally by Qdrant Cloud, so no local embedding model is needed for search
- Make sure your `.env` file has the correct `QDRANT_URL` and `QDRANT_API_KEY` values
