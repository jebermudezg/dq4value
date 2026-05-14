import asyncio
import secrets
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from database.db import get_connection, hash_password, init_db, verify_password
from engine.parsers import get_column_info, parse_file
from engine.report_gen import generate_excel_report
from engine.scorer import DQScorer

# ──────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DQ4Value",
    description="API para análisis de calidad de datos.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


# ──────────────────────────────────────────────────────────────────────
# In-memory stores
# ──────────────────────────────────────────────────────────────────────

_file_store: dict = {}
_analysis_store: dict = {}
_progress_store: dict = {}   # file_id -> {pct, message, done, error}

TEMP_DIR = Path(__file__).resolve().parent.parent / "temp_files"
TEMP_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".txt"}

# ──────────────────────────────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    file_id: str
    id_column: str
    columns_config: dict[str, dict[str, dict]]


class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    password: str
    nombre: str
    rol: str = "usuario"
    max_registros: int = 10000
    fecha_vencimiento: Optional[str] = None


class UpdateUserRequest(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[str] = None
    max_registros: Optional[int] = None
    fecha_vencimiento: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────────────────────────────


def get_current_user(authorization: str = Header(None)) -> dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autenticación requerido.")
    token = authorization.removeprefix("Bearer ").strip()
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    row = conn.execute(
        """SELECT u.* FROM sesiones s
           JOIN usuarios u ON s.usuario_id = u.id
           WHERE s.token = ? AND s.fecha_expiracion > ?""",
        (token, now),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Token inválido o sesión expirada.")
    return dict(row)


def require_admin(authorization: str = Header(None)) -> dict:
    user = get_current_user(authorization)
    if user["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Se requiere rol de administrador.")
    return user


# ──────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


# ──────────────────────────────────────────────────────────────────────
# Auth endpoints
# ──────────────────────────────────────────────────────────────────────


@app.post("/auth/login")
def login(request: LoginRequest):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM usuarios WHERE email = ?", (request.email,)
    ).fetchone()

    if not user or not verify_password(request.password, user["password_hash"]):
        conn.close()
        raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

    if not user["activo"]:
        conn.close()
        raise HTTPException(status_code=403, detail="Usuario desactivado.")

    if user["fecha_vencimiento"]:
        if datetime.utcnow().date() > datetime.strptime(user["fecha_vencimiento"], "%Y-%m-%d").date():
            conn.close()
            raise HTTPException(status_code=403, detail="Usuario vencido.")

    # Clean only expired sessions to allow multiple concurrent sessions
    conn.execute(
        "DELETE FROM sesiones WHERE usuario_id = ? AND fecha_expiracion <= ?",
        (user["id"], datetime.utcnow().isoformat()),
    )

    token = secrets.token_urlsafe(32)
    expiry = (datetime.utcnow() + timedelta(hours=8)).isoformat()
    conn.execute(
        "INSERT INTO sesiones (usuario_id, token, fecha_expiracion) VALUES (?, ?, ?)",
        (user["id"], token, expiry),
    )
    conn.commit()
    conn.close()

    return {
        "token": token,
        "nombre": user["nombre"],
        "email": user["email"],
        "rol": user["rol"],
        "max_registros": user["max_registros"],
    }


@app.post("/auth/logout")
def logout(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Token requerido.")
    token = authorization.removeprefix("Bearer ").strip()
    conn = get_connection()
    conn.execute("DELETE FROM sesiones WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return {"message": "Sesión cerrada correctamente."}


@app.get("/auth/me")
def me(authorization: str = Header(None)):
    user = get_current_user(authorization)
    return {
        "id": user["id"],
        "nombre": user["nombre"],
        "email": user["email"],
        "rol": user["rol"],
        "max_registros": user["max_registros"],
        "fecha_vencimiento": user["fecha_vencimiento"],
    }


# ──────────────────────────────────────────────────────────────────────
# File endpoints (protected)
# ──────────────────────────────────────────────────────────────────────


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    authorization: str = Header(None),
):
    current_user = get_current_user(authorization)

    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato '{suffix}' no compatible. Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    file_id = secrets.token_urlsafe(16)
    dest_path = TEMP_DIR / f"{file_id}{suffix}"

    try:
        content = await file.read()
        dest_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al guardar el archivo: {e}")

    try:
        df, columns = parse_file(str(dest_path))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error interno al parsear el archivo: {e}")

    # Enforce row limit for the user
    max_reg = current_user["max_registros"]
    if len(df) > max_reg:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=403,
            detail=f"El archivo tiene {len(df)} registros pero tu plan permite máximo {max_reg} registros.",
        )

    col_info = get_column_info(df)

    _file_store[file_id] = {
        "path": str(dest_path),
        "df": df,
        "columns": columns,
        "original_name": file.filename,
        "usuario_id": current_user["id"],
    }

    return {
        "file_id": file_id,
        "nombre_archivo": file.filename,
        "total_registros": len(df),
        "total_columnas": len(columns),
        "columnas": col_info,
    }


@app.get("/analyze/status/{file_id}")
def analyze_status(file_id: str, authorization: str = Header(None)):
    get_current_user(authorization)
    return _progress_store.get(
        file_id,
        {"pct": 0, "message": "No iniciado", "done": False, "error": None},
    )


@app.post("/analyze")
async def analyze(request: AnalyzeRequest, authorization: str = Header(None)):
    current_user = get_current_user(authorization)

    if request.file_id not in _file_store:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró el archivo con id '{request.file_id}'.",
        )
    if not request.columns_config:
        raise HTTPException(status_code=400, detail="El campo 'columns_config' no puede estar vacío.")

    stored = _file_store[request.file_id]
    df = stored["df"]

    if request.id_column not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"La columna ID '{request.id_column}' no existe. Disponibles: {stored['columns']}",
        )
    missing = [c for c in request.columns_config if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Columnas no encontradas: {missing}. Disponibles: {stored['columns']}",
        )

    # Initialise progress
    col_names  = list(request.columns_config.keys())
    total_dims = sum(len(v) for v in request.columns_config.values())
    fid        = request.file_id
    _progress_store[fid] = {"pct": 0, "message": "Iniciando análisis...", "done": False, "error": None}

    def _progress_cb(col: str, dim_name: str, done: int, total: int) -> None:
        pct     = min(5 + int((done / max(total, 1)) * 80), 84)
        col_idx = col_names.index(col) + 1 if col in col_names else "?"
        _progress_store[fid] = {
            "pct":     pct,
            "message": f"Procesando columna {col_idx} de {len(col_names)} ({col})",
            "done":    False,
            "error":   None,
        }

    def _run_sync() -> dict:
        scorer = DQScorer(df, id_col=request.id_column, progress_callback=_progress_cb)
        for col_name, dim_config in request.columns_config.items():
            scorer.configure(col_name, dim_config)
        return scorer.run_analysis()

    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, _run_sync)
    except Exception as e:
        print("ERROR DETALLADO:")
        traceback.print_exc()
        _progress_store[fid] = {"pct": 0, "message": str(e), "done": True, "error": str(e)}
        if isinstance(e, (ValueError, RuntimeError)):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=f"Error interno durante el análisis: {e}")

    _progress_store[fid] = {"pct": 90, "message": "Generando reporte...", "done": False, "error": None}

    # Compute summary without re-running analysis
    summary = DQScorer.compute_summary(results)

    _analysis_store[request.file_id] = results

    # Persist analysis record
    try:
        conn = get_connection()
        conn.execute(
            "INSERT INTO analisis (usuario_id, file_id, nombre_archivo, total_registros, score_general) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                current_user["id"],
                request.file_id,
                stored.get("original_name", ""),
                results["total_registros"],
                results["score_general"],
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Non-critical

    _progress_store[fid] = {"pct": 100, "message": "¡Análisis completado!", "done": True, "error": None}

    return {
        "file_id": request.file_id,
        "score_general": results["score_general"],
        "total_registros": results["total_registros"],
        "total_problemas": results["total_problemas"],
        "pct_limpios": summary["pct_limpios"],
        "peor_dimension": summary["peor_dimension"],
        "scores_por_columna": results["scores_por_columna"],
    }


@app.get("/report/{file_id}")
def get_report(file_id: str, authorization: str = Header(None)):
    get_current_user(authorization)

    if file_id not in _file_store:
        raise HTTPException(status_code=404, detail=f"Archivo '{file_id}' no encontrado.")
    if file_id not in _analysis_store:
        raise HTTPException(status_code=400, detail="Ejecuta primero POST /analyze.")

    report_path = TEMP_DIR / f"reporte_{file_id}.xlsx"
    try:
        generate_excel_report(_analysis_store[file_id], str(report_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar el reporte: {e}")

    original_name = Path(_file_store[file_id]["original_name"]).stem
    return FileResponse(
        path=str(report_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"reporte_calidad_{original_name}.xlsx",
    )


class SuggestRequest(BaseModel):
    file_id: str


@app.post("/ai/suggest")
def ai_suggest(request: SuggestRequest, authorization: str = Header(None)):
    from ai.claude_analyzer import suggest_dimensions_rules

    get_current_user(authorization)
    file_id = request.file_id

    if file_id not in _file_store:
        raise HTTPException(status_code=404, detail=f"Archivo '{file_id}' no encontrado.")

    df = _file_store[file_id]["df"]
    col_info = get_column_info(df)

    # Enrich metadata with unique-value stats needed for type-based rules
    for ci in col_info:
        col = ci["nombre"]
        ci["valores_unicos"] = int(df[col].nunique(dropna=True))
        if ci["valores_unicos"] <= 15:
            ci["top_values"] = (
                df[col].dropna().value_counts().head(10).index.astype(str).tolist()
            )
        else:
            ci["top_values"] = []

    return suggest_dimensions_rules(col_info)


@app.get("/issues/{file_id}")
def get_issues(file_id: str, authorization: str = Header(None)):
    get_current_user(authorization)

    if file_id not in _file_store:
        raise HTTPException(status_code=404, detail=f"Archivo '{file_id}' no encontrado.")
    if file_id not in _analysis_store:
        raise HTTPException(status_code=400, detail="Ejecuta primero POST /analyze.")

    issues_df = _analysis_store[file_id]["issues_df"]
    if issues_df.empty:
        return {"file_id": file_id, "total": 0, "issues": []}

    df = issues_df.copy()
    df = df.rename(columns={df.columns[0]: "id_registro"})
    df = df.where(df.notna(), other=None)
    return {"file_id": file_id, "total": len(df), "issues": df.to_dict(orient="records")}


# ──────────────────────────────────────────────────────────────────────
# Admin endpoints
# ──────────────────────────────────────────────────────────────────────


@app.get("/admin/usuarios")
def list_users(authorization: str = Header(None)):
    require_admin(authorization)
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, email, nombre, rol, max_registros, fecha_vencimiento, activo, fecha_creacion "
        "FROM usuarios ORDER BY fecha_creacion DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/admin/usuarios")
def create_user(request: CreateUserRequest, authorization: str = Header(None)):
    require_admin(authorization)
    if request.rol not in ("admin", "usuario"):
        raise HTTPException(status_code=400, detail="Rol debe ser 'admin' o 'usuario'.")
    conn = get_connection()
    existing = conn.execute("SELECT id FROM usuarios WHERE email = ?", (request.email,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail=f"Ya existe un usuario con email '{request.email}'.")
    conn.execute(
        "INSERT INTO usuarios (email, password_hash, nombre, rol, max_registros, fecha_vencimiento) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            request.email,
            hash_password(request.password),
            request.nombre,
            request.rol,
            request.max_registros,
            request.fecha_vencimiento,
        ),
    )
    conn.commit()
    user_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()
    return {"message": "Usuario creado.", "id": user_id}


@app.put("/admin/usuarios/{user_id}")
def update_user(user_id: int, request: UpdateUserRequest, authorization: str = Header(None)):
    require_admin(authorization)
    conn = get_connection()
    user = conn.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")

    fields, values = [], []
    if request.nombre            is not None: fields.append("nombre = ?");           values.append(request.nombre)
    if request.rol               is not None: fields.append("rol = ?");              values.append(request.rol)
    if request.max_registros     is not None: fields.append("max_registros = ?");   values.append(request.max_registros)
    if request.fecha_vencimiento is not None: fields.append("fecha_vencimiento = ?"); values.append(request.fecha_vencimiento)
    if request.activo            is not None: fields.append("activo = ?");           values.append(1 if request.activo else 0)
    if request.password          is not None:
        if len(request.password) < 6:
            conn.close()
            raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres.")
        fields.append("password_hash = ?")
        values.append(hash_password(request.password))

    if fields:
        values.append(user_id)
        conn.execute(f"UPDATE usuarios SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()
    return {"message": "Usuario actualizado."}


@app.delete("/admin/usuarios/{user_id}")
def delete_user(user_id: int, authorization: str = Header(None)):
    admin = require_admin(authorization)
    if admin["id"] == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta.")
    conn = get_connection()
    user = conn.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    conn.execute("DELETE FROM usuarios WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": "Usuario eliminado."}


@app.get("/admin/usuarios/{user_id}/analisis")
def user_analyses(user_id: int, authorization: str = Header(None)):
    require_admin(authorization)
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM analisis WHERE usuario_id = ? ORDER BY fecha DESC LIMIT 50",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
