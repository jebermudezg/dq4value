import random
import csv
from pathlib import Path
from datetime import date, timedelta

random.seed(42)

OUTPUT = Path(__file__).resolve().parent / "dataset_1000.csv"
N = 1000

# ── Pools ────────────────────────────────────────────────────────────

NOMBRES = [
    "Carlos", "Andrés", "Luis", "Jorge", "Miguel", "David", "Juan", "Felipe",
    "Sebastián", "Alejandro", "Daniel", "Ricardo", "Nicolás", "Camilo", "Sergio",
    "María", "Ana", "Laura", "Valentina", "Sofía", "Isabella", "Gabriela",
    "Daniela", "Natalia", "Paola", "Catalina", "Marcela", "Alejandra", "Diana",
    "Sandra",
]

APELLIDOS = [
    "García", "Rodríguez", "López", "Martínez", "González", "Hernández",
    "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Díaz", "Reyes",
    "Morales", "Jiménez", "Vargas", "Castro", "Ortega", "Ríos", "Mendoza",
    "Cruz", "Herrera", "Suárez", "Medina", "Rojas", "Guerrero", "Muñoz",
    "Vega", "Molina", "Salazar",
]

DOMINIOS = ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "empresa.co"]

CIUDADES_VALIDAS = [
    "Bogotá", "Medellín", "Cali", "Barranquilla", "Cartagena",
    "Bucaramanga", "Cúcuta", "Manizales",
]
CIUDADES_INVALIDAS = [
    "Bogota", "MEDELLIN", "bogotá", "Ciudad X", "cali", "CALI",
    "Barranquila", "cartagena", "BOGOTÁ", "Medelin",
]

ESTADOS_VALIDOS = ["Activo", "Inactivo", "Suspendido"]
ESTADOS_INVALIDOS = ["activo", "ACTIVO", "Pendiente", "N/A", "inactivo", "INACTIVO"]

CATEGORIAS_VALIDAS = ["Premium", "Estándar", "Básico"]
CATEGORIAS_INVALIDAS = ["premium", "PREMIUM", "VIP", "Normal", "standard"]

PAISES_VALIDOS = ["Colombia", "Venezuela", "Ecuador", "Perú", "México"]
PAISES_INVALIDOS = ["colombia", "COLOMBIA", "Brasil", "Chile", "Argentina"]


def rand_date(start: date, end: date) -> str:
    delta = (end - start).days
    return str(start + timedelta(days=random.randint(0, delta)))


def bad_date_formats(base: date) -> str:
    fmt = random.choice([
        base.strftime("%d/%m/%Y"),
        base.strftime("%m-%d-%Y"),
        base.strftime("%B %Y"),
        base.strftime("%d %b %Y"),
    ])
    return fmt


# ── Build index sets for injected errors ─────────────────────────────

all_idx = list(range(N))


def sample(n: int, exclude: set = None) -> set:
    pool = [i for i in all_idx if (exclude is None or i not in exclude)]
    return set(random.sample(pool, n))


# cliente_id duplicates — positions where we replace with one of 5 dup IDs
dup_ids = [50, 150, 300, 450, 600]
dup_positions = sample(5)                           # 5 rows → use dup IDs

# nombre nulls
nombre_null = sample(25)

# email invalids
email_invalid = sample(40)

# telefono invalids
tel_invalid = sample(30)

# edad invalids: 15 negative + 10 >120
edad_neg = sample(15)
edad_high = sample(10, exclude=edad_neg)
edad_bad = edad_neg | edad_high

# salario outliers
sal_outlier = sample(20)

# ciudad invalids
ciudad_invalid = sample(35)

# estado invalids
estado_invalid = sample(25)

# fecha_registro: 20 old (2010) + 15 bad format
freg_old = sample(20)
freg_bad_fmt = sample(15, exclude=freg_old)
freg_bad = freg_old | freg_bad_fmt

# fecha_ultima_compra: 50 nulls + 10 before fecha_registro
fuc_null = sample(50)
fuc_inconsistent = sample(10, exclude=fuc_null)

# monto_ultima_compra: null same as fuc_null + 15 negative (not in fuc_null)
monto_null = fuc_null
monto_neg = sample(15, exclude=monto_null)

# categoria nulls + invalids
cat_null = sample(20)
cat_invalid = sample(15, exclude=cat_null)

# nit duplicates + bad format
nit_pool = [str(random.randint(100000000, 999999999)) for _ in range(20)]
nit_dup_pos = sample(30)
nit_bad_fmt = sample(20, exclude=nit_dup_pos)

# pais invalids
pais_invalid = sample(10)

# score fuera de rango
score_bad = sample(25)

# ── Build rows ────────────────────────────────────────────────────────

rows = []
dup_pos_sorted = sorted(dup_positions)

