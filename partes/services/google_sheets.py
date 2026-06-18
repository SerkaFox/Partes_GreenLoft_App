import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def append_parte_to_google_sheet(parte):
    if not getattr(settings, 'GOOGLE_SHEETS_ENABLED', False):
        logger.info('Google Sheets disabled')
        return False
    logger.info('Google Sheets enabled but API integration is not configured. parte_id=%s', parte.pk)
    return False
