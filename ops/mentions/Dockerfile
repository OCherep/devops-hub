FROM python:3.12-alpine
RUN pip install --no-cache-dir psycopg2-binary
WORKDIR /app
COPY app.py /app/app.py
COPY ui /app/ui
EXPOSE 8091
CMD ["python","-u","/app/app.py"]
