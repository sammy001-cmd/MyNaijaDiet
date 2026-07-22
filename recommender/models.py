from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


# ============================================================
# CUSTOM USER MANAGER
# ============================================================

class UserManager(BaseUserManager):

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email address is required")
        email = self.normalize_email(email)
        user  = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff",     True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active",    True)
        return self.create_user(email, password, **extra_fields)


# ============================================================
# USER MODEL
# ============================================================

class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model — email is the login identifier,
    not username.
    """
    email       = models.EmailField(unique=True)
    first_name  = models.CharField(max_length=50)
    last_name   = models.CharField(max_length=50)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"


# ============================================================
# HEALTH PROFILE
# ============================================================

class HealthProfile(models.Model):

    GENDER_CHOICES = [
        ("male",   "Male"),
        ("female", "Female"),
    ]

    ACTIVITY_CHOICES = [
        ("sedentary",   "Sedentary (little or no exercise)"),
        ("light",       "Light (1-3 days/week)"),
        ("moderate",    "Moderate (3-5 days/week)"),
        ("active",      "Active (6-7 days/week)"),
        ("very_active", "Very Active (hard exercise daily)"),
    ]

    GOAL_CHOICES = [
        ("weight_loss",   "Lose Weight"),
        ("weight_gain",   "Gain Weight"),
        ("maintenance",   "Maintain Weight"),
    ]

    REGION_CHOICES = [
        ("general",          "General (No Preference)"),
        ("yoruba_southwest", "Yoruba / Southwest"),
        ("igbo_southeast",   "Igbo / Southeast"),
        ("hausa_north",      "Hausa / North"),
        ("south_south",      "South-South"),
    ]

    user               = models.OneToOneField(User, on_delete=models.CASCADE, related_name="health_profile")
    age                = models.PositiveIntegerField(validators=[MinValueValidator(10), MaxValueValidator(100)])
    gender             = models.CharField(max_length=10, choices=GENDER_CHOICES)
    weight_kg          = models.FloatField(validators=[MinValueValidator(20), MaxValueValidator(300)])
    height_cm          = models.FloatField(validators=[MinValueValidator(50), MaxValueValidator(250)])
    activity_level     = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, default="sedentary")
    health_goal        = models.CharField(max_length=20, choices=GOAL_CHOICES, default="maintenance")
    regional_preference = models.CharField(max_length=30, choices=REGION_CHOICES, default="general")

    # Medical flags
    is_diabetic       = models.BooleanField(default=False)
    is_hypertensive   = models.BooleanField(default=False)
    is_vegetarian     = models.BooleanField(default=False)

    # Auto-calculated fields (set on save)
    bmi  = models.FloatField(blank=True, null=True)
    bmr  = models.FloatField(blank=True, null=True)
    tdee = models.FloatField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Health Profile"
        verbose_name_plural = "Health Profiles"

    def calculate_bmi(self):
        """BMI = weight(kg) / height(m)^2"""
        height_m = self.height_cm / 100
        return round(self.weight_kg / (height_m ** 2), 2)

    def calculate_bmr(self):
        """
        Mifflin-St Jeor Equation:
        Male:   (10 × weight) + (6.25 × height) − (5 × age) + 5
        Female: (10 × weight) + (6.25 × height) − (5 × age) − 161
        """
        bmr = (10 * self.weight_kg) + (6.25 * self.height_cm) - (5 * self.age)
        if self.gender == "male":
            bmr += 5
        else:
            bmr -= 161
        return round(bmr, 2)

    def calculate_tdee(self):
        """TDEE = BMR × activity multiplier"""
        multipliers = {
            "sedentary":   1.2,
            "light":       1.375,
            "moderate":    1.55,
            "active":      1.725,
            "very_active": 1.9,
        }
        multiplier = multipliers.get(self.activity_level, 1.2)
        return round(self.bmr * multiplier, 2)

    def save(self, *args, **kwargs):
        """Auto-calculate BMI, BMR, TDEE before saving."""
        self.bmi  = self.calculate_bmi()
        self.bmr  = self.calculate_bmr()
        self.tdee = self.calculate_tdee()
        super().save(*args, **kwargs)

    def get_bmi_category(self):
        if self.bmi is None:
            return "Unknown"
        if self.bmi < 18.5:
            return "Underweight"
        elif self.bmi < 25:
            return "Normal"
        elif self.bmi < 30:
            return "Overweight"
        else:
            return "Obese"

    def get_daily_calorie_target(self):
        """
        Adjust TDEE based on health goal:
        - Weight loss:  TDEE - 500 kcal
        - Muscle gain:  TDEE + 300 kcal
        - Maintenance:  TDEE
        """
        if self.health_goal == "weight_loss":
            return round(self.tdee - 500, 0)
        elif self.health_goal == "weight_gain":
            return round(self.tdee + 300, 0)
        return round(self.tdee, 0)

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.health_goal} ({self.bmi} BMI)"


# ============================================================
# MEAL
# ============================================================

class Meal(models.Model):

    CATEGORY_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch",     "Lunch"),
        ("dinner",    "Dinner"),
        ("snack",     "Snack"),
    ]

    REGION_CHOICES = [
        ("General",           "General"),
        ("Yoruba/Southwest",  "Yoruba / Southwest"),
        ("Southeast/Igbo",    "Southeast / Igbo"),
        ("Hausa/North",       "Hausa / North"),
        ("South-South",       "South-South"),
    ]

    GOAL_CHOICES = [
        ("weight_loss",  "Weight Loss"),
        ("weight_gain",  "Weight Gain"),
        ("maintenance",  "Maintenance"),
        ("all",          "All Goals"),
    ]

    DIET_TYPE_CHOICES = [
        ("balanced",     "Balanced"),
        ("high-protein", "High Protein"),
        ("low-calorie",  "Low Calorie"),
        ("energy-rich",  "Energy Rich"),
        ("vegetarian",   "Vegetarian"),
        ("indulgent",    "Indulgent"),
    ]

    PREP_TIME_CHOICES = [
        ("short",  "Short (< 20 mins)"),
        ("medium", "Medium (20-45 mins)"),
        ("long",   "Long (> 45 mins)"),
    ]

    PRICE_CHOICES = [
        ("low",    "Low (₦0 - ₦1,000)"),
        ("medium", "Medium (₦1,000 - ₦3,000)"),
        ("high",   "High (₦3,000+)"),
    ]

    food_name        = models.CharField(max_length=200, unique=True)
    category         = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    region           = models.CharField(max_length=50, choices=REGION_CHOICES, default="General")
    meal_time        = models.CharField(max_length=100, help_text="Comma-separated: breakfast,lunch,dinner,snack")

    # Nutrition (real kcal values — not labels)
    calories_kcal    = models.PositiveIntegerField()
    protein_g        = models.FloatField()
    carb_g           = models.FloatField()
    fat_g            = models.FloatField()

    # ML features
    goal_suitability = models.CharField(max_length=20, choices=GOAL_CHOICES)
    diet_type        = models.CharField(max_length=20, choices=DIET_TYPE_CHOICES)
    taste_profile    = models.CharField(max_length=100)
    prep_time        = models.CharField(max_length=10, choices=PREP_TIME_CHOICES)
    price_range      = models.CharField(max_length=10, choices=PRICE_CHOICES)

    # Metadata
    image            = models.ImageField(upload_to="meal_images/", blank=True, null=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Meal"
        verbose_name_plural = "Meals"
        ordering            = ["food_name"]
        
        
    @property
    def name(self):
        return self.food_name

    @property
    def calories(self):
        return self.calories_kcal

    @property
    def carbs(self):
        return self.carb_g

    @property
    def protein(self):
        return self.protein_g

    @property
    def fat(self):
        return self.fat_g

    @property
    def meal_type(self):
        return self.category.upper()

    @property
    def get_display_image(self):
        if self.image and hasattr(self.image, 'url'):
            return self.image.url
        return ''

    def __str__(self):
        return f"{self.food_name} ({self.calories_kcal} kcal)"

    def get_meal_times(self):
        """Returns meal_time as a Python list."""
        return [t.strip() for t in self.meal_time.split(",")]

    def is_suitable_for_goal(self, goal):
        return self.goal_suitability == goal or self.goal_suitability == "all"


# ============================================================
# MEAL PLAN
# ============================================================

class MealPlan(models.Model):

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meal_plans")
    plan_name  = models.CharField(max_length=100, default="My Meal Plan")
    start_date = models.DateField()
    end_date   = models.DateField()
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Meal Plan"
        verbose_name_plural = "Meal Plans"
        ordering            = ["-created_at"]

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.plan_name}"

    def get_total_calories(self):
        return sum(entry.actual_calories for entry in self.entries.all())


# ============================================================
# MEAL PLAN ENTRY
# ============================================================

class MealPlanEntry(models.Model):

    DAY_CHOICES = [
        (1, "Monday"),
        (2, "Tuesday"),
        (3, "Wednesday"),
        (4, "Thursday"),
        (5, "Friday"),
        (6, "Saturday"),
        (7, "Sunday"),
    ]

    MEAL_TIME_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch",     "Lunch"),
        ("dinner",    "Dinner"),
        ("snack",     "Snack"),
    ]

    meal_plan       = models.ForeignKey(MealPlan, on_delete=models.CASCADE, related_name="entries")
    meal            = models.ForeignKey(Meal, on_delete=models.CASCADE)
    day             = models.IntegerField(choices=DAY_CHOICES)
    meal_time       = models.CharField(max_length=20, choices=MEAL_TIME_CHOICES)
    portion_size    = models.FloatField(default=1.0, help_text="1.0 = standard serving")
    actual_calories = models.PositiveIntegerField(blank=True, null=True)
    match_score     = models.FloatField(default=0.5, help_text="LightGBM prediction score at time of planning, 0-1")

    class Meta:
        verbose_name        = "Meal Plan Entry"
        verbose_name_plural = "Meal Plan Entries"
        ordering            = ["day", "meal_time"]

    def save(self, *args, **kwargs):
        """Auto-calculate actual calories based on portion size."""
        self.actual_calories = round(self.meal.calories_kcal * self.portion_size)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_day_display()} {self.meal_time} — {self.meal.food_name}"


# ============================================================
# RECOMMENDATION
# ============================================================

class Recommendation(models.Model):

    ML_MODEL_CHOICES = [
        ("random_forest", "Random Forest"),
        ("lightgbm",      "LightGBM"),
        ("ann",           "ANN (Neural Network)"),
        ("lstm",          "LSTM"),
        ("ensemble",      "Ensemble"),
    ]

    user           = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recommendations")
    meal           = models.ForeignKey(Meal, on_delete=models.CASCADE)
    ml_model_used  = models.CharField(max_length=20, choices=ML_MODEL_CHOICES)
    score          = models.FloatField(help_text="Recommendation confidence score (0.0 - 1.0)")
    ensemble_score = models.FloatField(blank=True, null=True, help_text="Combined score from all models")
    rank           = models.PositiveIntegerField(help_text="1 = top recommendation")
    was_accepted   = models.BooleanField(default=False, help_text="Did the user act on this recommendation?")
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Recommendation"
        verbose_name_plural = "Recommendations"
        ordering            = ["-created_at", "rank"]

    def __str__(self):
        return f"{self.user.get_full_name()} — {self.meal.food_name} (rank {self.rank}, {self.ml_model_used})"


# ============================================================
# MEAL FEEDBACK
# ============================================================

class MealFeedback(models.Model):

    RATING_CHOICES = [
        (1, "1 - Didn't like it"),
        (2, "2 - It was okay"),
        (3, "3 - Good"),
        (4, "4 - Really good"),
        (5, "5 - Loved it"),
    ]

    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="feedbacks")
    meal       = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name="feedbacks")
    rating     = models.PositiveIntegerField(choices=RATING_CHOICES)
    was_cooked = models.BooleanField(default=False, help_text="Did the user cook this at home?")
    comment    = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Meal Feedback"
        verbose_name_plural = "Meal Feedbacks"
        ordering            = ["-created_at"]
        # One feedback per user per meal
        unique_together     = ("user", "meal")

    def __str__(self):
        return f"{self.user.get_full_name()} rated {self.meal.food_name} — {self.rating}/5"
    



class MealEdit(models.Model):
    """
    A staff-proposed change to the Meal dataset. Nothing here touches
    the live Meal table until a superadmin approves it.
    """

    ACTION_CHOICES = [
        ('create', 'Add New Meal'),
        ('update', 'Edit Existing Meal'),
        ('delete', 'Delete Meal'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    target_meal = models.ForeignKey(
        'Meal',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pending_edits',
        help_text="The meal being edited/deleted. Blank for new meal proposals."
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        help_text="Proposed field values, e.g. {'food_name': 'Jollof Rice', 'calories_kcal': 620, ...}"
    )
    image = models.ImageField(
        upload_to='meal_edit_uploads/',
        blank=True,
        null=True,
        help_text="Proposed image, applied to the meal on approval."
    )

    submitted_by = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='submitted_edits'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_edits'
    )
    reviewer_notes = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Meal Edit Proposal"
        verbose_name_plural = "Meal Edit Proposals"
        ordering = ["-created_at"]

    def __str__(self):
        target = self.target_meal.food_name if self.target_meal else self.payload.get('food_name', 'New Meal')
        return f"[{self.get_status_display()}] {self.get_action_display()} — {target}"

    def apply(self, reviewer):
        """
        Applies the proposed change to the live Meal table.
        Called only when a superadmin approves.
        """
        from .models import Meal  # local import avoids circular import at module load

        if self.action == 'create':
            meal = Meal.objects.create(**self.payload)
            if self.image:
                meal.image = self.image
                meal.save()

        elif self.action == 'update' and self.target_meal:
            for field, value in self.payload.items():
                setattr(self.target_meal, field, value)
            if self.image:
                self.target_meal.image = self.image
            self.target_meal.save()

        elif self.action == 'delete' and self.target_meal:
            self.target_meal.delete()

        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer, notes=''):
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewer_notes = notes
        self.reviewed_at = timezone.now()
        self.save()