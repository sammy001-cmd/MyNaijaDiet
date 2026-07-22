from django import forms
from .models import Meal


class MealEditForm(forms.Form):
    """
    Used for both 'create' and 'update' proposals. Staff fill this out
    normally; on submit, the view packages the cleaned data into a
    MealEdit.payload rather than touching Meal directly.
    """
    food_name        = forms.CharField(max_length=200)
    category          = forms.ChoiceField(choices=Meal.CATEGORY_CHOICES)
    region            = forms.ChoiceField(choices=Meal.REGION_CHOICES)
    meal_time         = forms.CharField(
        max_length=100,
        help_text="Comma-separated: breakfast,lunch,dinner,snack"
    )
    calories_kcal     = forms.IntegerField(min_value=0)
    protein_g         = forms.FloatField(min_value=0)
    carb_g            = forms.FloatField(min_value=0)
    fat_g             = forms.FloatField(min_value=0)
    goal_suitability  = forms.ChoiceField(choices=Meal.GOAL_CHOICES)
    diet_type         = forms.ChoiceField(choices=Meal.DIET_TYPE_CHOICES)
    taste_profile     = forms.CharField(max_length=100)
    prep_time         = forms.ChoiceField(choices=Meal.PREP_TIME_CHOICES)
    price_range       = forms.ChoiceField(choices=Meal.PRICE_CHOICES)
    image             = forms.ImageField(required=False, help_text="Optional — leave blank to keep the current image.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-input').strip()