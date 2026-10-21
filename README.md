# Enfoque — gestor privado de tareas

Aplicación web local en español para crear una cuenta y organizar tareas privadas. Usa Flask y SQLite; no requiere servicios externos ni una base de datos aparte.

## Requisitos

- Python 3.12 o posterior.
- `pip`.

## Instalación y ejecución

Desde la carpeta del proyecto, crea y activa un entorno virtual:

**Windows (PowerShell):**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
python app.py
```

**macOS / Linux:**

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python app.py
```

Abre <http://127.0.0.1:5000>. Regístrate para empezar. La variable `FLASK_SECRET_KEY` es obligatoria y debe tener al menos 32 caracteres; los comandos anteriores generan una clave aleatoria privada. No la incluyas en el código ni la compartas. Para conservar la sesión entre reinicios, mantén la misma clave en tu entorno. Si falta o es demasiado corta, la aplicación se niega a arrancar.

La base de datos se crea automáticamente en `instance/tasks.sqlite3`. Ese directorio está excluido de Git y contiene información privada. Para reiniciar el almacenamiento, detén la aplicación y elimina ese archivo.

## Uso

- Registro e inicio/cierre de sesión.
- Crear tareas con título y descripción opcional.
- Ver todas, pendientes o completadas; editar y completar/reabrir.
- Eliminar una tarea con confirmación.
- Los nombres de usuario admiten entre 3 y 30 letras, números o guion bajo. Las contraseñas deben tener al menos 10 caracteres.

La aplicación está pensada para uso local por HTTP. Para exponerla en una red o Internet, primero configura HTTPS, cookies seguras, un servidor WSGI de producción y las medidas de despliegue apropiadas; el servidor integrado de Flask no es un servidor de producción.

## Seguridad

- Contraseñas almacenadas mediante `werkzeug.security` (hash scrypt), nunca en texto plano.
- Token CSRF impredecible en todas las solicitudes POST, comparado en tiempo constante.
- Clave de sesión de configuración obligatoria, cookies HttpOnly y SameSite=Lax.
- Cada consulta y mutación de tareas filtra por el propietario autenticado; un recurso ajeno se responde como no encontrado.
- SQLite aplica clave foránea de tarea a usuario y consultas parametrizadas.
- La plantilla de Flask escapa automáticamente los datos de usuario.

## Pruebas

Instala las dependencias y ejecuta:

```sh
python -m unittest discover -s tests -v
```

Las pruebas cubren registro, hash de contraseña, inicio/cierre de sesión, CSRF, validación, operaciones de tareas y aislamiento entre usuarios.
