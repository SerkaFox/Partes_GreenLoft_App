from django.db import migrations, models


def migrate_to_status(apps, schema_editor):
    TaskMaterial = apps.get_model('workdocs', 'TaskMaterial')
    for tm in TaskMaterial.objects.all():
        tm.status = 'objeto' if getattr(tm, 'is_gathered', False) else 'falta'
        tm.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('workdocs', '0011_electrical_materials'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskmaterial',
            name='status',
            field=models.CharField(
                max_length=20,
                choices=[('falta', 'Falta'), ('pedido', 'Pedido'), ('almacen', 'En almacén'), ('objeto', 'En obra')],
                default='falta',
            ),
        ),
        migrations.RunPython(migrate_to_status, migrations.RunPython.noop),
        migrations.RemoveField(model_name='taskmaterial', name='is_needed'),
        migrations.RemoveField(model_name='taskmaterial', name='is_gathered'),
    ]
