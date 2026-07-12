# socketmock: SocketMock protocol server + admin/dashboard HTTP API in one process.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY SocketMock ./SocketMock

# 2775: SocketMock protocol endpoint -- point your client here
# 8080: admin REST API + dashboard -- open http://localhost:8080/ in a browser
EXPOSE 2775 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/__admin/health', timeout=2)" || exit 1

ENTRYPOINT ["python", "-m", "SocketMock.app"]
CMD ["--host", "0.0.0.0", "--port", "2775", "--admin-host", "0.0.0.0", "--admin-port", "8080"]
