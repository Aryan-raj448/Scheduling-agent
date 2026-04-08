FROM python:3.11-slim

WORKDIR /app

# Install uv securely from the official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency manifests
COPY pyproject.toml uv.lock ./

# Generate virtual environment and sync dependencies
RUN uv sync --frozen

# Copy the rest of the application
COPY . .

# Expose Hugging Face's default web routing port
EXPOSE 7860

# Run the OpenEnv ASGI server entrypoint
CMD ["uv", "run", "server"]
