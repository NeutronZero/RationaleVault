# TODO API Implementation Plan

## Goal
Build a simple TODO API to validate Relay's multi-agent context preservation capabilities.

## Requirements
- Create project structure
- Define endpoints
- Decide database (Question: SQLite or PostgreSQL?)
- Create implementation plan (FastAPI decided)

## Proposed Project Structure
```text
todo_api/
├── main.py            # FastAPI endpoints
├── database.py        # Database connection/session
├── models.py          # Database models
└── schemas.py         # Pydantic schemas
```

## Proposed Endpoints
- `GET /todos` - List all TODOs
- `POST /todos` - Create a new TODO
- `GET /todos/{id}` - Get a specific TODO
- `PUT /todos/{id}` - Update a TODO
- `DELETE /todos/{id}` - Delete a TODO
