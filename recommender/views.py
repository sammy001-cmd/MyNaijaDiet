from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required,user_passes_test
from django.contrib import messages
from django.db.models import Avg, Count
from django.utils import timezone
from .models import User, HealthProfile, Meal, MealPlan, MealPlanEntry, Recommendation, MealFeedback, MealFeedback, MealEdit
from .forms import MealEditForm


# ============================================================
# LANDING PAGE
# ============================================================

def landing(request):
    """
    Public landing page.
    If user is already logged in, send them straight to dashboard.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'landing.html')


# ============================================================
# REGISTER
# ============================================================

def register(request):
    """
    Handles new user registration + health profile creation in one step.
    The register template collects: full_name, email, password,
    age, gender, weight, height, activity_level, goal, region.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # --- Pull form data ---
        full_name      = request.POST.get('full_name', '').strip()
        email          = request.POST.get('email', '').strip().lower()
        password       = request.POST.get('password', '')
        age            = request.POST.get('age')
        gender_raw     = request.POST.get('gender', 'M')   # 'M' or 'F' from template
        weight         = request.POST.get('weight')
        height         = request.POST.get('height')
        activity_level = request.POST.get('activity_level', 'sedentary')
        goal           = request.POST.get('goal', 'maintenance')
        region         = request.POST.get('region', 'National')

        # --- Basic validation ---
        if not all([full_name, email, password, age, weight, height]):
            messages.error(request, 'Please fill in all required fields.')
            return render(request, 'register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'An account with this email already exists.')
            return render(request, 'register.html')

        # --- Split full name ---
        name_parts = full_name.split(' ', 1)
        first_name = name_parts[0]
        last_name  = name_parts[1] if len(name_parts) > 1 else ''

        # --- Map gender from template (M/F) to model (male/female) ---
        gender = 'male' if gender_raw.upper() == 'M' else 'female'

        # --- Map goal from template to model choices ---
        goal_map = {
            'weight_loss':  'weight_loss',
            'maintenance':  'maintenance',
            'weight_gain':  'weight_gain',   # template says weight_gain, model uses weight_gain
            
        }
        health_goal = goal_map.get(goal, 'maintenance')

        # --- Map region from template to model choices ---
        region_map = {
            'Yoruba':      'yoruba_southwest',
            'Igbo':        'igbo_southeast',
            'Hausa':       'hausa_north',
            'South-South': 'south_south',
            'National':    'general',
            'Middle Belt': 'general',
        }
        regional_preference = region_map.get(region, 'general')

        # --- Map activity level (template uses 'very', model uses 'very_active') ---
        activity_map = {
            'sedentary': 'sedentary',
            'light':     'light',
            'moderate':  'moderate',
            'active':    'active',
            'very':      'very_active',
        }
        mapped_activity = activity_map.get(activity_level, 'sedentary')

        # --- Create User ---
        try:
            user = User.objects.create_user(
                email      = email,
                password   = password,
                first_name = first_name,
                last_name  = last_name,
            )
        except Exception as e:
            messages.error(request, f'Account creation failed: {str(e)}')
            return render(request, 'register.html')

        # --- Create HealthProfile ---
        try:
            HealthProfile.objects.create(
                user                = user,
                age                 = int(age),
                gender              = gender,
                weight_kg           = float(weight),
                height_cm           = float(height),
                activity_level      = mapped_activity,
                health_goal         = health_goal,
                regional_preference = regional_preference,
            )
        except Exception as e:
            # Profile failed — delete user so we don't leave orphan accounts
            user.delete()
            messages.error(request, f'Profile setup failed: {str(e)}')
            return render(request, 'register.html')

        # --- Log user in and redirect ---
        login(request, user)
        messages.success(request, f'Welcome to MyNaijaDiet, {first_name}!')
        return redirect('dashboard')

    return render(request, 'register.html')


# ============================================================
# LOGIN
# ============================================================

def login_view(request):
    """
    Email + password login with role-based redirects.
    """
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_dashboard')
        return redirect('dashboard')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        user = authenticate(request, username=email, password=password)

        if user is not None:
            login(request, user)

            if user.is_staff or user.is_superuser:
                return redirect('admin_dashboard')

            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid email or password. Please try again.')

    return render(request, 'login.html')


# ============================================================
# LOGOUT
# ============================================================

@login_required
def logout_view(request):
    logout(request)
    return redirect('landing')


# ============================================================
# DASHBOARD
# ============================================================

@login_required
def dashboard(request):
    user = request.user

    try:
        profile = user.health_profile
    except HealthProfile.DoesNotExist:
        messages.warning(request, 'Please complete your health profile first.')
        return redirect('profile')

    # ── Greeting ──────────────────────────────────────────────────────────
    hour = timezone.localtime().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    # ── Calorie + macro targets ───────────────────────────────────────────
    calorie_target = int(profile.get_daily_calorie_target())
    tdee           = int(profile.tdee)

    if profile.health_goal == 'weight_loss':
        p_ratio, c_ratio, f_ratio = 0.35, 0.40, 0.25
    elif profile.health_goal == 'weight_gain':
        p_ratio, c_ratio, f_ratio = 0.35, 0.45, 0.20
    else:
        p_ratio, c_ratio, f_ratio = 0.25, 0.50, 0.25

    macro_protein_target = int((calorie_target * p_ratio) / 4)
    macro_carb_target    = int((calorie_target * c_ratio) / 4)
    macro_fat_target     = int((calorie_target * f_ratio) / 9)
    protein_pct          = int(p_ratio * 100)
    carb_pct             = int(c_ratio * 100)
    fat_pct              = int(f_ratio * 100)
    protein_carb_pct     = protein_pct + carb_pct

    # ── Get or generate weekly plan ───────────────────────────────────────
    from .meal_planner import generate_weekly_plan, get_today_meals, get_match_reason
    from .models import MealPlanEntry

    plan                    = generate_weekly_plan(user, profile, duration='1_week')
    today_meals, day_number = get_today_meals(plan)

    # ── Pull today's entries too, so we get match_score alongside the meal ──
    # (get_today_meals only returns Meal objects — score lives on the entry)
    today_entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day       = day_number,
    ).select_related('meal')

    entry_by_slot = {entry.meal_time: entry for entry in today_entries}

    # ── Build meal_slots list for template ────────────────────────────────
    SLOT_META = [
        {'slot': 'breakfast', 'label': 'Breakfast', 'icon': 'egg_alt'},
        {'slot': 'lunch',     'label': 'Lunch',     'icon': 'set_meal'},
        {'slot': 'dinner',    'label': 'Dinner',    'icon': 'soup_kitchen'},
        {'slot': 'snack',     'label': 'Snack',     'icon': 'bakery_dining'},
    ]

    meal_slots = []
    for meta in SLOT_META:
        meal  = today_meals.get(meta['slot'])
        entry = entry_by_slot.get(meta['slot'])

        match_score  = entry.match_score if entry else None
        match_reason = None
        if meal and match_score is not None:
            match_reason = get_match_reason(meal, match_score, profile.health_goal)

        meal_slots.append({
            'slot':         meta['slot'],
            'label':        meta['label'],
            'icon':         meta['icon'],
            'meal':         meal,
            'match_score':  match_score,
            'match_reason': match_reason,
        })

    # Plan summary totals
    plan_total_kcal    = sum(s['meal'].calories_kcal for s in meal_slots if s['meal'])
    plan_total_protein = round(sum(s['meal'].protein_g for s in meal_slots if s['meal']), 1)

    # ── User initials ─────────────────────────────────────────────────────
    initials = f"{user.first_name[:1]}{user.last_name[:1]}".upper()

    context = {
        'user_name':            user.first_name,
        'user_initials':        initials,
        'greeting':             greeting,
        'profile':              profile,
        'calorie_target':       f'{calorie_target:,}',
        'tdee':                 f'{tdee:,}',
        'bmi_status':           profile.get_bmi_category().upper(),
        'macro_protein_target': macro_protein_target,
        'macro_carb_target':    macro_carb_target,
        'macro_fat_target':     macro_fat_target,
        'protein_pct':          protein_pct,
        'carb_pct':             carb_pct,
        'fat_pct':              fat_pct,
        'protein_carb_pct':     protein_carb_pct,
        'meal_slots':           meal_slots,
        'plan_total_kcal':      plan_total_kcal,
        'plan_total_protein':   plan_total_protein,
        'active_plan':          plan,
    }
    return render(request, 'dashboard.html', context)


