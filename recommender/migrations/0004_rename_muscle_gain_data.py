from django.db import migrations


def rename_forward(apps, schema_editor):
    HealthProfile = apps.get_model('recommender', 'HealthProfile')
    Meal = apps.get_model('recommender', 'Meal')
    HealthProfile.objects.filter(health_goal='muscle_gain').update(health_goal='weight_gain')
    Meal.objects.filter(goal_suitability='muscle_gain').update(goal_suitability='weight_gain')


def rename_backward(apps, schema_editor):
    HealthProfile = apps.get_model('recommender', 'HealthProfile')
    Meal = apps.get_model('recommender', 'Meal')
    HealthProfile.objects.filter(health_goal='weight_gain').update(health_goal='muscle_gain')
    Meal.objects.filter(goal_suitability='weight_gain').update(goal_suitability='muscle_gain')


class Migration(migrations.Migration):

    dependencies = [
        ("recommender", "0003_alter_healthprofile_health_goal_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_forward, rename_backward),
    ]