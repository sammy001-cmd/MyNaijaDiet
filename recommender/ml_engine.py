"""
MyNaijaDiet — ML Engine (LightGBM Only)
=========================================
Stripped down from 4-model ensemble to single LightGBM model.

Why LightGBM:
- 88% accuracy (matches ANN, beats Random Forest)
- Loads in < 1 second (vs 30 seconds for TensorFlow)
- No heavy dependencies
- Handles tabular nutrition data natively
- Production-ready

The model scores each meal against a user's goal and returns
a ranked list. Higher score = better match for that goal.
"""

import os
import pickle
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR   = os.path.join(BASE_DIR, 'ml')

# ── Load LightGBM model once at module level ──────────────────────────────
with open(os.path.join(ML_DIR, 'lightgbm.pkl'), 'rb') as f:
    lgb_model = pickle.load(f)

with open(os.path.join(ML_DIR, 'feature_names.pkl'), 'rb') as f:
    feature_names = pickle.load(f)

print('[MyNaijaDiet] LightGBM model loaded.')

# ── Encoding maps (must match preprocessing.py exactly) ───────────────────
ORDINAL_MAPS = {
    'prep_time':        {'short': 0, 'medium': 1, 'long': 2},
    'price_range':      {'low': 0, 'medium': 1, 'high': 2},
    'goal_suitability': {'weight_loss': 0, 'maintenance': 1, 'muscle_gain': 2},
    'diet_type':        {'low-calorie': 0, 'vegetarian': 1, 'balanced': 2,
                         'high-protein': 3, 'energy-rich': 4, 'indulgent': 5},
    'category':         {'breakfast': 0, 'snack': 1, 'lunch': 2, 'dinner': 3},
}

GOAL_INDEX = {'weight_loss': 0, 'maintenance': 1, 'muscle_gain': 2}

TASTE_OPTIONS = [
    'bitter-savory', 'mild', 'mild-savory', 'mild-sweet', 'savory',
    'savory-mild', 'savory-smoky', 'savory-sour', 'savory-spicy',
    'savory-sweet', 'smoky-spicy', 'sour-savory', 'sour-sweet',
    'spicy', 'spicy-savory', 'spicy-smoky', 'spicy-sweet',
    'sweet', 'sweet-savory', 'sweet-sour', 'sweet-spicy',
]

REGION_OPTIONS = [
    'General', 'Hausa/North', 'South-South', 'Southeast/Igbo', 'Yoruba/Southwest'
]


def _encode_meal(meal):
    """Convert a Meal instance to a feature vector for LightGBM."""
    row = {}

    # Ordinal features
    row['category']         = ORDINAL_MAPS['category'].get(meal.category, 2)
    row['goal_suitability'] = ORDINAL_MAPS['goal_suitability'].get(meal.goal_suitability, 1)
    row['diet_type']        = ORDINAL_MAPS['diet_type'].get(meal.diet_type, 2)
    row['prep_time']        = ORDINAL_MAPS['prep_time'].get(meal.prep_time, 1)
    row['price_range']      = ORDINAL_MAPS['price_range'].get(meal.price_range, 0)

    # Numeric features
    row['calories_kcal'] = meal.calories_kcal
    row['protein_g']     = meal.protein_g
    row['carb_g']        = meal.carb_g
    row['fat_g']         = meal.fat_g

    # Meal time binary
    meal_times = [t.strip() for t in meal.meal_time.split(',')]
    for mt in ['breakfast', 'lunch', 'dinner', 'snack']:
        row[f'meal_time_{mt}'] = 1 if mt in meal_times else 0

    # One-hot region
    for region in REGION_OPTIONS:
        row[f'region_{region}'] = 1 if meal.region == region else 0

    # One-hot taste profile
    for taste in TASTE_OPTIONS:
        row[f'taste_profile_{taste}'] = 1 if meal.taste_profile == taste else 0

    # Engineered features
    kcal_p = meal.protein_g * 4
    kcal_c = meal.carb_g    * 4
    kcal_f = meal.fat_g     * 9
    total  = max(kcal_p + kcal_c + kcal_f, 1)

    row['macro_ratio_protein']  = round(kcal_p / total, 4)
    row['macro_ratio_carb']     = round(kcal_c / total, 4)
    row['macro_ratio_fat']      = round(kcal_f / total, 4)
    row['calorie_density']      = 0 if meal.calories_kcal < 300 else (1 if meal.calories_kcal < 600 else 2)
    row['protein_per_100kcal']  = round((meal.protein_g / meal.calories_kcal) * 100, 2) if meal.calories_kcal else 0

    return np.array([row.get(f, 0) for f in feature_names], dtype=np.float32)


def score_meals(user_goal, meals_queryset):
    """
    Score all meals using LightGBM.
    Returns list of (meal, score) tuples sorted by score descending.

    Args:
        user_goal: 'weight_loss', 'maintenance', or 'muscle_gain'
        meals_queryset: Django Meal queryset

    Returns:
        List of (Meal, float) sorted by relevance score descending
    """
    goal_idx = GOAL_INDEX.get(user_goal, 1)
    scored   = []

    for meal in meals_queryset:
        try:
            vector = _encode_meal(meal).reshape(1, -1)
            prob   = lgb_model.predict_proba(vector)[0][goal_idx]
            scored.append((meal, float(prob)))
        except Exception:
            scored.append((meal, 0.0))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def get_recommendations(user_goal, meals_queryset, top_n=50):
    """
    Get top N meals ranked by LightGBM score for a given goal.
    Used by recommendations page.
    """
    scored = score_meals(user_goal, meals_queryset)
    return [meal for meal, score in scored[:top_n]]