from workdocs.models import TaskVoiceReport


def transcribe_audio(report_id):
    report = TaskVoiceReport.objects.get(pk=report_id)
    report.transcript_status = TaskVoiceReport.TRANSCRIPT_PENDING
    report.save(update_fields=['transcript_status'])
    return report