@login_required
def meal_plan(request):
    user = request.user

    try:
        profile = user.health_profile
    except HealthProfile.DoesNotExist:
        return redirect('profile')

    from .meal_planner import generate_weekly_plan, get_week_plan_display

    # Handle duration selection
    duration    = request.GET.get('duration', '1_week')
    regenerate  = request.GET.get('regenerate') == 'true'
    week_offset = int(request.GET.get('week', 0))

    plan = generate_weekly_plan(user, profile, duration=duration, regenerate=regenerate)

    if regenerate:
        messages.success(request, 'Your meal plan has been regenerated!')
        return redirect('meal_plan')

    week_days = get_week_plan_display(plan, week_offset=week_offset)

    # Today's entries for the sticky summary bar
    today      = timezone.now().date()
    day_number = (today - plan.start_date).days + 1
    today_entries = MealPlanEntry.objects.filter(
        meal_plan = plan,
        day       = day_number,
    ).select_related('meal')

    calorie_target  = int(profile.get_daily_calorie_target())
    consumed_kcal   = sum(e.meal.calories_kcal for e in today_entries)
    consumed_protein= round(sum(e.meal.protein_g for e in today_entries), 1)
    consumed_carbs  = round(sum(e.meal.carb_g    for e in today_entries), 1)
    consumed_fats   = round(sum(e.meal.fat_g     for e in today_entries), 1)
    progress_pct    = min(int((consumed_kcal / calorie_target) * 100), 100) if calorie_target else 0

    if profile.health_goal == 'weight_loss':
        p_ratio, c_ratio, f_ratio = 0.35, 0.40, 0.25
    elif profile.health_goal == 'weight_gain':
        p_ratio, c_ratio, f_ratio = 0.35, 0.45, 0.20
    else:
        p_ratio, c_ratio, f_ratio = 0.25, 0.50, 0.25

    context = {
        'plan':              plan,
        'week_days':         week_days,
        'week_offset':       week_offset,
        'duration':          duration,
        'today_date':        today.strftime('%A, %B %d, %Y'),
        'calorie_target':    f'{calorie_target:,}',
        'consumed_kcal':     f'{consumed_kcal:,}',
        'progress_pct':      progress_pct,
        'consumed_protein':  consumed_protein,
        'consumed_carbs':    consumed_carbs,
        'consumed_fats':     consumed_fats,
        'target_protein':    int((calorie_target * p_ratio) / 4),
        'target_carbs':      int((calorie_target * c_ratio) / 4),
        'target_fats':       int((calorie_target * f_ratio) / 9),
        'profile':           profile,
    }
    return render(request, 'meal_plan.html', context)


