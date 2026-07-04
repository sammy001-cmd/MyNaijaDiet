"""
MyNaijaDiet — Weekly Meal Plan Generator v2
=============================================
Fixes from v1:
  1. Day calculation uses plan offset (not isoweekday) — fixes "wrong day" bug
  2. Variety rules — no same food family more than twice per week
  3. No same base ingredient (e.g. Amala) more than once per day
  4. Feedback-aware scoring — low-rated meals ranked lower

Plan durations: 1 week (7 days), 2 weeks (14 days), 1 month (28 days)
"""

from datetime import timedelta, date
from django.utils import timezone
from .models import Meal, MealPlan, MealPlanEntry

SLOT_RATIOS = {
    'breakfast': 0.25,
    'lunch':     0.35,
    'dinner':    0.30,
    'snack':     0.10,
}

TOLERANCE = 0.28

PLAN_LENGTHS = {
    '1_week':  7,
    '2_weeks': 14,
    '1_month': 28,
}

# Food family groups — meals sharing a base ingredient
# Used to prevent e.g. Tuwo appearing 5x a week
FOOD_FAMILIES = {
    'amala':       ['amala'],
    'eba':         ['eba', 'garri'],
    'pounded_yam': ['pounded yam'],
    'fufu':        ['fufu', 'akpu'],
    'semo':        ['semo', 'semovita'],
    'tuwo':        ['tuwo'],
    'jollof':      ['jollof rice'],
    'fried_rice':  ['fried rice'],
    'indomie':     ['indomie'],
    'spaghetti':   ['spaghetti'],
    'bread':       ['bread'],
    'yam':         ['yam and', 'yamarita', 'yam porridge', 'fried yam'],
    'plantain':    ['fried plantain', 'plantain porridge', 'roasted plantain', 'bole'],
    'beans':       ['beans', 'moi moi', 'akara'],
}

MAX_FAMILY_PER_WEEK = 2   # same food family max 2x per week
MAX_FAMILY_PER_DAY  = 1   # same food family max 1x per day


def _get_food_family(meal_name):
    """Return the food family key for a meal name, or None."""
    name_lower = meal_name.lower()
    for family, keywords in FOOD_FAMILIES.items():
        if any(kw in name_lower for kw in keywords):
            return family
    return None


def _get_scored_meals(goal, user=None):
    """
    Get all meals scored by LightGBM.
    If user provided, apply feedback penalty to low-rated meals.
    """
    try:
        from .ml_engine import score_meals
        all_meals = Meal.objects.all()
        scored    = score_meals(goal, all_meals)
    except Exception:
        import random
        meals = list(Meal.objects.all())
        random.shuffle(meals)
        scored = [(m, 0.5) for m in meals]

    # Apply feedback penalty if user provided
    if user:
        try:
            from .models import MealFeedback
            feedback = {
                f.meal_id: f.rating
                for f in MealFeedback.objects.filter(user=user)
            }
            adjusted = []
            for meal, score in scored:
                rating  = feedback.get(meal.id)
                if rating is not None:
                    # Penalty: rating 1 → -0.3, rating 2 → -0.15,
                    # rating 4 → +0.1, rating 5 → +0.2
                    penalty = (rating - 3) * 0.075
                    score   = max(0.0, min(1.0, score + penalty))
                adjusted.append((meal, score))
            adjusted.sort(key=lambda x: x[1], reverse=True)
            return adjusted
        except Exception:
            pass

    return scored


def _pick_for_slot(slot, budget, scored_meals, used_ids,
                   week_family_count, day_family_set):
    """
    Pick the best available meal for a slot respecting:
    - Calorie budget (±TOLERANCE)
    - Not already used (used_ids)
    - Variety: food family not overused this week
    - Variety: food family not repeated today
    """
    min_kcal = budget * (1 - TOLERANCE)
    max_kcal = budget * (1 + TOLERANCE)

    def is_variety_ok(meal):
        family = _get_food_family(meal.food_name)
        if family is None:
            return True
        if family in day_family_set:
            return False   # already had this family today
        if week_family_count.get(family, 0) >= MAX_FAMILY_PER_WEEK:
            return False   # used this family too much this week
        return True

    # Pass 1: strict budget + variety
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if not (min_kcal <= meal.calories_kcal <= max_kcal):
            continue
        if is_variety_ok(meal):
            return meal

    # Pass 2: relax variety constraint, keep budget
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if min_kcal <= meal.calories_kcal <= max_kcal:
            return meal

    # Pass 3: relax everything, just pick closest calorie match
    candidates = []
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        diff = abs(meal.calories_kcal - budget)
        candidates.append((diff, score, meal))

    if candidates:
        candidates.sort(key=lambda x: (x[0], -x[1]))
        return candidates[0][2]

    return None


