from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workdocs', '0009_materials'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskmaterial',
            name='is_needed',
            field=models.BooleanField(default=True),
        ),
    ]
