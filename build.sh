#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# 1. Load the meals dataset into the live database
python manage.py load_meals

# 2. Create the superuser directly via the Django ORM

python manage.py shell <<EOF
from django.contrib.auth import get_user_model

User = get_user_model()
email = "samueltoluwani169@gmail.com"
password = "samnaija001"

if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password)
    print("✅ Superuser created successfully!")
else:
    print("✅ Superuser already exists.")
EOF