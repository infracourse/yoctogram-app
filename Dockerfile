FROM python:3.12-slim AS builder

ENV POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

# to run poetry directly as soon as it's installed
ENV PATH="$POETRY_HOME/bin:$PATH"

# install poetry
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

# copy only pyproject.toml and poetry.lock file nothing else here
COPY ./poetry.lock ./pyproject.toml ./

RUN poetry export -f requirements.txt --output requirements.txt

# ---------------------------------------------------------------------

FROM python:3.12-slim

# still need curl for the ECS container health check!
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic-dev curl

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="$PYTHONPATH:/code"

WORKDIR /code

# copy the venv folder from builder image 
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY app app
COPY alembic alembic
COPY alembic.ini alembic.ini
COPY prestart.sh prestart.sh

EXPOSE 80

CMD ["./prestart.sh"]