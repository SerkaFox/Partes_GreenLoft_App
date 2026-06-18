from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from partes.models import Tecnico
from workdocs.models import UserProfile


class Command(BaseCommand):
    help = 'Prepara usuarios de trabajo para admin y técnicos existentes.'

    def add_arguments(self, parser):
        parser.add_argument('--password', default='111')
        parser.add_argument('--reset-technician-passwords', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        password = options['password']

        admin, _ = User.objects.update_or_create(
            username='admin',
            defaults={
                'email': 'serkafox@gmail.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        admin.set_password(password)
        admin.save(update_fields=['password', 'email', 'is_staff', 'is_superuser', 'is_active'])
        UserProfile.objects.update_or_create(user=admin, defaults={'role': UserProfile.ROLE_ADMIN})
        self.stdout.write(self.style.SUCCESS('Usuario admin preparado.'))

        created = 0
        updated = 0
        for tecnico in Tecnico.objects.filter(activo=True).order_by('nombre'):
            username = self._unique_username(User, slugify(tecnico.nombre) or f'tecnico-{tecnico.pk}', tecnico.pk)
            user, was_created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': tecnico.nombre,
                    'email': tecnico.email,
                    'is_active': True,
                },
            )
            changed_fields = []
            if user.first_name != tecnico.nombre:
                user.first_name = tecnico.nombre
                changed_fields.append('first_name')
            if tecnico.email and user.email != tecnico.email:
                user.email = tecnico.email
                changed_fields.append('email')
            if not user.is_active:
                user.is_active = True
                changed_fields.append('is_active')
            if was_created or options['reset_technician_passwords']:
                user.set_password(password)
                changed_fields.append('password')
            if changed_fields:
                user.save(update_fields=sorted(set(changed_fields)))
            UserProfile.objects.update_or_create(user=user, defaults={'role': UserProfile.ROLE_TECHNICIAN})
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(f'Técnicos preparados: {created} creados, {updated} existentes.'))

    def _unique_username(self, User, base, tecnico_pk):
        base = base[:120]
        existing = User.objects.filter(username=base).first()
        if existing and existing.first_name:
            return base
        if not existing:
            return base
        candidate = f'{base}-{tecnico_pk}'[:150]
        suffix = 2
        while User.objects.filter(username=candidate).exists():
            candidate = f'{base}-{tecnico_pk}-{suffix}'[:150]
            suffix += 1
        return candidate
