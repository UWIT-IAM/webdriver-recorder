FROM python:${PYTHON_VERSION}-slim AS env-base

# Python base config
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# pip base config
ENV PIP_NO_CACHE_DIR=yes
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100

# Poetry base config
ENV POETRY_NO_INTERACTION=1
ENV POETRY_VIRTUALENVS_CREATE=false

# Install pipx
RUN pip install --upgrade pipx

# Install poetry via pipx
RUN pipx install poetry

# Update PATH
ENV PATH="/root/.local/bin:${PATH}"

# Leave a note behind for tracking
RUN echo "${TIMESTAMP}" > /docker-tag

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
