import os
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.db.models import Q
from recommender.models import Meal
from duckduckgo_search import DDGS

class Command(BaseCommand):
    help = 'Automatically downloads images for meals that do not have one'

    def handle(self, *args, **kwargs):
        meals = Meal.objects.filter(Q(image__isnull=True) | Q(image=''))
        
        if not meals:
            self.stdout.write(self.style.SUCCESS("All meals already have images!"))
            return

        with DDGS() as ddgs:
            for meal in meals:
                self.stdout.write(f"Searching image for: {meal.food_name}...")
                
                # Make the search query specific to get better results
                query = f"Delicious Nigerian {meal.food_name} food high quality"
                
                try:
                    # Search for 1 image
                    results = list(ddgs.images(query, max_results=1))
                    
                    if results:
                        image_url = results[0]['image']
                        
                        # Download the image
                        response = requests.get(image_url, timeout=10)
                        if response.status_code == 200:
                            # Save it to the Django model
                            file_name = f"{meal.food_name.replace(' ', '_').lower()}.jpg"
                            meal.image.save(file_name, ContentFile(response.content), save=True)
                            self.stdout.write(self.style.SUCCESS(f"Successfully saved {file_name}"))
                        else:
                            self.stdout.write(self.style.ERROR(f"Failed to download image from URL for {meal.food_name}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"No image found for {meal.food_name}"))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing {meal.food_name}: {str(e)}"))