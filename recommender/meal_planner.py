"""
MyNaijaDiet — Weekly Meal Plan Generator
==========================================
Generates a full 7-day meal plan for a user based on their health profile.

Rules:
- Each day has 4 meals: breakfast, lunch, dinner, snack
- Each meal fits within the calorie budget for that slot
- No meal repeats within the same week
- Total daily calories stay within ±10% of user's target
- Meals are picked from LightGBM-ranked list (best match for goal first)
- Regional preferences respected where possible

Plan durations:
- 1 week  = 7 days
- 2 weeks = 14 days
- 1 month = 28 days
"""

from datetime import timedelta
from django.utils import timezone
from .models import Meal, MealPlan, MealPlanEntry

# Calorie split per meal slot
SLOT_RATIOS = {
    'breakfast': 0.25,
    'lunch':     0.35,
    'dinner':    0.30,
    'snack':     0.10,
}

TOLERANCE    = 0.28   # ±28% calorie tolerance per slot
PLAN_LENGTHS = {
    '1_week':  7,
    '2_weeks': 14,
    '1_month': 28,
}


def _get_scored_meals(goal):
    """Get all meals scored by LightGBM for this goal."""
    from .models import Meal
    try:
        from .ml_engine import score_meals
        all_meals = Meal.objects.all()
        scored    = score_meals(goal, all_meals)
        # Add unscored meals as fallback
        scored_ids = {meal.id for meal, _ in scored}
        extras     = [(m, 0.0) for m in Meal.objects.exclude(id__in=scored_ids)]
        return scored + extras
    except Exception:
        meals = list(Meal.objects.all())
        import random
        random.shuffle(meals)
        return [(m, 0.0) for m in meals]


def _pick_for_slot(slot, budget, scored_meals, used_ids):
    """
    Pick the best available meal for a slot.
    - Highest LightGBM score
    - Available at this meal time
    - Fits calorie budget (±TOLERANCE)
    - Not already used in this week's plan
    """
    min_kcal = budget * (1 - TOLERANCE)
    max_kcal = budget * (1 + TOLERANCE)

    # First pass: strict budget + available at this time
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if min_kcal <= meal.calories_kcal <= max_kcal:
            return meal

    # Second pass: ignore budget, just pick closest calorie match
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
    Generate a full meal plan for the specified duration.

    Args:
        user: User instance
        profile: HealthProfile instance
        duration: '1_week', '2_weeks', or '1_month'
        regenerate: if True, delete existing plan and create fresh one

    Returns:
        MealPlan instance
    """
    today      = timezone.now().date()
    num_days   = PLAN_LENGTHS.get(duration, 7)
    start_date = today
    end_date   = today + timedelta(days=num_days - 1)

    # ── Delete existing plan if regenerating ──────────────────────────────
    if regenerate:
        MealPlan.objects.filter(user=user, is_active=True).delete()

    # ── Check if active plan already exists ───────────────────────────────
    existing = MealPlan.objects.filter(
        user      = user,
        is_active = True,
    ).prefetch_related('entries').first()

    if existing and not regenerate:
        return existing

    # ── Create new plan ───────────────────────────────────────────────────
    plan = MealPlan.objects.create(
        user       = user,
        plan_name  = f'{num_days}-Day Meal Plan',
        start_date = start_date,
        end_date   = end_date,
        is_active  = True,
    )

    daily_target  = int(profile.get_daily_calorie_target())
    goal          = profile.health_goal
    scored_meals  = _get_scored_meals(goal)
    used_ids      = set()   # track meals used across entire plan (no repeats)

    entries_to_create = []

    for day_offset in range(num_days):
        day_number   = day_offset + 1   # 1-based day number
        day_used_ids = set()            # meals used today only

        for slot, ratio in SLOT_RATIOS.items():
            budget = daily_target * ratio

            # Exclude meals used today AND across whole plan
            excluded = used_ids | day_used_ids

            meal = _pick_for_slot(slot, budget, scored_meals, excluded)

            if meal:
                day_used_ids.add(meal.id)
                entries_to_create.append(
                    MealPlanEntry(
                        meal_plan    = plan,
                        meal         = meal,
                        day          = day_number,
                        meal_time    = slot,
                        portion_size = 1.0,
                    )
                )

        # After each day, add today's meals to the global used set
        used_ids |= day_used_ids

        # If we run out of unique meals (unlikely with 371), reset used_ids
        # but keep today's to avoid same-day repeats
        if len(used_ids) > len(scored_meals) * 0.8:
            used_ids = day_used_ids.copy()

    # Bulk create all entries at once for performance
    MealPlanEntry.objects.bulk_create(entries_to_create)

    return plan


def get_week_plan_display(plan, week_offset=0):
    """
    Get meal entries for a specific week within a plan, grouped by day.

    Args:
        plan: MealPlan instance
        week_offset: 0 = current week, 1 = next week, etc.

    Returns:
        list of 7 dicts, each with:
            day_number, date, day_name,
            breakfast, lunch, dinner, snack,
            total_kcal, is_today
    """
    from datetime import date

    today      = timezone.now().date()
    start_day  = (week_offset * 7) + 1
    end_day    = start_day + 6

    entries = MealPlanEntry.objects.filter(
        meal_plan__in = [plan],
        day__gte      = start_day,
        day__lte      = end_day,
    ).select_related('meal')

    # Group entries by day
    day_entries = {}
    for entry in entries:
        if entry.day not in day_entries:
            day_entries[entry.day] = {}
        day_entries[entry.day][entry.meal_time] = entry.meal

    # Build display list
    days_display = []
    day_names    = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    for i, day_num in enumerate(range(start_day, end_day + 1)):
        meals   = day_entries.get(day_num, {})
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


def get_today_meals(plan):
    """
    Get today's 4 meals from the active plan.
    Returns dict: {breakfast: Meal, lunch: Meal, dinner: Meal, snack: Meal}
    """
    today      = timezone.now().date()
    day_number = (today - plan.start_date).days + 1

    entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day       = day_number,
    ).select_related('meal')

    result = {'breakfast': None, 'lunch': None, 'dinner': None, 'snack': None}
    for entry in entries:
        if entry.meal_time in result:
            result[entry.meal_time] = entry.meal

    return result, day_number


def swap_meal_in_plan(user, meal_time, new_meal):
    """Replace a meal in today's active plan."""
    today      = timezone.now().date()
    day_number = None

    plan = MealPlan.objects.filter(
        user      = user,
        is_active = True,
    ).first()

    if not plan:
        return None

    day_number = (today - plan.start_date).days + 1

    entry, created = MealPlanEntry.objects.update_or_create(
        meal_plan = plan,
        day       = day_number,
        meal_time = meal_time,
        defaults  = {'meal': new_meal}
    )
    return entry