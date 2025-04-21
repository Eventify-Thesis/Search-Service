# Qdrant Service

This project provides a service layer for interacting with [Qdrant](https://qdrant.tech/), an open-source vector database for efficient similarity search and AI applications.

## Features
- API endpoints for searching and managing vector data
- Hybrid search capabilities
- Dockerized deployment
- Environment-based configuration

## Project Structure
- `api/` — API endpoints (e.g., `search.py`)
- `app/` — Core application logic (e.g., `hybrid_searcher.py`)
- `jobs/` — Background jobs and tasks
- `qdrant_storage/` — Storage and database-related code
- `main.py` — Application entry point
- `requirements.txt` — Python dependencies
- `docker-compose.yml` — Multi-container Docker setup
- `Dockerfile` — Docker image definition

## Getting Started

### Prerequisites
- Python 3.8+
- Docker & Docker Compose

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/qdrant-service.git
   cd qdrant-service
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Running with Docker
```bash
docker-compose up --build
```

### Running Locally
```bash
python main.py
```

### Environment Variables
Copy `.env.example` to `.env` and update as needed.

## Usage
- Access the API endpoints as documented in `api/`
- Use the hybrid searcher for advanced vector search

## License
MIT License
