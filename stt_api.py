import os
import shutil
import tempfile
from pathlib import Path

import django
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'j_listoya.settings')
django.setup()

from workdocs.services.transcription import transcribe_file  # noqa: E402

app = FastAPI(title='J Listoya STT API')


def _check_token(token):
    expected = os.getenv('JARVIS_STT_TOKEN', '')
    if not expected:
        raise HTTPException(status_code=503, detail='STT token is not configured')
    if token != expected:
        raise HTTPException(status_code=401, detail='Invalid token')


@app.post('/api/stt/transcribe')
async def transcribe_upload(
    file: UploadFile = File(...),
    x_jarvis_token: str = Header(default='', alias='X-JARVIS-TOKEN'),
):
    _check_token(x_jarvis_token)
    suffix = Path(file.filename or 'audio').suffix or '.audio'
    tmp_path = ''
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        language = os.getenv('JARVIS_STT_LANGUAGE', 'ru')
        result = transcribe_file(tmp_path, language=language)
        return {
            'text': result['text'],
            'language': result['language'] or language,
            'duration': result['duration'],
        }
    finally:
        await file.close()
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
