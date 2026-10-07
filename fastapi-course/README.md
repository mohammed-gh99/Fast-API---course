# FastAPI Course Project

A beginner-friendly FastAPI project built as part of my backend and API learning journey.

## Features

* CRUD operations for jokes
* SQLite database with SQLModel
* Pydantic data validation
* OAuth2 password authentication
* JWT access tokens
* Password hashing with Argon2
* Role-based authorization
* Protected API endpoints
* Query parameters, filtering, pagination, and partial updates
* Environment variables for sensitive configuration

## Technologies

* Python
* FastAPI
* SQLModel
* SQLite
* Pydantic
* JWT
* OAuth2
* pwdlib

## Running the Project

Create and activate the virtual environment:

```bash
python -m venv .venv
source .venv/Scripts/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file:

```env
SECRET_KEY=your_secret_key
```

Run the application:

```bash
python -m uvicorn main:app --reload
```

Open the API documentation:

```text
http://127.0.0.1:8000/docs
```

## Authentication

The API uses OAuth2 with JWT authentication.

Users can obtain an access token through:

```text
POST /token
```

Protected endpoints require a Bearer token.

## Authorization

The project includes role-based authorization:

* `user` → regular authenticated user
* `admin` → can access admin-only operations such as deleting jokes

## Purpose

This project was built to practice the fundamentals of designing and building APIs with FastAPI, including database integration, authentication, authorization, validation, and API testing.