@login_required
def swap_meal(request, meal_id):
    """Replace a meal in today's plan with a user-chosen meal."""
    from .meal_planner import swap_meal_in_plan

    meal      = get_object_or_404(Meal, id=meal_id)
    meal_time = request.GET.get('meal_time', '').strip()

    if not meal_time or meal_time not in ['breakfast', 'lunch', 'dinner', 'snack']:
        messages.error(request, 'Invalid meal time.')
        return redirect('recommendations')

    swap_meal_in_plan(request.user, meal_time, meal)
    messages.success(request, f'Swapped! {meal.food_name} is now your {meal_time}.')
    return redirect('dashboard')

# ============================================================
# RECOMMENDATIONS
# ============================================================

@login_required
def recommendations(request):
    user = request.user

    try:
        profile = user.health_profile
    except HealthProfile.DoesNotExist:
        return redirect('profile')

    meal_time_filter = request.GET.get('meal_time', '').strip()
    region_filter    = request.GET.get('region', '').strip()
    search_query     = request.GET.get('search', '').strip()
    swap_mode        = request.GET.get('swap', '') == 'true'

    meals_qs = Meal.objects.all()

    if meal_time_filter:
        meals_qs = meals_qs.filter(meal_time__icontains=meal_time_filter)
    if region_filter:
        meals_qs = meals_qs.filter(region__icontains=region_filter)
    if search_query:
        meals_qs = meals_qs.filter(food_name__icontains=search_query)

    # ── Scoring — same source as the meal planner, so scores are consistent
    # app-wide rather than coming from two different ranking paths. ─────────
    from .meal_planner import _get_scored_meals, get_match_reason

    try:
        all_scored = _get_scored_meals(profile.health_goal, user=user)
        # Filter scored list down to the queryset's ids, preserving score order
        allowed_ids = set(meals_qs.values_list('id', flat=True))
        scored_filtered = [(m, s) for m, s in all_scored if m.id in allowed_ids]
    except Exception:
        scored_filtered = [(m, 0.5) for m in meals_qs.order_by('food_name')]

    # Attach score + reason directly onto each meal object so the template
    # can read meal.match_score / meal.match_reason without extra plumbing.
    meals = []
    for meal, score in scored_filtered[:100]:
        meal.match_score  = score
        meal.match_reason = get_match_reason(meal, score, profile.health_goal)
        meals.append(meal)

    meal_time_options = [
        {'value': 'breakfast', 'label': 'Breakfast'},
        {'value': 'lunch',     'label': 'Lunch'},
        {'value': 'dinner',    'label': 'Dinner'},
        {'value': 'snack',     'label': 'Snack'},
    ]

    region_options = [
        {'value': 'General',          'label': 'General'},
        {'value': 'Yoruba/Southwest', 'label': 'Yoruba'},
        {'value': 'Southeast/Igbo',   'label': 'Igbo'},
        {'value': 'Hausa/North',      'label': 'Hausa'},
        {'value': 'South-South',      'label': 'South-South'},
    ]

    context = {
        'meals':             meals,
        'active_meal_time':  meal_time_filter,
        'active_region':     region_filter,
        'active_search':     search_query,
        'swap_mode':         swap_mode,
        'meal_time_options': meal_time_options,
        'region_options':    region_options,
        'profile':           profile,
    }

    return render(request, 'recommendations.html', context)


