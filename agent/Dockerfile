FROM python:3.12-slim AS build

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim

RUN useradd --create-home --uid 10001 agent
WORKDIR /app
COPY --from=build /install /usr/local
COPY src /app/src
COPY samples /app/samples

ENV PYTHONPATH=/app/src \
    APP_ENV=production \
    AUTH_MODE=entra
USER agent
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "closed_agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