for i in range(N):
    # ── cliente_id
    # Default: sequential 1..1000; 5 injected positions get a repeated dup ID
    if i in dup_positions:
        cid = dup_ids[dup_pos_sorted.index(i)]
    else:
        cid = i + 1

    # ── nombre
    if i in nombre_null:
        nombre = ""
    else:
        nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)} {random.choice(APELLIDOS)}"

    # ── email
    base_email = f"{random.choice(NOMBRES).lower()}{random.randint(1,999)}"
    if i in email_invalid:
        bad_type = random.choice(["no_at", "no_dot"])
        if bad_type == "no_at":
            email = f"{base_email}{random.choice(DOMINIOS)}"
        else:
            email = f"{base_email}@{random.choice(['gmail','yahoo','hotmail'])}"
    else:
        email = f"{base_email}@{random.choice(DOMINIOS)}"

    # ── telefono
    if i in tel_invalid:
        bad_tel = random.choice([
            "abc-1234", "555 123", "12-34-567", "not_a_phone",
            "+(57)invalid", "0000-XXXX", "tel:1234",
        ])
        telefono = bad_tel
    else:
        telefono = str(random.randint(3000000000, 3299999999))

    # ── edad
    if i in edad_neg:
        edad = random.randint(-50, -1)
    elif i in edad_high:
        edad = random.randint(121, 200)
    else:
        edad = random.randint(18, 75)

    # ── salario
    if i in sal_outlier:
        salario = random.choice([
            round(random.uniform(200000, 900000), 2),
            round(random.uniform(-5000, -500), 2),
        ])
    else:
        salario = round(random.uniform(1500, 8000), 2)

    # ── ciudad
    if i in ciudad_invalid:
        ciudad = random.choice(CIUDADES_INVALIDAS)
    else:
        ciudad = random.choice(CIUDADES_VALIDAS)

    # ── estado_cliente
    if i in estado_invalid:
        estado = random.choice(ESTADOS_INVALIDOS)
    else:
        estado = random.choice(ESTADOS_VALIDOS)

    # ── fecha_registro
    base_freg = date(2020, 1, 1) + timedelta(days=random.randint(0, (date(2024, 12, 31) - date(2020, 1, 1)).days))
    if i in freg_old:
        freg_str = str(date(2010, 1, 1) + timedelta(days=random.randint(0, 364)))
    elif i in freg_bad_fmt:
        freg_str = bad_date_formats(base_freg)
    else:
        freg_str = str(base_freg)

    # ── fecha_ultima_compra
    if i in fuc_null:
        fuc_str = ""
    elif i in fuc_inconsistent:
        # date BEFORE fecha_registro
        try:
            reg_date = date.fromisoformat(freg_str)
        except Exception:
            reg_date = date(2022, 1, 1)
        days_before = random.randint(1, 365)
        before = reg_date - timedelta(days=days_before)
        fuc_str = str(max(before, date(2015, 1, 1)))
    else:
        fuc_str = rand_date(date(2022, 1, 1), date(2024, 12, 31))

    # ── monto_ultima_compra
    if i in monto_null:
        monto = ""
    elif i in monto_neg:
        monto = round(random.uniform(-2000, -10), 2)
    else:
        monto = round(random.uniform(10, 5000), 2)

    # ── categoria_cliente
    if i in cat_null:
        categoria = ""
    elif i in cat_invalid:
        categoria = random.choice(CATEGORIAS_INVALIDAS)
    else:
        categoria = random.choice(CATEGORIAS_VALIDAS)

    # ── nit_empresa
    if i in nit_dup_pos:
        nit = random.choice(nit_pool)
    elif i in nit_bad_fmt:
        nit = random.choice([
            "12-345-678", "ABC123456", "123.456.78", "NIT9999",
            "12345678X", "00000000",
        ])
    else:
        nit = str(random.randint(100000000, 999999999))

    # ── pais
    if i in pais_invalid:
        pais = random.choice(PAISES_INVALIDOS)
    else:
        pais = random.choice(PAISES_VALIDOS)

    # ── score_credito
    if i in score_bad:
        score = random.choice([
            random.randint(-200, -1),
            random.randint(851, 1200),
        ])
    else:
        score = random.randint(300, 850)

    rows.append([
        cid, nombre, email, telefono, edad, salario, ciudad,
        estado, freg_str, fuc_str, monto, categoria, nit, pais, score,
    ])

# ── Write CSV ────────────────────────────────────────────────────────

HEADERS = [
    "cliente_id", "nombre", "email", "telefono", "edad", "salario", "ciudad",
    "estado_cliente", "fecha_registro", "fecha_ultima_compra",
    "monto_ultima_compra", "categoria_cliente", "nit_empresa", "pais",
    "score_credito",
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(HEADERS)
    writer.writerows(rows)

# ── Summary ──────────────────────────────────────────────────────────

print(f"\n{'─'*55}")
print(f"  Dataset generado: {OUTPUT.name}  ({N} registros)")
print(f"{'─'*55}")
problems = {
    "cliente_id  (duplicados)":        len(dup_positions),
    "nombre      (nulos)":             len(nombre_null),
    "email       (formato inválido)":  len(email_invalid),
    "telefono    (formato inválido)":  len(tel_invalid),
    "edad        (fuera de rango)":    len(edad_bad),
    "salario     (outliers)":          len(sal_outlier),
    "ciudad      (valor inválido)":    len(ciudad_invalid),
    "estado      (valor inválido)":    len(estado_invalid),
    "fecha_reg   (antiguas/mal fmt)":  len(freg_bad),
    "fecha_compra(nulas/inconsist.)":  len(fuc_null) + len(fuc_inconsistent),
    "monto_compra(nulos/negativos)":   len(monto_null) + len(monto_neg),
    "categoria   (nulos/inválidos)":   len(cat_null) + len(cat_invalid),
    "nit_empresa (dups/mal formato)":  len(nit_dup_pos) + len(nit_bad_fmt),
    "pais        (valor inválido)":    len(pais_invalid),
    "score_cred  (fuera de rango)":    len(score_bad),
}
total = 0
for col, cnt in problems.items():
    print(f"  {col:<40} {cnt:>4} problemas")
    total += cnt
print(f"{'─'*55}")
print(f"  Total de problemas inyectados:         {total:>4}")
print(f"{'─'*55}\n")
