from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User,
    HealthProfile,
    Meal,
    MealPlan,
    MealPlanEntry,
    Recommendation,
    MealFeedback,
)


# ============================================================
# USER ADMIN
# ============================================================

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Custom User admin. Extends Django's built-in UserAdmin
    so password hashing and permission management still work.
    """
    list_display  = ("email", "first_name", "last_name", "is_staff", "is_active", "date_joined")
    list_filter   = ("is_staff", "is_active")
    search_fields = ("email", "first_name", "last_name")
    ordering      = ("-date_joined",)

    readonly_fields = ("date_joined",)

    fieldsets = (
        (None,               {"fields": ("email", "password")}),
        ("Personal Info",    {"fields": ("first_name", "last_name")}),
        ("Permissions",      {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important Dates",  {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "password1", "password2", "is_staff", "is_active"),
        }),
    )


# ============================================================
# HEALTH PROFILE ADMIN
# ============================================================

@admin.register(HealthProfile)
class HealthProfileAdmin(admin.ModelAdmin):
    list_display  = (
        "user", "age", "gender", "health_goal",
        "activity_level", "bmi", "bmr", "tdee",
        "regional_preference", "created_at",
    )
    list_filter   = ("health_goal", "activity_level", "gender", "regional_preference")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    ordering      = ("-created_at",)
    readonly_fields = ("bmi", "bmr", "tdee", "created_at", "updated_at")

    fieldsets = (
        ("User",            {"fields": ("user",)}),
        ("Body Metrics",    {"fields": ("age", "gender", "weight_kg", "height_cm", "bmi", "bmr", "tdee")}),
        ("Lifestyle",       {"fields": ("activity_level", "health_goal", "regional_preference")}),
        ("Medical Flags",   {"fields": ("is_diabetic", "is_hypertensive", "is_vegetarian")}),
        ("Timestamps",      {"fields": ("created_at", "updated_at")}),
    )


# ============================================================
# MEAL ADMIN — direct edits locked to superuser only.
# Staff propose changes through MealEdit below instead.
# ============================================================

@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display  = (
        "food_name", "category", "region", "meal_time",
        "calories_kcal", "protein_g", "carb_g", "fat_g",
        "goal_suitability", "diet_type", "price_range",
    )
    list_filter   = (
        "category", "region", "meal_time",
        "goal_suitability", "diet_type", "price_range", "prep_time",
    )
    search_fields = ("food_name", "region", "taste_profile")
    ordering      = ("food_name",)

    fieldsets = (
        ("Identity",     {"fields": ("food_name", "category", "region", "meal_time")}),
        ("Nutrition",    {"fields": ("calories_kcal", "protein_g", "carb_g", "fat_g")}),
        ("Suitability",  {"fields": ("goal_suitability", "diet_type")}),
        ("Details",      {"fields": ("taste_profile", "prep_time", "price_range")}),
    )

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ============================================================
# MEAL PLAN ADMIN
# ============================================================

class MealPlanEntryInline(admin.TabularInline):
    model  = MealPlanEntry
    extra  = 0
    fields = ("day", "meal_time", "meal", "portion_size", "actual_calories", "match_score")
    readonly_fields = ("actual_calories",)


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display  = ("user", "plan_name", "start_date", "end_date", "is_active", "created_at")
    list_filter   = ("is_active",)
    search_fields = ("user__email", "plan_name")
    ordering      = ("-created_at",)
    inlines       = [MealPlanEntryInline]

    fieldsets = (
        ("Plan Info",   {"fields": ("user", "plan_name", "is_active")}),
        ("Duration",    {"fields": ("start_date", "end_date")}),
        ("Timestamps",  {"fields": ("created_at",)}),
    )
    readonly_fields = ("created_at",)


@admin.register(MealPlanEntry)
class MealPlanEntryAdmin(admin.ModelAdmin):
    list_display  = ("meal_plan", "day", "meal_time", "meal", "portion_size", "actual_calories", "match_score")
    list_filter   = ("day", "meal_time")
    search_fields = ("meal_plan__plan_name", "meal__food_name")
    ordering      = ("meal_plan", "day", "meal_time")
    readonly_fields = ("actual_calories",)


# ============================================================
# RECOMMENDATION ADMIN
# ============================================================

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display  = (
        "user", "meal", "ml_model_used",
        "score", "rank", "was_accepted", "created_at",
    )
    list_filter   = ("ml_model_used", "was_accepted")
    search_fields = ("user__email", "meal__food_name")
    ordering      = ("-created_at", "rank")
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Recommendation",  {"fields": ("user", "meal", "ml_model_used")}),
        ("ML Output",       {"fields": ("score", "rank", "ensemble_score")}),
        ("User Response",   {"fields": ("was_accepted",)}),
        ("Timestamps",      {"fields": ("created_at",)}),
    )


# ============================================================
# MEAL FEEDBACK ADMIN
# ============================================================

@admin.register(MealFeedback)
class MealFeedbackAdmin(admin.ModelAdmin):
    list_display  = ("user", "meal", "rating", "was_cooked", "created_at")
    list_filter   = ("rating", "was_cooked")
    search_fields = ("user__email", "meal__food_name", "comment")
    ordering      = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Feedback",     {"fields": ("user", "meal", "rating", "was_cooked")}),
        ("Comment",      {"fields": ("comment",)}),
        ("Timestamps",   {"fields": ("created_at",)}),
    )


# ============================================================
# ADMIN SITE BRANDING
# ============================================================
admin.site.site_header  = "MyNaijaDiet Administration"
admin.site.site_title   = "MyNaijaDiet Admin"
admin.site.index_title  = "Dashboard"