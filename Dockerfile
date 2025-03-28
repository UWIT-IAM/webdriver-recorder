FROM us-docker.pkg.dev/uwit-mci-iam/containers/base-python-3.9:latest AS env-base

WORKDIR /app
COPY poetry.lock pyproject.toml ./
RUN --mount=type=secret,id=gcloud_auth_credentials \
    md5sum /run/secrets/gcloud_auth_credentials
# get gcloud_auth_credentials secret from docker buildx (put in /run/secrets by default)
# install GAR keyring + setup ENV VAR per docs
# https://pypi.org/project/keyrings.google-artifactregistry-auth/
RUN --mount=type=secret,id=gcloud_auth_credentials \
    poetry self add keyrings.google-artifactregistry-auth && \
    export GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/gcloud_auth_credentials && \
    poetry install --only main --no-root --no-interaction \

RUN apt-get update && apt-get install -y curl jq

FROM env-base AS poetry-base
WORKDIR /webdriver
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-interaction

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
