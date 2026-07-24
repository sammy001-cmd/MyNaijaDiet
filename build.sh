#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# 1. Load the meals dataset into the live database
python manage.py load_meals

# 2. Create the superuser automatically (the '|| true' part prevents the build from crashing on future deploys if the user already exists)
# 2. Create the superuser automatically using ONLY the email
python manage.py createsuperuser --noinput --email $ADMIN_EMAIL || true