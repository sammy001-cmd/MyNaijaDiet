"""
MyNaijaDiet — Smart Meal Picker v2
====================================
Changes from v1:
- Saves generated plan to MealPlan + MealPlanEntry in DB
- On subsequent loads, retrieves saved plan instead of regenerating
- Swap function replaces a single meal slot and saves back to DB
- Models load from cached ml_engine (loaded once at startup via apps.py)
"""

from datetime import timedelta
from django.utils import timezone
from .models import Meal, MealPlan, MealPlanEntry


# Calorie budget per slot as % of daily target
SLOT_RATIOS = {
    'breakfast': 0.25,
    'lunch':     0.35,
    'dinner':    0.30,
    'snack':     0.10,
}

TOLERANCE = 0.25   # ±25% of slot budget is acceptable


# ────────────────────────────────────────────────────────────────────────────
# INTERNAL: Pick best meal for a slot using ML + calorie budget
# ────────────────────────────────────────────────────────────────────────────

def _pick_meal_for_slot(slot, slot_budget, ranked_meals, excluded_ids):
    """
    From a list of ML-ranked meals, pick the best one that:
    - Is available at this meal time
    - Fits within the calorie budget (±TOLERANCE)
    - Hasn't been picked for another slot already
    """
    min_kcal = slot_budget * (1 - TOLERANCE)
    max_kcal = slot_budget * (1 + TOLERANCE)

    # First pass — strict budget match
    for meal in ranked_meals:
        if meal.id in excluded_ids:
            continue
        meal_times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in meal_times:
            continue
        if min_kcal <= meal.calories_kcal <= max_kcal:
            return meal

    # Second pass — closest calorie match (no budget restriction)
    candidates = []
    for meal in ranked_meals:
        if meal.id in excluded_ids:
            continue
        meal_times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in meal_times:
            continue
        diff = abs(meal.calories_kcal - slot_budget)
        candidates.append((diff, meal))

    if candidates:
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]

    return None


def _get_ranked_meals(goal):
    """
    Get ML-ranked meals for a goal.
    Falls back to DB query if ML is unavailable.
    """
    try:
        from .ml_engine import get_recommendations
        ranked = get_recommendations(
            user_goal      = goal,
            meals_queryset = Meal.objects.filter(goal_suitability=goal),
            top_n          = 80,
        )
        # Add maintenance meals as backup
        backup = list(
            Meal.objects.filter(
                goal_suitability='maintenance'
            ).exclude(
                id__in=[m.id for m in ranked]
            ).order_by('?')[:30]
        )
        return ranked + backup
    except Exception:
        return list(Meal.objects.filter(goal_suitability=goal).order_by('?')[:80])


# ────────────────────────────────────────────────────────────────────────────
# PUBLIC: Get or generate today's meal plan
# ────────────────────────────────────────────────────────────────────────────

def get_or_generate_plan(user, profile):
    """
    Main function called by the dashboard view.

    Returns:
        dict with keys: breakfast, lunch, dinner, snack
        Each value is a Meal instance or None
    """
    today      = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)
    day_number = today.isoweekday()

    # ── Check if today's plan already exists in DB ────────────────────────
    existing_plan = MealPlan.objects.filter(
        user       = user,
        is_active  = True,
        start_date = week_start,
        end_date   = week_end,
    ).first()

    if existing_plan:
        entries = MealPlanEntry.objects.filter(
            meal_plan = existing_plan,
            day       = day_number,
        ).select_related('meal')

        if entries.exists():
            # Plan already generated for today — return it
            plan = {'breakfast': None, 'lunch': None, 'dinner': None, 'snack': None}
            for entry in entries:
                if entry.meal_time in plan:
                    plan[entry.meal_time] = entry.meal
            return plan, existing_plan, day_number

    # ── No plan yet — generate one ────────────────────────────────────────
    active_plan, _ = MealPlan.objects.get_or_create(
        user       = user,
        is_active  = True,
        start_date = week_start,
        end_date   = week_end,
        defaults   = {'plan_name': f'Week of {week_start.strftime("%b %d")}'}
    )

    daily_target  = int(profile.get_daily_calorie_target())
    ranked_meals  = _get_ranked_meals(profile.health_goal)
    excluded_ids  = set()
    plan          = {}

    for slot, ratio in SLOT_RATIOS.items():
        slot_budget = daily_target * ratio
        meal        = _pick_meal_for_slot(slot, slot_budget, ranked_meals, excluded_ids)

        if meal:
            excluded_ids.add(meal.id)
            plan[slot] = meal

            # Save to database
            MealPlanEntry.objects.get_or_create(
                meal_plan = active_plan,
                day       = day_number,
                meal_time = slot,
                defaults  = {'meal': meal}
            )
        else:
            plan[slot] = None

    return plan, active_plan, day_number


# ────────────────────────────────────────────────────────────────────────────
# PUBLIC: Swap one meal slot with a user-chosen meal
# ────────────────────────────────────────────────────────────────────────────

def swap_meal_in_plan(user, meal_time, new_meal):
    """
    Replace a meal in today's active plan with new_meal.
    Called when user clicks "Use for [meal_time]" on recommendations page.
    """
    today      = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)
    day_number = today.isoweekday()

    active_plan = MealPlan.objects.filter(
        user       = user,
        is_active  = True,
        start_date = week_start,
        end_date   = week_end,
    ).first()

    if not active_plan:
        # No plan yet — create one
        active_plan = MealPlan.objects.create(
            user       = user,
            is_active  = True,
            start_date = week_start,
            end_date   = week_end,
            plan_name  = f'Week of {week_start.strftime("%b %d")}',
        )

    # Update or create the entry for this slot
    entry, created = MealPlanEntry.objects.update_or_create(
        meal_plan = active_plan,
        day       = day_number,
        meal_time = meal_time,
        defaults  = {'meal': new_meal}
    )

    return entry


# ────────────────────────────────────────────────────────────────────────────
# PUBLIC: Plan nutrition summary
# ────────────────────────────────────────────────────────────────────────────

def get_plan_summary(meal_plan_dict):
    total_kcal = total_protein = total_carbs = total_fat = 0

    for slot, meal in meal_plan_dict.items():
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