# ============================================================
# MEAL DETAIL
# ============================================================

@login_required
def meal_detail(request, meal_id=None):
    if meal_id:
        meal = get_object_or_404(Meal, id=meal_id)
    else:
        meal = Meal.objects.first()

    if not meal:
        messages.error(request, 'Meal not found.')
        return redirect('recommendations')

    # ── Macro percentages for visual bars ────────────────────────────────
    total_grams = meal.protein_g + meal.carb_g + meal.fat_g
    if total_grams > 0:
        protein_pct = round((meal.protein_g / total_grams) * 100)
        carb_pct    = round((meal.carb_g    / total_grams) * 100)
        fat_pct     = round((meal.fat_g     / total_grams) * 100)
    else:
        protein_pct = carb_pct = fat_pct = 0

    # ── Similar meals ─────────────────────────────────────────────────────
    similar_meals = Meal.objects.filter(
        goal_suitability = meal.goal_suitability,
        diet_type        = meal.diet_type,
    ).exclude(id=meal.id).order_by('?')[:3]

    # ── Feedback ─────────────────────────────────────────────────────────
    existing_feedback = MealFeedback.objects.filter(user=request.user, meal=meal).first()
    feedback_stats = meal.feedbacks.aggregate(avg_rating=Avg('rating'), count=Count('id'))

    context = {
        'meal':              meal,
        'protein_pct':       protein_pct,
        'carb_pct':          carb_pct,
        'fat_pct':           fat_pct,
        'similar_meals':     similar_meals,
        'existing_feedback': existing_feedback,
        'avg_rating':        feedback_stats['avg_rating'],
        'feedback_count':    feedback_stats['count'],
    }

    return render(request, 'meal_detail.html', context)



