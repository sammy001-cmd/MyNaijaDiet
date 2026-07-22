from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('accounts/login/', views.login_view),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('recommendations/', views.recommendations, name='recommendations'),
    path('meal-plan/', views.meal_plan, name='meal_plan'),
    path('meal-plan/add/<int:meal_id>/', views.add_to_plan, name='add_to_plan'),
    path('meal-plan/remove/<int:entry_id>/', views.remove_meal_entry, name='remove_meal_entry'),
    path('swap/<int:meal_id>/', views.swap_meal, name='swap_meal'),
    path('meal/<int:meal_id>/feedback/', views.submit_meal_feedback, name='submit_meal_feedback'),
    path('profile/', views.profile, name='profile'),
    #as per say we didn't have a meal detail page but we can add it later if we want to show details of a specific meal
    path('meal/<int:meal_id>/', views.meal_detail, name='meal_detail'),
    path('swap/<int:meal_id>/', views.swap_meal, name='swap_meal'),
    # path('meal/', views.meal_detail, name='meal_detail'),
    path('logout/', views.logout_view, name='logout'),


    path('staff/', views.admin_dashboard, name='admin_dashboard'),
    path('staff/meals/', views.meal_management, name='meal_management'),
    path('staff/meals/edit/<int:meal_id>/', views.superuser_edit_meal, name='superuser_edit_meal'),
    path('staff/meals/delete/<int:meal_id>/', views.superuser_delete_meal, name='superuser_delete_meal'),
    path('staff/queue/', views.meal_edit_queue, name='meal_edit_queue'),
    path('staff/propose/new/', views.propose_new_meal, name='propose_new_meal'),
    path('staff/propose/edit/<int:meal_id>/', views.propose_meal_update, name='propose_meal_update'),
    path('staff/propose/delete/<int:meal_id>/', views.propose_meal_delete, name='propose_meal_delete'),
    path('staff/review/', views.review_queue, name='review_queue'),
    path('staff/review/approve/<int:edit_id>/', views.approve_edit, name='approve_edit'),
    path('staff/review/reject/<int:edit_id>/', views.reject_edit, name='reject_edit'),
]