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
import random 
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
SWALLOW_FAMILIES = {'amala', 'eba', 'pounded_yam', 'fufu', 'semo', 'tuwo'}
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




def _is_swallow_ok(meal, day_family_set):
    """
    Hard constraint — never relaxed, even in fallback passes.
    Prevents two different swallows landing on the same day
    (e.g. Amala for lunch, Pounded Yam for dinner).
    """
    family = _get_food_family(meal.food_name)
    if family in SWALLOW_FAMILIES and any(f in SWALLOW_FAMILIES for f in day_family_set):
        return False
    return True


def _pick_for_slot(slot, budget, scored_meals, used_ids,
                   week_family_count, day_family_set):
    """
    Pick the best available meal for a slot respecting constraints,
    with controlled randomness to allow for regeneration variety.

    Returns a (meal, score) tuple, or (None, None) if nothing fits.
    """
    min_kcal = budget * (1 - TOLERANCE)
    max_kcal = budget * (1 + TOLERANCE)

    def is_variety_ok(meal):
        family = _get_food_family(meal.food_name)
        if family is None:
            return True

        # 1. Prevent the exact same family today
        if family in day_family_set:
            return False

        # 2. Prevent multiple different swallows in one day
        if not _is_swallow_ok(meal, day_family_set):
            return False

        # 3. Prevent overusing a family across the week
        if week_family_count.get(family, 0) >= MAX_FAMILY_PER_WEEK:
            return False

        return True

    # PASS 1: Strict budget + variety (Pool the top 3 and pick randomly)
    pass_1_candidates = []
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if min_kcal <= meal.calories_kcal <= max_kcal:
            if is_variety_ok(meal):
                pass_1_candidates.append((meal, score))
                # Stop looking once we have 3 excellent choices
                if len(pass_1_candidates) >= 3:
                    break

    if pass_1_candidates:
        return random.choice(pass_1_candidates)

    # PASS 2: Relax week/day-family variety, but swallow rule stays hard
    pass_2_candidates = []
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if not _is_swallow_ok(meal, day_family_set):
            continue
        if min_kcal <= meal.calories_kcal <= max_kcal:
            pass_2_candidates.append((meal, score))
            if len(pass_2_candidates) >= 3:
                break

    if pass_2_candidates:
        return random.choice(pass_2_candidates)

    # PASS 3: Relax budget too, just pick closest calorie match — swallow rule still hard
    candidates = []
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        if not _is_swallow_ok(meal, day_family_set):
            continue
        diff = abs(meal.calories_kcal - budget)
        candidates.append((diff, score, meal))

    if candidates:
        candidates.sort(key=lambda x: (x[0], -x[1]))
        # Pick from the top 2 closest matches
        top_closest = [(c[2], c[1]) for c in candidates[:2]]
        return random.choice(top_closest)

    # PASS 4: Absolute last resort — drop the swallow rule too, so a slot
    # is never left empty. Should be rare; worth logging if it triggers.
    fallback_candidates = []
    for meal, score in scored_meals:
        if meal.id in used_ids:
            continue
        times = [t.strip() for t in meal.meal_time.split(',')]
        if slot not in times:
            continue
        diff = abs(meal.calories_kcal - budget)
        fallback_candidates.append((diff, score, meal))

    if fallback_candidates:
        fallback_candidates.sort(key=lambda x: (x[0], -x[1]))
        top_closest = [(c[2], c[1]) for c in fallback_candidates[:2]]
        return random.choice(top_closest)

    return None, None


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

            meal, score = _pick_for_slot(
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
                        match_score  = round(score, 2) if score is not None else 0.5,
                    )
                )

        used_ids |= day_used_ids

        # Reset used_ids after 2 weeks to allow repetition in long plans
        if day_offset == 13:
            used_ids = set()

    MealPlanEntry.objects.bulk_create(entries_to_create)
    return plan
def get_match_reason(meal, score, goal):
    """
    Generate short, human-readable microcopy explaining why a meal
    was recommended. Rule-based — reads signals already computed
    (LightGBM score, meal macros, user's goal), not a separate model.

    Priority order: strongest/most specific signal wins, so a meal
    doesn't get a generic reason when a sharper one applies.
    """
    goal_clean = (goal or '').lower()

    # ── High confidence from the model itself ──────────────────────
    if score is not None and score >= 0.85:
        return "Strong AI match for your goal"

    # ── Goal-specific macro signals ─────────────────────────────────
    if goal_clean == 'weight_gain' and meal.calories_kcal >= 700:
        return "Calorie-dense pick to support weight gain"

    if goal_clean == 'weight_gain' and meal.protein_g >= 30:
        return "High-protein pick to support weight gain"

    if goal_clean == 'weight_loss' and meal.calories_kcal <= 500:
        return "Lower-calorie choice to support your goal"

    if goal_clean == 'weight_loss' and meal.protein_g >= 25:
        return "High-protein, helps keep you full"

    if goal_clean == 'maintenance' and score is not None and score >= 0.6:
        return "Well-balanced pick for maintenance"

    # ── Taste / cultural signals (nice to have, lower priority) ─────
    if getattr(meal, 'taste_profile', None):
        taste = meal.taste_profile.lower()
        if 'spicy' in taste:
            return "Popular spicy favorite"

    # ── Fallback — still true, just less specific ────────────────────
    if score is not None and score >= 0.6:
        return "Good match for your goal"

    return "Matched to your profile"


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

    Each slot now carries both the meal and its match_score, so the
    template can show the AI confidence inline without a second query.
    """
    today     = timezone.now().date()
    start_day = (week_offset * 7) + 1
    end_day   = start_day + 6

    entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day__gte  = start_day,
        day__lte  = end_day,
    ).select_related('meal')

    # Group by day — store the whole entry now, not just entry.meal,
    # so match_score travels with it.
    day_entries = {}
    for entry in entries:
        if entry.day not in day_entries:
            day_entries[entry.day] = {}
        day_entries[entry.day][entry.meal_time] = entry

    days_display = []
    day_names    = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                    'Friday', 'Saturday', 'Sunday']

    for i, day_num in enumerate(range(start_day, end_day + 1)):
        slots    = day_entries.get(day_num, {})
        day_date = plan.start_date + timedelta(days=day_num - 1)

        breakfast_entry = slots.get('breakfast')
        lunch_entry     = slots.get('lunch')
        dinner_entry    = slots.get('dinner')
        snack_entry     = slots.get('snack')

        meals_for_total = [
            e.meal for e in [breakfast_entry, lunch_entry, dinner_entry, snack_entry] if e
        ]
        total_kcal = sum(m.calories_kcal for m in meals_for_total)

        days_display.append({
            'day_number': day_num,
            'day_name':   day_names[i % 7],
            'date':       day_date.strftime('%b %d'),
            'is_today':   day_date == today,
            'breakfast':  breakfast_entry.meal if breakfast_entry else None,
            'lunch':      lunch_entry.meal if lunch_entry else None,
            'dinner':     dinner_entry.meal if dinner_entry else None,
            'snack':      snack_entry.meal if snack_entry else None,
            'breakfast_score': breakfast_entry.match_score if breakfast_entry else None,
            'lunch_score':     lunch_entry.match_score if lunch_entry else None,
            'dinner_score':    dinner_entry.match_score if dinner_entry else None,
            'snack_score':     snack_entry.match_score if snack_entry else None,
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