@login_required
def add_to_plan(request, meal_id):
    """
    Adds a meal to the user's active meal plan for today.
    Called when user clicks the + button on a meal card.
    meal_time is passed as a GET parameter e.g. ?meal_time=lunch
    """
    from datetime import timedelta

    user  = request.user
    today = timezone.now().date()
    meal  = get_object_or_404(Meal, id=meal_id)

    # Determine meal_time — from GET param or infer from meal's available times
    meal_time = request.GET.get('meal_time', '').strip()
    if not meal_time:
        # Pick first available time for this meal
        times     = meal.get_meal_times()
        meal_time = times[0] if times else 'lunch'

    # Get or create this week's plan
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    active_plan, _ = MealPlan.objects.get_or_create(
        user       = user,
        is_active  = True,
        start_date = week_start,
        end_date   = week_end,
        defaults   = {'plan_name': f'Week of {week_start.strftime("%b %d")}'}
    )

    day_number = today.isoweekday()

    # Avoid duplicate entries for same meal on same day and time
    already_exists = MealPlanEntry.objects.filter(
        meal_plan = active_plan,
        meal      = meal,
        day       = day_number,
        meal_time = meal_time,
    ).exists()

    if already_exists:
        messages.info(request, f'{meal.food_name} is already in your {meal_time} plan.')
    else:
        MealPlanEntry.objects.create(
            meal_plan = active_plan,
            meal      = meal,
            day       = day_number,
            meal_time = meal_time,
        )
        messages.success(request, f'{meal.food_name} added to your {meal_time}!')

    # Redirect back to wherever they came from
    next_url = request.GET.get('next', 'meal_plan')
    return redirect(next_url)


@login_required
def remove_meal_entry(request, entry_id):
    """
    Removes a meal entry from the active meal plan.
    """
    entry = get_object_or_404(MealPlanEntry, id=entry_id, meal_plan__user=request.user)
    meal_name = entry.meal.food_name
    entry.delete()
    messages.success(request, f'{meal_name} removed from your plan.')
    return redirect('meal_plan')


# ============================================================
# PROFILE / SETTINGS
# ============================================================

