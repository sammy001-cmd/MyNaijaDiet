from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recommender', '0008_add_profile_picture_to_healthprofile'),
    ]

    operations = [
        migrations.RenameField(
            model_name='mealedit',
            old_name='image',
            new_name='proposed_image',
        ),
    ]
