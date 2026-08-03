import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

_default = Path(__file__).resolve().parent / "app.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", str(_default)))


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            email             TEXT    UNIQUE NOT NULL,
            password_hash     TEXT    NOT NULL,
            nombre            TEXT    NOT NULL,
            rol               TEXT    NOT NULL DEFAULT 'usuario',
            max_registros     INTEGER DEFAULT 10000,
            fecha_vencimiento DATE,
            activo            BOOLEAN DEFAULT 1,
            fecha_creacion    DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sesiones (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id       INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            token            TEXT    UNIQUE NOT NULL,
            fecha_expiracion DATETIME NOT NULL,
            creado_en        DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS analisis (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id      INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            file_id         TEXT,
            nombre_archivo  TEXT,
            total_registros INTEGER,
            score_general   REAL,
            fecha           DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Migrate analisis table: add columns if missing
    for col_def in [
        "descripcion TEXT",
        "etiqueta TEXT",
        "total_columnas INTEGER",
        "total_problemas INTEGER",
        "dimensiones_aplicadas TEXT",
        "ruta_reporte TEXT",
        "ruta_dashboard TEXT",
        "estado TEXT DEFAULT 'completado'",
        "version_motor TEXT DEFAULT 'v2'",
        "naturaleza_dato TEXT",
        "proposito_analisis TEXT",
        "tipo_ia TEXT",
    ]:
        try:
            conn.execute(f"ALTER TABLE analisis ADD COLUMN {col_def}")
        except Exception:
            pass  # Column already exists
    conn.commit()

    existing = conn.execute(
        "SELECT id FROM usuarios WHERE email = ?", ("admin@dqplatform.com",)
    ).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO usuarios (email, password_hash, nombre, rol, max_registros, activo) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            ("admin@dqplatform.com", hash_password("Admin123!"), "Administrador", "admin", 999999),
        )

    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    return f"{salt}:{digest}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split(":", 1)
        return hashlib.sha256(f"{password}{salt}".encode()).hexdigest() == digest
    except Exception:
        return False
