#!/bin/bash

# Let the DB start
python /code/app/prestart.py

# Run migrations
alembic upgrade head

uvicorn app.main:app --host 0.0.0.0 --port 80