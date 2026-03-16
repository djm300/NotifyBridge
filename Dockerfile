FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY SPECS.MD ./

RUN pip install --no-cache-dir .

EXPOSE 8000 2525 5514/udp

CMD ["notifybridge", "dev"]
