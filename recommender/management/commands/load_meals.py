"""
Management command to load MyNaijaDiet dataset into the database.

Usage:
    python manage.py load_meals
    python manage.py load_meals --clear        (wipe existing meals first)
    python manage.py load_meals --file path/to/custom.csv
"""

import os
import csv
from django.core.management.base import BaseCommand, CommandError
from recommender.models import Meal


class Command(BaseCommand):
    help = 'Load Nigerian food dataset from CSV into the Meal table'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Path to the CSV file. Defaults to mynaijadiet_dataset_v2.csv in the project root.',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete all existing meals before loading. Use with caution.',
        )

    def handle(self, *args, **options):

        # ── Resolve file path ────────────────────────────────────────────
        if options['file']:
            csv_path = options['file']
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__)))
            ))
            csv_path = os.path.join(base_dir, 'mynaijadiet_dataset_v2.csv')

        if not os.path.exists(csv_path):
            raise CommandError(
                f'CSV file not found at: {csv_path}\n'
                f'Place mynaijadiet_dataset_v2.csv in your project root, '
                f'or pass --file /full/path/to/file.csv'
            )

        self.stdout.write(f'Loading from: {csv_path}')

        if options['clear']:
            count = Meal.objects.count()
            Meal.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Cleared {count} existing meal(s).')
            )

        created_count = 0
        skipped_count = 0
        error_count = 0

        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)

            for row_num, row in enumerate(reader, start=2):
                food_name = row.get('food_name', '').strip()

                if not food_name:
                    self.stdout.write(
                        self.style.WARNING(f'Row {row_num}: Empty food_name — skipped.')
                    )
                    skipped_count += 1
                    continue

                if Meal.objects.filter(food_name=food_name).exists():
                    self.stdout.write(f'  Row {row_num}: "{food_name}" already exists — skipped.')
                    skipped_count += 1
                    continue

                try:
                    Meal.objects.create(
                        food_name        = food_name,
                        category         = row['category'].strip(),
                        region           = row['region'].strip(),
                        meal_time        = row['meal_time'].strip(),
                        calories_kcal    = int(row['calories_kcal']),
                        protein_g        = float(row['protein_g']),
                        carb_g           = float(row['carb_g']),
                        fat_g            = float(row['fat_g']),
                        goal_suitability = row['goal_suitability'].strip(),
                        diet_type        = row['diet_type'].strip(),
                        taste_profile    = row['taste_profile'].strip(),
                        prep_time        = row['prep_time'].strip(),
                        price_range      = row['price_range'].strip(),
                    )
                    created_count += 1

                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Row {row_num} — "{food_name}": {str(e)}')
                    )
                    error_count += 1

        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(
            self.style.SUCCESS(f'✓ Created : {created_count} meals')
        )
        if skipped_count:
            self.stdout.write(
                self.style.WARNING(f'⚠ Skipped : {skipped_count} (duplicates or empty)')
            )
        if error_count:
            self.stdout.write(
                self.style.ERROR(f'✗ Errors  : {error_count} rows failed')
            )
        self.stdout.write(
            f'  Total in DB: {Meal.objects.count()} meals'
        )
        self.stdout.write('=' * 50)
