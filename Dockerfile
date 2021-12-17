FROM ghcr.io/uwit-iam/poetry:latest AS env-base
RUN apt-get update && apt-get install -y curl jq

FROM env-base AS poetry-base
WORKDIR /webdriver
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-interaction

FROM poetry-base AS webdriver
COPY ./webdriver_recorder ./webdriver_recorder
COPY ./entrypoint.sh ./
RUN poetry install --no-interaction
ENTRYPOINT ["/webdriver/entrypoint.sh"]