def generate_weekly_plan(user, profile, duration='1_week', regenerate=False):
    """
    Generate or retrieve a meal plan for the given duration.

    Day numbering: day 1 = plan start date, day 2 = next day, etc.
    This is independent of weekday — avoids the isoweekday bug.
    """
    today      = timezone.now().date()
    num_days   = PLAN_LENGTHS.get(duration, 7)
    start_date = today
    end_date   = today + timedelta(days=num_days - 1)

    # Delete existing if regenerating
    if regenerate:
        MealPlan.objects.filter(user=user, is_active=True).delete()

    # Return existing plan if it covers today
    existing = MealPlan.objects.filter(
        user        = user,
        is_active   = True,
        start_date__lte = today,
        end_date__gte   = today,
    ).first()

    if existing and not regenerate:
        return existing

    # Deactivate any stale plans
    MealPlan.objects.filter(user=user, is_active=True).update(is_active=False)

    # Create new plan
    plan = MealPlan.objects.create(
        user       = user,
        plan_name  = f'{num_days}-Day Meal Plan',
        start_date = start_date,
        end_date   = end_date,
        is_active  = True,
    )

    daily_target      = int(profile.get_daily_calorie_target())
    goal              = profile.health_goal
    scored_meals      = _get_scored_meals(goal, user=user)
    used_ids          = set()           # meals used across whole plan
    week_family_count = {}              # food family usage this week

    entries_to_create = []

    for day_offset in range(num_days):
        day_number      = day_offset + 1
        day_used_ids    = set()
        day_family_set  = set()

        # Reset week family count every 7 days
        if day_offset % 7 == 0:
            week_family_count = {}

        for slot, ratio in SLOT_RATIOS.items():
            budget   = daily_target * ratio
            excluded = used_ids | day_used_ids

            meal = _pick_for_slot(
                slot, budget, scored_meals, excluded,
                week_family_count, day_family_set
            )

            if meal:
                day_used_ids.add(meal.id)
                family = _get_food_family(meal.food_name)
                if family:
                    day_family_set.add(family)
                    week_family_count[family] = week_family_count.get(family, 0) + 1

                entries_to_create.append(
                    MealPlanEntry(
                        meal_plan    = plan,
                        meal         = meal,
                        day          = day_number,
                        meal_time    = slot,
                        portion_size = 1.0,
                    )
                )

        used_ids |= day_used_ids

        # Reset used_ids after 2 weeks to allow repetition in long plans
        if day_offset == 13:
            used_ids = set()

    MealPlanEntry.objects.bulk_create(entries_to_create)
    return plan


def get_today_meals(plan):
    """
    Get today's 4 meals using plan-relative day number.
    day 1 = plan start date. No isoweekday used.
    """
    today      = timezone.now().date()
    day_number = (today - plan.start_date).days + 1

    # Safety check — if today is outside plan range
    if day_number < 1:
        day_number = 1
    total_days = (plan.end_date - plan.start_date).days + 1
    if day_number > total_days:
        day_number = total_days

    entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day       = day_number,
    ).select_related('meal')

    result = {'breakfast': None, 'lunch': None, 'dinner': None, 'snack': None}
    for entry in entries:
        if entry.meal_time in result:
            result[entry.meal_time] = entry.meal

    return result, day_number


def get_week_plan_display(plan, week_offset=0):
    """
    Get 7 days of the plan for display in the weekly calendar.
    week_offset=0 = first 7 days of plan, week_offset=1 = days 8-14, etc.
    """
    today     = timezone.now().date()
    start_day = (week_offset * 7) + 1
    end_day   = start_day + 6

    entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day__gte  = start_day,
        day__lte  = end_day,
    ).select_related('meal')

    # Group by day
    day_entries = {}
    for entry in entries:
        if entry.day not in day_entries:
            day_entries[entry.day] = {}
        day_entries[entry.day][entry.meal_time] = entry.meal

    days_display = []
    day_names    = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday']

    for i, day_num in enumerate(range(start_day, end_day + 1)):
        meals    = day_entries.get(day_num, {})
        day_date = plan.start_date + timedelta(days=day_num - 1)

        breakfast = meals.get('breakfast')
        lunch     = meals.get('lunch')
        dinner    = meals.get('dinner')
        snack     = meals.get('snack')

        total_kcal = sum(
            m.calories_kcal for m in [breakfast, lunch, dinner, snack] if m
        )

        days_display.append({
            'day_number': day_num,
            'day_name':   day_names[i % 7],
            'date':       day_date.strftime('%b %d'),
            'is_today':   day_date == today,
            'breakfast':  breakfast,
            'lunch':      lunch,
            'dinner':     dinner,
            'snack':      snack,
            'total_kcal': total_kcal,
        })

    return days_display


def swap_meal_in_plan(user, meal_time, new_meal):
    """Replace a meal in today's active plan."""
    today = timezone.now().date()

    plan = MealPlan.objects.filter(
        user            = user,
        is_active       = True,
        start_date__lte = today,
        end_date__gte   = today,
    ).first()

    if not plan:
        return None

    day_number = (today - plan.start_date).days + 1

    entry, _ = MealPlanEntry.objects.update_or_create(
        meal_plan = plan,
        day       = day_number,
        meal_time = meal_time,
        defaults  = {'meal': new_meal}
    )
    return entry


def get_plan_summary(meal_dict):
    """Calculate total nutrition for a set of meals."""
    total_kcal = total_protein = total_carbs = total_fat = 0
    for meal in meal_dict.values():
        if meal:
            total_kcal    += meal.calories_kcal
            total_protein += meal.protein_g
            total_carbs   += meal.carb_g
            total_fat     += meal.fat_g
    return {
        'total_kcal':    round(total_kcal),
        'total_protein': round(total_protein, 1),
        'total_carbs':   round(total_carbs, 1),
        'total_fat':     round(total_fat, 1),
    }