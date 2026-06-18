import os

from django.conf import settings

from workdocs.models import TaskVoiceReport


def _model_name():
    return getattr(settings, 'WORKDOCS_WHISPER_MODEL', os.getenv('WORKDOCS_WHISPER_MODEL', 'tiny'))


def _download_root():
    return getattr(settings, 'WORKDOCS_WHISPER_CACHE', settings.BASE_DIR / 'media' / 'whisper_models')


def transcribe_audio(report_id):
    report = TaskVoiceReport.objects.get(pk=report_id)
    if report.transcript_status == TaskVoiceReport.TRANSCRIPT_PROCESSING:
        return report

    report.transcript_status = TaskVoiceReport.TRANSCRIPT_PROCESSING
    report.save(update_fields=['transcript_status'])

    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(_model_name(), device='cpu', compute_type='int8', download_root=str(_download_root()))
        segments, _info = model.transcribe(report.audio_file.path, beam_size=1)
        transcript = ' '.join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        report.transcript_text = transcript
        report.transcript_status = TaskVoiceReport.TRANSCRIPT_DONE
        report.save(update_fields=['transcript_text', 'transcript_status'])
    except Exception as exc:
        report.transcript_text = str(exc)[:2000]
        report.transcript_status = TaskVoiceReport.TRANSCRIPT_ERROR
        report.save(update_fields=['transcript_text', 'transcript_status'])
    return report
