from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('workdocs', '0012_taskmaterial_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskWorkerReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField(auto_now_add=True)),
                ('jornada', models.CharField(choices=[('normal', 'Normal (1h pausa comida)'), ('intensiva', 'Intensiva (sin pausa)')], default='normal', max_length=20)),
                ('gastos_comida', models.DecimalField(decimal_places=2, default=0, max_digits=6)),
                ('hora_comida', models.TimeField(blank=True, null=True)),
                ('entrada_obra', models.TimeField(blank=True, null=True)),
                ('salida_obra', models.TimeField(blank=True, null=True)),
                ('trabajos_realizados', models.TextField(blank=True)),
                ('is_finished', models.BooleanField(default=False)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='worker_reports', to='workdocs.task')),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='task_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Informe de jornada',
                'verbose_name_plural': 'Informes de jornada',
                'ordering': ['-created_at'],
                'unique_together': {('task', 'worker', 'date')},
            },
        ),
    ]
