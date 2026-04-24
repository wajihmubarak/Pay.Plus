FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install flask
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]