@login_required
def profile(request):
    user = request.user

    profile_obj, created = HealthProfile.objects.get_or_create(
        user=user,
        defaults={
            'age':            25,
            'gender':         'male',
            'weight_kg':      70.0,
            'height_cm':      170.0,
            'activity_level': 'sedentary',
            'health_goal':    'maintenance',
        }
    )

    if request.method == 'POST':
        age            = request.POST.get('age')
        gender_raw     = request.POST.get('gender', 'M')
        weight         = request.POST.get('weight')
        height         = request.POST.get('height')
        activity_level = request.POST.get('activity_level', 'sedentary')
        goal           = request.POST.get('goal', 'maintenance')
        region         = request.POST.get('region', 'general')

        # Gender mapping
        gender = 'male' if gender_raw.upper() == 'M' else 'female'

        # Goal mapping
        goal_map = {
            'weight_loss': 'weight_loss',
            'maintenance': 'maintenance',
            'weight_gain': 'weight_gain',
            'weight_gain': 'weight_gain',
        }

        # Activity level — template now sends exact model values
        activity_map = {
            'sedentary':   'sedentary',
            'light':       'light',
            'moderate':    'moderate',
            'active':      'active',
            'very_active': 'very_active',
            'very':        'very_active',
        }

        # Medical flags — checkboxes only appear in POST if checked
        is_diabetic     = 'is_diabetic'     in request.POST
        is_hypertensive = 'is_hypertensive' in request.POST
        is_vegetarian   = 'is_vegetarian'   in request.POST

        try:
            profile_obj.age                  = int(age)
            profile_obj.gender               = gender
            profile_obj.weight_kg            = float(weight)
            profile_obj.height_cm            = float(height)
            profile_obj.activity_level       = activity_map.get(activity_level, 'sedentary')
            profile_obj.health_goal          = goal_map.get(goal, 'maintenance')
            profile_obj.regional_preference  = region
            profile_obj.is_diabetic          = is_diabetic
            profile_obj.is_hypertensive      = is_hypertensive
            profile_obj.is_vegetarian        = is_vegetarian
            profile_obj.save()   # auto-recalculates BMI, BMR, TDEE

            messages.success(request, 'Profile updated! Your BMI and calorie targets have been recalculated.')
        except Exception as e:
            messages.error(request, f'Update failed: {str(e)}')

        return redirect('profile')

    # ── BMI indicator position (map BMI to 0-100% on the gradient bar) ───
    # Bar spans 15 to 35 BMI range
    bmi = profile_obj.bmi or 22
    bmi_pct = max(0, min(100, int(((bmi - 15) / (35 - 15)) * 100)))

    # BMI message
    bmi_cat = profile_obj.get_bmi_category()
    bmi_messages = {
        'Underweight': 'You are underweight. Consider increasing your calorie intake with nutritious Nigerian meals.',
        'Normal':      'Your BMI is within the healthy range. Keep focusing on balanced local meals!',
        'Overweight':  'You are slightly overweight. Focus on portion control and high-protein Nigerian meals.',
        'Obese':       'Your BMI indicates obesity. A structured meal plan with calorie deficit is recommended.',
    }
    bmi_message = bmi_messages.get(bmi_cat, 'Keep maintaining a healthy lifestyle!')

    # Calorie target
    calorie_target = int(profile_obj.get_daily_calorie_target())

    # User initials
    initials = f"{user.first_name[:1]}{user.last_name[:1]}".upper()

    context = {
        'profile':         profile_obj,
        'user_name':       user.get_full_name(),
        'user_initials':   initials,
        'bmi_value':       profile_obj.bmi,
        'bmi_status':      bmi_cat.upper(),
        'bmi_pct':         bmi_pct,
        'bmi_message':     bmi_message,
        'calorie_target':  f'{calorie_target:,}',
        'current_region':  profile_obj.regional_preference,
    }

    return render(request, 'profile.html', context)


@login_required
def submit_meal_feedback(request, meal_id):
    if request.method != 'POST':
        return redirect('meal_detail', meal_id=meal_id)

    meal = get_object_or_404(Meal, id=meal_id)
    rating = request.POST.get('rating')
    was_cooked = request.POST.get('was_cooked') == 'on'
    comment = request.POST.get('comment', '').strip()

    if not rating:
        messages.error(request, 'Please select a rating before submitting.')
        return redirect('meal_detail', meal_id=meal_id)

    feedback, created = MealFeedback.objects.update_or_create(
        user=request.user,
        meal=meal,
        defaults={
            'rating': int(rating),
            'was_cooked': was_cooked,
            'comment': comment,
        }
    )

    if created:
        messages.success(request, f'Thanks for rating {meal.food_name}!')
    else:
        messages.success(request, f'Your feedback for {meal.food_name} was updated.')

    return redirect('meal_detail', meal_id=meal_id)






def _staff_required(user):
    return user.is_authenticated and user.is_staff


