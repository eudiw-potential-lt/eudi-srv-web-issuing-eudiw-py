FROM python:3.12 AS build

ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /

COPY pyproject.toml /pyproject.toml
COPY poetry.lock /poetry.lock

RUN touch README.md \
    && mkdir -p /app \
    && touch /app/__init__.py \
    && echo "[virtualenvs]" >> /poetry.toml \
    && echo "create = true" >> /poetry.toml \
    && echo "in-project = true" >> /poetry.toml \
    && pip install poetry \
    && poetry install --without dev

FROM python:3.12

ENV BUILD_TAG 2025-09-17-01
ENV PORT=5000
ENV HOST=0.0.0.0
ENV EIDAS_NODE_URL="https://preprod.issuer.eudiw.dev/EidasNode/"
ENV DYNAMIC_PRESENTATION_URL="https://dev.verifier-backend.eudiw.dev/ui/presentations/"
ENV SERVICE_URL="http://127.0.0.1:${PORT}/"
ENV FLASK_SECRET="secret"
ENV REVOCATION_API_KEY="secret"
ENV EIDASNODE_LIGHTTOKEN_SECRET="secret"
ENV FLASK_RUN_PORT=$PORT
ENV FLASK_RUN_HOST=$HOST
ENV REQUESTS_CA_BUNDLE=/app/secrets/cert.pem
ENV USE_GCP_LOGGER=0
ENV USE_FILE_LOGGER=1
ENV REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
ENV ENABLED_COUNTRIES=""
ENV PID_ISSUING_AUTHORITY="Test PID Issuer"
ENV PID_ORG_ID="Test mDL Issuer"
ENV MDL_ISSUING_AUTHORITY="Test mDL Issuer"
ENV QEAA_ISSUING_AUTHORITY="Test QEAA Issuer"

EXPOSE $PORT

VOLUME /app/secrets/cert.pem
VOLUME /app/secrets/cert.key
VOLUME /etc/eudiw/pid-issuer/privKey
VOLUME /etc/eudiw/pid-issuer/cert
VOLUME /tmp/log_dev

WORKDIR /app

RUN mkdir -p /tmp/log_dev \
    && chmod -R 755 /tmp/log_dev \
    && mkdir -p /etc/eudiw/pid-issuer/cert \
    && mkdir -p /etc/eudiw/pid-issuer/privKey

COPY --from=build /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=build /.venv /.venv
COPY ./app /app

CMD ["/.venv/bin/flask", "--app", ".", "run"]