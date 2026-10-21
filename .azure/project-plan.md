# Plan de proyecto: Gestor de tareas

Status: Approved

## Objetivo

Crear una aplicación web local en Python para que cada persona pueda administrar sus propias tareas mediante una cuenta protegida.

## Alcance

- Registro de usuarios, inicio y cierre de sesión.
- Contraseñas almacenadas mediante hash seguro, nunca en texto plano.
- Crear, consultar, editar, completar/reabrir y eliminar tareas.
- Restringir todas las operaciones de tareas al usuario autenticado propietario.
- Interfaz web en español, adaptable a móvil, con formularios y mensajes de validación.
- Persistencia local con SQLite.

## Tecnología

- Python 3.12 o superior.
- Flask para rutas, sesiones y renderizado del lado del servidor.
- SQLite para usuarios y tareas.
- HTML y CSS propios, sin servicios externos requeridos para ejecutar la aplicación.

## Modelo de datos

- Usuario: identificador, nombre de usuario único, hash de contraseña y fecha de creación.
- Tarea: identificador, propietario, título, descripción opcional, estado completado y fechas de creación/actualización.
- La relación de tarea a usuario tendrá integridad referencial; cada consulta y mutación verificará el propietario.

## Seguridad y validación

- Hash de contraseñas mediante el mecanismo seguro de Werkzeug.
- Protección CSRF en formularios que modifican datos.
- Validación de entradas en servidor; mensajes claros para formularios inválidos y nombres de usuario duplicados.
- Acceso no autenticado redirigido al inicio de sesión; acceso a recursos ajenos rechazado sin revelar datos.
- Clave de sesión proporcionada mediante variable de entorno, con instrucción segura para desarrollo local.

## Criterios de aceptación

1. Una persona puede registrarse, iniciar sesión y cerrar sesión.
2. Una persona autenticada puede crear, editar, completar/reabrir y eliminar sus tareas.
3. Un usuario no puede consultar ni modificar tareas pertenecientes a otra cuenta.
4. La aplicación conserva usuarios y tareas después de reiniciarse.
5. Las entradas inválidas y los errores de autenticación se muestran de forma comprensible.
6. Se documentan la instalación, configuración y ejecución local, y se incluyen pruebas automatizadas para autenticación, operaciones de tareas y aislamiento entre usuarios.

## Fuera de alcance

- Despliegue en Azure u otro proveedor, recuperación de contraseña por correo, colaboración entre usuarios y notificaciones.
