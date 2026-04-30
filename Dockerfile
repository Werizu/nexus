FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client iputils-ping iproute2 wakeonlan && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/ core/
COPY plugins/ plugins/
COPY config/ config/
COPY scenes/ scenes/

RUN mkdir -p data

RUN mkdir -p /root/.ssh

CMD ["uvicorn", "core.main:app", "--host", "0.0.0.0", "--port", "8000"]
