import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import create_app


TOKEN_RE = re.compile(
    r'<input[^>]+name="csrf_token"[^>]+value="([^"]+)"'
)


class TaskAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only-secret-that-is-long-enough",
                "DATABASE": self.db_path,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def token(self, client=None, path="/iniciar-sesion"):
        response = (client or self.client).get(path)
        self.assertEqual(response.status_code, 200)
        match = TOKEN_RE.search(response.get_data(as_text=True))
        self.assertIsNotNone(match, "El formulario debe incluir token CSRF")
        return match.group(1)

    def register(self, client, username, password="correct-horse-battery"):
        token = self.token(client, "/registro")
        return client.post(
            "/registro",
            data={"csrf_token": token, "username": username, "password": password},
            follow_redirects=True,
        )

    def create_task(self, client, title, description=""):
        token = self.token(client, "/")
        return client.post(
            "/tareas/nueva",
            data={"csrf_token": token, "title": title, "description": description},
            follow_redirects=True,
        )

    def test_registration_hashes_password_and_duplicate_is_rejected(self):
        response = self.register(self.client, "ana")
        self.assertIn("Tu cuenta se creó", response.get_data(as_text=True))

        db = sqlite3.connect(self.db_path)
        try:
            password_hash = db.execute(
                "SELECT password_hash FROM users WHERE username = 'ana'"
            ).fetchone()[0]
        finally:
            db.close()
        self.assertNotEqual(password_hash, "correct-horse-battery")
        self.assertTrue(password_hash.startswith("scrypt:"))

        duplicate = self.register(self.app.test_client(), "ANA")
        self.assertIn("ya está registrado", duplicate.get_data(as_text=True))

    def test_login_logout_and_authentication_required(self):
        self.client.get("/")
        self.assertEqual(self.register(self.client, "ana").status_code, 200)
        logout_token = self.token(self.client, "/")
        response = self.client.post(
            "/cerrar-sesion", data={"csrf_token": logout_token}, follow_redirects=True
        )
        self.assertIn("Iniciar sesión", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/").status_code, 302)

        token = self.token(self.client, "/iniciar-sesion")
        response = self.client.post(
            "/iniciar-sesion",
            data={
                "csrf_token": token,
                "username": "ana",
                "password": "correct-horse-battery",
            },
            follow_redirects=True,
        )
        self.assertIn("Mis tareas", response.get_data(as_text=True))

    def test_task_crud_and_completion_reopening(self):
        self.register(self.client, "ana")
        response = self.create_task(self.client, "Preparar informe", "Resumen del mes")
        page = response.get_data(as_text=True)
        self.assertIn("Preparar informe", page)
        self.assertIn("Resumen del mes", page)

        with self.app.app_context():
            from app import get_db

            task_id = get_db().execute("SELECT id FROM tasks").fetchone()["id"]

        token = self.token(self.client, "/")
        response = self.client.post(
            f"/tareas/{task_id}/estado",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn("Reabrir", response.get_data(as_text=True))
        self.assertIn("Completadas", self.client.get("/?estado=completadas").get_data(as_text=True))

        edit_token = self.token(self.client, f"/tareas/{task_id}/editar")
        response = self.client.post(
            f"/tareas/{task_id}/editar",
            data={
                "csrf_token": edit_token,
                "title": "Informe terminado",
                "description": "Revisado",
            },
            follow_redirects=True,
        )
        self.assertIn("Informe terminado", response.get_data(as_text=True))

        token = self.token(self.client, "/")
        response = self.client.post(
            f"/tareas/{task_id}/estado",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        self.assertIn("Completar", response.get_data(as_text=True))

        token = self.token(self.client, "/")
        self.client.post(f"/tareas/{task_id}/eliminar", data={"csrf_token": token})
        self.assertNotIn("Informe terminado", self.client.get("/").get_data(as_text=True))

    def test_owner_isolation_for_read_edit_toggle_and_delete(self):
        self.register(self.client, "ana")
        self.create_task(self.client, "Privada de Ana")
        with self.app.app_context():
            from app import get_db

            task_id = get_db().execute("SELECT id FROM tasks").fetchone()["id"]

        other = self.app.test_client()
        self.register(other, "bea")
        self.assertNotIn("Privada de Ana", other.get("/").get_data(as_text=True))
        self.assertEqual(other.get(f"/tareas/{task_id}/editar").status_code, 404)

        for endpoint in ("estado", "eliminar"):
            token = self.token(other, "/")
            response = other.post(
                f"/tareas/{task_id}/{endpoint}", data={"csrf_token": token}
            )
            self.assertEqual(response.status_code, 404)

        with self.app.app_context():
            from app import get_db

            self.assertEqual(
                get_db().execute(
                    "SELECT title FROM tasks WHERE id = ?", (task_id,)
                ).fetchone()["title"],
                "Privada de Ana",
            )

    def test_csrf_and_server_side_validation(self):
        self.register(self.client, "ana")
        self.assertEqual(self.client.post("/tareas/nueva", data={"title": "Sin token"}).status_code, 400)

        token = self.token(self.client, "/")
        response = self.client.post(
            "/tareas/nueva",
            data={"csrf_token": token, "title": "  ", "description": ""},
            follow_redirects=True,
        )
        self.assertIn("El título es obligatorio", response.get_data(as_text=True))
        self.assertEqual(self.client.get("/?estado=desconocido").status_code, 200)

    def test_secret_key_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "FLASK_SECRET_KEY"):
            create_app({"SECRET_KEY": None, "DATABASE": self.db_path})
        with self.assertRaisesRegex(RuntimeError, "32 caracteres"):
            create_app(
                {
                    "SECRET_KEY": "weak",
                    "DATABASE": self.db_path,
                }
            )


if __name__ == "__main__":
    unittest.main()
