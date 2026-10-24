cd /opt/app
cat > Dockerfile << 'EOF'
FROM python:3.14-slim
WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

ENV PATH="/app/.venv/bin:$PATH"
CMD ["sh", "-c", "alembic upgrade head && python -m app.main"]
EOF

cat > .dockerignore << 'EOF'
.git
.idea
.venv
__pycache__
.env
EOF

docker compose up -d --build
docker compose logs -f app