def _superuser_required(user):
    return user.is_authenticated and user.is_superuser


# ── Admin dashboard home ──────────────────────────────────────────────────
@login_required
@user_passes_test(_staff_required)
def admin_dashboard(request):
    context = {
        'active':            'dashboard',
        'total_meals':       Meal.objects.count(),
        'total_users':       User.objects.filter(is_staff=False).count(),
        'pending_count':     MealEdit.objects.filter(status='pending').count(),
        'my_pending':        MealEdit.objects.filter(submitted_by=request.user, status='pending').count(),
        'avg_rating':        MealFeedback.objects.aggregate(avg=Avg('rating'))['avg'],
        'feedback_count':    MealFeedback.objects.count(),
        'recent_proposals':  MealEdit.objects.order_by('-created_at')[:6],
    }
    return render(request, 'staff/admin_dashboard.html', context)


# ── Meal Management — browse all meals with edit/delete/image actions ─────
@login_required
@user_passes_test(_staff_required)
def meal_management(request):
    search = request.GET.get('search', '').strip()
    meals  = Meal.objects.all().order_by('food_name')
    if search:
        meals = meals.filter(food_name__icontains=search)

    context = {
        'meals':         meals,
        'active':        'meals',
        'search':        search,
        'pending_count': MealEdit.objects.filter(status='pending').count(),
    }
    return render(request, 'staff/meal_management.html', context)


# ── Staff: view their own proposal queue ─────────────────────────────────
@login_required
@user_passes_test(_staff_required)
def meal_edit_queue(request):
    my_edits = MealEdit.objects.filter(submitted_by=request.user).order_by('-created_at')
    context = {
        'my_edits':      my_edits,
        'active':        'queue',
        'pending_count': MealEdit.objects.filter(status='pending').count(),
    }
    return render(request, 'staff/meal_edit_queue.html', context)


def _extract_image(cleaned_data):
    """Pull the uploaded image out of form data — it can't go in JSON payload."""
    image = cleaned_data.pop('image', None)
    return cleaned_data, image


# ── Staff: propose a brand new meal ───────────────────────────────────────
@login_required
@user_passes_test(_staff_required)
def propose_new_meal(request):
    if request.method == 'POST':
        form = MealEditForm(request.POST, request.FILES)
        if form.is_valid():
            payload, image = _extract_image(form.cleaned_data)
            MealEdit.objects.create(
                action        = 'create',
                payload       = payload,
                image         = image,
                submitted_by  = request.user,
            )
            messages.success(request, 'New meal proposal submitted for review.')
            return redirect('meal_edit_queue')
    else:
        form = MealEditForm()

    context = {'form': form, 'mode': 'create', 'active': 'queue'}
    return render(request, 'staff/propose_meal_edit.html', context)


# ── Staff: propose an edit to an existing meal ────────────────────────────
@login_required
@user_passes_test(_staff_required)
def propose_meal_update(request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)

    if request.method == 'POST':
        form = MealEditForm(request.POST, request.FILES)
        if form.is_valid():
            payload, image = _extract_image(form.cleaned_data)
            MealEdit.objects.create(
                action        = 'update',
                target_meal   = meal,
                payload       = payload,
                image         = image,
                submitted_by  = request.user,
            )
            messages.success(request, f'Edit proposal for "{meal.food_name}" submitted for review.')
            return redirect('meal_edit_queue')
    else:
        form = MealEditForm(initial={
            'food_name':        meal.food_name,
            'category':         meal.category,
            'region':           meal.region,
            'meal_time':        meal.meal_time,
            'calories_kcal':    meal.calories_kcal,
            'protein_g':        meal.protein_g,
            'carb_g':           meal.carb_g,
            'fat_g':            meal.fat_g,
            'goal_suitability': meal.goal_suitability,
            'diet_type':        meal.diet_type,
            'taste_profile':    meal.taste_profile,
            'prep_time':        meal.prep_time,
            'price_range':      meal.price_range,
        })

    context = {'form': form, 'mode': 'update', 'meal': meal, 'active': 'meals'}
    return render(request, 'staff/propose_meal_edit.html', context)


