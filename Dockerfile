# syntax=docker/dockerfile:1.7-labs

# Stage 1: build dependencies with uv
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install build tooling and uv
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Copy all necessary files for dependency installation
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Create project virtualenv ahead of dependency install for reuse in runtime stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

# Install project dependencies (not editable to avoid needing all source files)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /opt/venv/bin/python .


# Stage 2: runtime image
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install required runtime packages only
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        sqlite3 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Bring in pre-built Python dependencies
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" \
    WORKSPACE_DIR=/tmp/claude_orchestrator \
    LOG_DIR=/logs \
    ORCHESTRATOR_HOST=0.0.0.0 \
    ORCHESTRATOR_PORT=8001

# Create isolated user and required directories
RUN useradd -m -u 1000 -s /bin/bash madrox \
    && install -d -m 755 -o madrox -g madrox /app /data /logs /tmp/claude_orchestrator

WORKDIR /app

# Copy application source
COPY --chown=madrox:madrox src/ ./src/
COPY --chown=madrox:madrox --chmod=755 run_orchestrator.py run_orchestrator_stdio.py madrox-server madrox-mcp ./
COPY --chown=madrox:madrox --chmod=755 docker/entrypoint.sh /entrypoint.sh

USER madrox

# Expose orchestrator
EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "run_orchestrator.py"]
