from django.core.management.base import BaseCommand

from workdocs.models import TaskVoiceReport
from workdocs.services.transcription import transcribe_audio


class Command(BaseCommand):
    help = 'Transcribe pending workdocs voice reports locally.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        limit = max(options['limit'], 1)
        reports = TaskVoiceReport.objects.filter(
            transcript_status=TaskVoiceReport.TRANSCRIPT_PENDING,
        ).order_by('created_at')[:limit]

        processed = 0
        for report in reports:
            self.stdout.write(f'Transcribing voice report #{report.pk}...')
            result = transcribe_audio(report.pk)
            self.stdout.write(f'#{result.pk}: {result.transcript_status}')
            processed += 1

        if not processed:
            self.stdout.write('No pending voice reports.')
