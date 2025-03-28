FROM us-docker.pkg.dev/uwit-mci-iam/containers/base-python-3.9:latest AS poetry-base
WORKDIR /webdriver
COPY pyproject.toml poetry.lock ./
RUN --mount=type=secret,id=gcloud_auth_credentials \
    poetry self add keyrings.google-artifactregistry-auth && \
    export GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcloud_auth_credentials && \
    poetry install --no-root --no-interaction

FROM poetry-base as webdriver-source
WORKDIR /webdriver
COPY ./webdriver_recorder ./webdriver_recorder
ENV PYTHONPATH="/webdriver"
COPY ./entrypoint.sh ./
ENTRYPOINT ["/webdriver/entrypoint.sh"]

FROM poetry-base AS webdriver-native
WORKDIR /webdriver
COPY ./webdriver_recorder ./webdriver_recorder
COPY ./entrypoint.sh ./
RUN poetry install --no-interaction && rm pyproject.toml poetry.lock
