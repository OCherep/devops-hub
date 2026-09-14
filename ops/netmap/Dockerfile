FROM python:3.12-alpine
RUN apk add --no-cache nmap \
 && pip install --no-cache-dir psycopg2-binary
WORKDIR /app
COPY app.py /app/app.py
COPY ui /app/ui
EXPOSE 8092
CMD ["python3","-u","/app/app.py"]
