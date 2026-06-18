from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from partes.models import ParteTrabajoFoto


class Command(BaseCommand):
    help = 'Elimina fotos de partes más antiguas que retention-days.'

    def add_arguments(self, parser):
        parser.add_argument('--retention-days', type=int, default=7)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options['retention_days'])
        qs = ParteTrabajoFoto.objects.filter(created_at__lt=cutoff)
        count = qs.count()
        deleted_files = 0
        for foto in qs.iterator():
            path = Path(foto.image.path) if foto.image else None
            if path and path.exists():
                if not options['dry_run']:
                    path.unlink()
                deleted_files += 1
            if not options['dry_run']:
                foto.delete()
        action = 'Se eliminarían' if options['dry_run'] else 'Eliminadas'
        self.stdout.write(f'{action} {count} fotos antiguas; archivos: {deleted_files}.')