# ── Staff: propose a deletion ──────────────────────────────────────────────
@login_required
@user_passes_test(_staff_required)
def propose_meal_delete(request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)

    if request.method == 'POST':
        MealEdit.objects.create(
            action        = 'delete',
            target_meal   = meal,
            submitted_by  = request.user,
        )
        messages.success(request, f'Deletion proposal for "{meal.food_name}" submitted for review.')
        return redirect('meal_edit_queue')

    context = {'meal': meal, 'active': 'meals'}
    return render(request, 'staff/confirm_delete_proposal.html', context)


# ── Superuser: instant edit — no approval needed for your own changes ─────
@login_required
@user_passes_test(_superuser_required)
def superuser_edit_meal(request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)

    if request.method == 'POST':
        form = MealEditForm(request.POST, request.FILES)
        if form.is_valid():
            payload, image = _extract_image(form.cleaned_data)
            for field, value in payload.items():
                setattr(meal, field, value)
            if image:
                meal.image = image
            meal.save()
            messages.success(request, f'"{meal.food_name}" updated.')
            return redirect('meal_management')
    else:
        form = MealEditForm(initial={
            'food_name':        meal.food_name,
            'category':         meal.category,
            'region':           meal.region,
            'meal_time':        meal.meal_time,
            'calories_kcal':    meal.calories_kcal,
            'protein_g':        meal.protein_g,
            'carb_g':           meal.carb_g,
            'fat_g':            meal.fat_g,
            'goal_suitability': meal.goal_suitability,
            'diet_type':        meal.diet_type,
            'taste_profile':    meal.taste_profile,
            'prep_time':        meal.prep_time,
            'price_range':      meal.price_range,
        })

    context = {'form': form, 'mode': 'update', 'meal': meal, 'active': 'meals', 'instant': True}
    return render(request, 'staff/propose_meal_edit.html', context)


# ── Superuser: instant delete ──────────────────────────────────────────────
@login_required
@user_passes_test(_superuser_required)
def superuser_delete_meal(request, meal_id):
    meal = get_object_or_404(Meal, id=meal_id)
    if request.method == 'POST':
        name = meal.food_name
        meal.delete()
        messages.success(request, f'"{name}" deleted.')
    return redirect('meal_management')


# ── Superadmin: review queue ──────────────────────────────────────────────
@login_required
@user_passes_test(_superuser_required)
def review_queue(request):
    pending  = MealEdit.objects.filter(status='pending').order_by('created_at')
    recent   = MealEdit.objects.exclude(status='pending').order_by('-reviewed_at')[:20]
    context  = {
        'pending':        pending,
        'recent':         recent,
        'active':         'review',
        'pending_count':  pending.count(),
    }
    return render(request, 'staff/review_queue.html', context)


# ── Superadmin: approve one proposal ──────────────────────────────────────
@login_required
@user_passes_test(_superuser_required)
def approve_edit(request, edit_id):
    edit = get_object_or_404(MealEdit, id=edit_id, status='pending')
    if request.method == 'POST':
        try:
            edit.apply(reviewer=request.user)
            messages.success(request, 'Change approved and applied to the live dataset.')
        except Exception as e:
            messages.error(request, f'Failed to apply change: {e}')
    return redirect('review_queue')


# ── Superadmin: reject one proposal ───────────────────────────────────────
@login_required
@user_passes_test(_superuser_required)
def reject_edit(request, edit_id):
    edit = get_object_or_404(MealEdit, id=edit_id, status='pending')
    if request.method == 'POST':
        notes = request.POST.get('notes', '')
        edit.reject(reviewer=request.user, notes=notes)
        messages.warning(request, 'Proposal rejected.')
    return redirect('review_queue')