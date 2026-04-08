FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run inference wrapper which interacts with env.py
CMD ["python", "inference.py"]
