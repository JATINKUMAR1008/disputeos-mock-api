FROM python:3.11-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code — wildcard so we don't have to remember to update
# this line every time a new module is added (this exact bug shipped to
# Render once when models.py and store.py were added in v2.0).
COPY *.py ./

# Alembic migration tree. Needed at container runtime because the entrypoint
# runs `alembic upgrade head` before the API starts.
COPY alembic.ini ./
COPY alembic ./alembic

EXPOSE 8888

# Run migrations against the direct Postgres endpoint, then start the API.
# `alembic upgrade head` reads DIRECT_DATABASE_URL from the container env;
# `uvicorn` reads DATABASE_URL (the pooler URL). Fails fast if either the
# migration or the app itself can't start, so container orchestrators
# (Render, Fly, Railway, etc.) see the failure clearly.
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8888"]
