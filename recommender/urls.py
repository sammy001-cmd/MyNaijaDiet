from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('meal-plan/', views.meal_plan, name='meal_plan'),
    path('meal-plan/add/<int:meal_id>/', views.add_to_plan, name='add_to_plan'),
    path('meal-plan/remove/<int:entry_id>/', views.remove_meal_entry, name='remove_meal_entry'),
    path('swap/<int:meal_id>/', views.swap_meal, name='swap_meal'),
    path('profile/', views.profile, name='profile'),
    #as per say we didn't have a meal detail page but we can add it later if we want to show details of a specific meal
    path('meal/<int:meal_id>/', views.meal_detail, name='meal_detail'),
    path('swap/<int:meal_id>/', views.swap_meal, name='swap_meal'),
    # path('meal/', views.meal_detail, name='meal_detail'),
    path('logout/', views.logout_view, name='logout'),
]