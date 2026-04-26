FROM python:3.12.9-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV VENV_PATH=/opt/venv

WORKDIR /app

COPY requirements.txt .

RUN python -m venv ${VENV_PATH} \
    && ${VENV_PATH}/bin/pip install --no-cache-dir --upgrade pip \
    && ${VENV_PATH}/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

FROM gcr.io/distroless/python3-debian12:nonroot

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/opt/venv/bin:${PATH}

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app /app

EXPOSE 8000

CMD ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]