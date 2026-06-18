# j.listoya.es - Gestión de Partes Técnicos

Aplicación Django independiente para registrar partes de trabajo, generar PDF/CSV, enviar PDF por email y administrar catálogos desde `/panel/`.

## Comandos útiles

```bash
cd /home/seradmin/jelec/j_listoya
/home/seradmin/jelec/j_listoya/venv/bin/python manage.py migrate
/home/seradmin/jelec/j_listoya/venv/bin/python manage.py seed_initial_data
/home/seradmin/jelec/j_listoya/venv/bin/python manage.py createsuperuser
/home/seradmin/jelec/j_listoya/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart j_listoya
sudo systemctl status j_listoya --no-pager
```

## Panel

URL: `https://j.listoya.es/panel/`

Crear usuario de panel:

```bash
cd /home/seradmin/jelec/j_listoya
/home/seradmin/jelec/j_listoya/venv/bin/python manage.py createsuperuser
```

## SMTP / Google Sheets

Configurar en `.env`:

```env
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=
GOOGLE_SHEETS_ENABLED=false
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=
```
