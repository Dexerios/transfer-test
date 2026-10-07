FROM python:3.11.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# several workers so slow Roblox writes don't queue every upload behind one request
CMD gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 2 --threads 8 --timeout 60 app:app
