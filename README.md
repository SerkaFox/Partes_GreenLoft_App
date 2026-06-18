# j.listoya.es

Plataforma Django para coordinar trabajo técnico de campo: tareas, técnicos, vehículos, chat operativo, archivos, partes de trabajo, PDF, email y panel interno.

El sistema tiene dos áreas principales:

- `/trabajo/`: panel operativo moderno para administradores, managers y técnicos.
- `/partes/`: formulario de parte de trabajo y generación de documentación final.

## Flujo completo

1. Login
   - Entrada desde `/panel/login/`.
   - Selector de acceso para administración/managers y técnicos.
   - Cada grupo recuerda su último usuario seleccionado sin guardar contraseñas.

2. Dashboard de trabajo
   - URL: `/trabajo/`.
   - Muestra métricas de tareas pendientes, finalizadas, documentos y activas.
   - Las tarjetas enlazan directamente al listado filtrado.
   - Admin/manager ven técnicos con actividad y las tareas activas asociadas.

3. Tareas
   - URL: `/trabajo/tareas/`.
   - Admin/manager ven tareas de técnicos.
   - Técnicos ven solo sus propias tareas.
   - Soporta filtros por estado, técnico, texto y documentos.
   - Cada tarjeta muestra estado, técnicos, dirección y badge de mensajes.

4. Creación y edición de tareas
   - Admin/manager crean tareas en `/trabajo/tareas/nueva/`.
   - Una tarea puede tener varios técnicos.
   - `assigned_to` se conserva como técnico principal para compatibilidad.
   - Puede asignarse vehículo desde lista buscable.
   - Si hay técnico con vehículo en perfil, se puede autocompletar.
   - Dirección y mapa guardan coordenadas para navegación.
   - Los campos ya completados se mantienen compactos y se editan bajo demanda.

5. Detalle de tarea
   - URL: `/trabajo/tareas/<id>/`.
   - Muestra información, técnicos, vehículo, estado, fechas, navegación y enlace a parte.
   - Los nombres de usuarios y vehículo son clicables para admin/manager.
   - Permite crear continuación de una tarea con relación a la tarea padre.

6. Estados técnicos
   - Técnicos asignados pueden registrar hitos:
     - `He llegado al trabajo`
     - `He llegado al objeto`
     - `Salí del objeto`
     - `Trabajo finalizado`
   - Cada acción actualiza estado y guarda evento histórico.

7. Chat de tarea
   - Texto, audio y archivos conviven en un chat cronológico.
   - El campo `Escribir mensaje` envía con Enter.
   - `Shift+Enter` permite salto de línea.
   - Botón `+` adjunta fotos, vídeos, audio, PDF y documentos.
   - Botón de micrófono graba audio desde el navegador.
   - Audio subido o grabado entra como mensaje de voz.
   - Los mensajes muestran autor, avatar, rol y hora.
   - Soporta respuestas tipo hilo y reacciones simples.
   - Si hay más de tres mensajes, el chat se limita en altura y hace scroll.

8. Transcripción local
   - Los audios se transcriben fuera del request HTTP.
   - Comando:
     ```bash
     venv/bin/python manage.py transcribe_pending_voice_reports
     ```
   - Timer systemd:
     - `j_listoya_transcribe.timer`
     - ejecuta `j_listoya_transcribe.service` cada minuto.
   - Motor: `faster-whisper`.
   - Idioma fijado a español.
   - Estados:
     - `pending`
     - `processing`
     - `done`
     - `error`

9. Materiales
   - En el detalle de tarea hay panel de materiales.
   - Permite subir archivos o hacer foto desde móvil.
   - Filtros: `Todos`, `Técnico`, `Admin`.
   - Imágenes tienen miniatura.
   - PDF tiene vista previa.
   - Vídeo/audio usan reproductor.
   - Word/Excel y otros documentos se descargan.

10. Partes de trabajo
    - URL: `/partes/`.
    - Puede abrirse desde una tarea con `?task=<id>`.
    - Precarga datos de la tarea:
      - técnico principal
      - compañeros
      - vehículo
      - tiempos registrados por botones de estado
      - dirección y contexto de trabajo
    - Genera PDF del parte.
    - Puede enviar PDF por email.
    - Puede exportar CSV desde panel.

11. Usuarios y perfiles
    - URL admin/manager: `/trabajo/usuarios/`.
    - Los usuarios se gestionan con tarjetas, no tabla.
    - Cada perfil tiene:
      - avatar
      - nombre
      - email
      - rol
      - activo/inactivo
      - descripción
      - vehículo asignado
    - Admin/manager pueden crear, editar, activar/desactivar y ver tareas de usuarios.
    - Nadie puede desactivarse a sí mismo desde la gestión.
    - Usuario actual edita su perfil en `/trabajo/perfil/`.

12. Vehículos
    - URL moderna: `/trabajo/vehiculos/`.
    - Usa el modelo existente `partes.Vehiculo`.
    - Gestión en diseño workdocs.
    - Tarjetas con matrícula, descripción, orden, activo/inactivo y foto.
    - Búsqueda en vivo por matrícula o descripción.
    - El panel legacy `/panel/vehiculos/` se conserva.

13. Panel legacy
    - URL: `/panel/`.
    - Mantiene gestión histórica de:
      - técnicos
      - vehículos
      - proyectos
      - partes
      - reenvío de email
      - exportación CSV

## Roles

- Admin
  - Acceso global a trabajo, usuarios, vehículos, tareas, partes y panel.

- Manager
  - Gestión operativa de tareas, usuarios permitidos, vehículos y partes según permisos definidos.

- Technician
  - Ve solo tareas asignadas directamente o por equipo.
  - Puede actualizar estados, escribir en chat, grabar audio, subir materiales y crear partes desde tarea.

## Modelos clave

- `UserProfile`
  - rol, avatar, descripción, activo, vehículo.

- `Task`
  - tarea, estado, dirección, coordenadas, técnicos, vehículo, fechas e historial de continuidad.

- `TaskEvent`
  - eventos de tarea, comentarios, respuestas y reacciones.

- `TaskFile`
  - archivos adjuntos de tarea.

- `TaskVoiceReport`
  - audios de chat y descripción con transcripción.

- `ParteTrabajo`
  - parte final de trabajo con PDF, email, CSV y fotos.

- `Vehiculo`
  - catálogo compartido entre partes y trabajo.

## Comandos útiles

```bash
cd /home/seradmin/jelec/j_listoya

venv/bin/python manage.py check
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py transcribe_pending_voice_reports

printf 'Spain785!\n' | sudo -S systemctl restart j_listoya
systemctl status j_listoya --no-pager
systemctl status j_listoya_transcribe.timer --no-pager
```

## Configuración

Variables principales en `.env`:

```env
DJANGO_SECRET_KEY=
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=j.listoya.es,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://j.listoya.es

EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=

GOOGLE_SHEETS_ENABLED=false
GOOGLE_SHEET_ID=
GOOGLE_SERVICE_ACCOUNT_JSON=

WORKDOCS_WHISPER_MODEL=tiny
```

## Stack

- Django 6
- Gunicorn
- Bootstrap
- Leaflet / OpenStreetMap
- ReportLab
- faster-whisper
- systemd

## Estado operativo

La plataforma está pensada para que el ciclo completo ocurra en el mismo flujo:

login -> dashboard -> tarea -> técnicos/vehículo/mapa -> chat y materiales -> estados técnicos -> parte -> PDF/email/exportación -> historial.
