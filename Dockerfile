FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

RUN mkdir -p /outputs

ENV API_HOST=0.0.0.0
ENV API_PORT=8765
ENV OUTPUT_DIR=/outputs

EXPOSE 8765

CMD ["python", "main.py"]
