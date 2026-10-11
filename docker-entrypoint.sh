#!/bin/bash
set -e

echo "Making and applying migrations"
python3 manage.py makemigrations --noinput
python3 manage.py migrate --noinput

echo "Starting server"
python3 manage.py runserver 0.0.0.0:8000
