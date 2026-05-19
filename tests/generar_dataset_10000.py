"""
Generador de dataset de prueba con 10,000 registros en formato TSV.
Incluye problemas de calidad de datos distribuidos aleatoriamente.
"""
import random
import string
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

OUTPUT = Path(__file__).resolve().parent / "dataset_10000.txt"
N = 10_000

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def random_date(start: date, end: date) -> str:
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")

def pick(seq):
    return random.choice(seq)

# ─────────────────────────────────────────────────────────────────────────────
# Catálogos base
# ─────────────────────────────────────────────────────────────────────────────

NOMBRES = [
    "Ana Torres", "Luis Mendoza", "Carlos Ramírez", "María López", "Pedro Gómez",
    "Laura Sánchez", "Andrés Martínez", "Sofía Herrera", "Diego Flores", "Valentina Díaz",
    "Camilo Ruiz", "Isabella Castro", "Juan Vargas", "Natalia Moreno", "Sebastián Jiménez",
    "Daniela Pérez", "Felipe Ortiz", "Alejandra Ramos", "Santiago Rojas", "Paola Guerrero",
    "Gustavo Medina", "Claudia Ríos", "Hernán Molina", "Gloria Suárez", "Roberto Parra",
    "Mónica Delgado", "Ernesto Aguilar", "Patricia Vera", "Mauricio Reyes", "Liliana Cruz",
]

DOMINIOS = ["gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "empresa.co",
            "correo.co", "mail.com", "protonmail.com"]

CIUDADES_VALIDAS = ["Bogotá", "Medellín", "Cali", "Barranquilla",
                    "Cartagena", "Bucaramanga", "Cúcuta", "Manizales"]

CIUDADES_INVALIDAS = [
    "bogota", "BOGOTÁ", "Bogota", "medellin", "MEDELLIN", "Medelín",
    "cali ", "CALI", " Barranquilla", "Cartagéna", "Bucaramanga ",
    "cucuta", "CUCUTA", "Manizáles", "bogotá", "Medllin", "Calí",
    "Barranqilla", "Cartágena", "Bucaramanga2", "MAnizales",
]

ESTADOS_VALIDOS = ["Activo", "Inactivo", "Suspendido"]
ESTADOS_INVALIDOS = ["activo", "ACTIVO", "inactivo", "INACTIVO", "suspendido",
                     "Activo ", " Inactivo", "Pendiente", "Bloqueado", "Eliminado",
                     "N/A", "NULL", "actIvo", "InActivo", "SUSPENDIDO"]

CATEGORIAS_VALIDAS = ["Premium", "Estándar", "Básico"]
CATEGORIAS_INVALIDAS = ["premium", "PREMIUM", "estandar", "ESTÁNDAR", "basico",
                        "BÁSICO", "Gold", "Silver", "Bronze", "VIP",
                        "Standard", "Basic", "Premiums", "Estandard"]

PAISES_VALIDOS = ["Colombia", "Venezuela", "Ecuador", "Perú", "México"]
PAISES_INVALIDOS = ["colombia", "COLOMBIA", "Venezuela ", "ecuador", "PERU",
                    "mexico", "Brasil", "Argentina", "Chile", "Bolivia",
                    "Perú ", " México", "ECUADOR", "Venezolana", "Colombiano"]

TIPOS_VALIDOS = ["Natural", "Jurídico"]
TIPOS_INVALIDOS = ["natural", "NATURAL", "juridico", "JURÍDICO", "Persona",
                   "Empresa", "N/A", "natural ", "Jurídiico", "Naturál"]

CANALES_VALIDOS = ["Online", "Referido", "Directo", "Agencia"]

REGIONES_VALIDAS = ["Norte", "Sur", "Centro", "Oriente", "Occidente"]
REGIONES_INVALIDAS = ["norte", "NORTE", "sur", "SUR", "centro", "CENTRO",
                      "oriente", "ORIENTE", "occidente", "OCCIDENTE",
                      "Nordeste", "Sureste", "Central", "Este", "Oeste",
                      "N/A", "norte ", " Sur", "Centro ", "Nort"]

# ─────────────────────────────────────────────────────────────────────────────
# Generadores por columna
# ─────────────────────────────────────────────────────────────────────────────

def gen_nombre(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        return ""
    return pick(NOMBRES)

def gen_email(idx: int, bad_set: set) -> str:
    user = "".join(random.choices(string.ascii_lowercase, k=random.randint(4, 10)))
    if idx in bad_set:
        # Sin arroba o sin punto
        kind = random.randint(0, 2)
        if kind == 0:
            return f"{user}dominio.com"          # sin @
        elif kind == 1:
            return f"{user}@dominioCom"          # sin punto
        else:
            return f"{user}dominioCom"           # sin @ ni punto
    return f"{user}@{pick(DOMINIOS)}"

def gen_telefono(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        kind = random.randint(0, 3)
        if kind == 0:
            return "".join(random.choices(string.ascii_letters, k=10))
        elif kind == 1:
            return f"+57 {random.randint(300,320)}-{''.join(random.choices(string.digits, k=3))}-ABCD"
        elif kind == 2:
            return f"{''.join(random.choices(string.digits, k=5))}XXXXX"
        else:
            return "N/A"
    return "".join(random.choices(string.digits, k=10))

def gen_edad(idx: int, neg_set: set, high_set: set) -> str:
    if idx in neg_set:
        return str(random.randint(-50, -1))
    if idx in high_set:
        return str(random.randint(121, 200))
    return str(random.randint(18, 75))

def gen_salario(idx: int, outlier_set: set) -> str:
    if idx in outlier_set:
        kind = random.randint(0, 1)
        if kind == 0:
            return f"{random.uniform(50000, 999999):.2f}"
        else:
            return f"{random.uniform(-5000, -1):.2f}"
    return f"{random.uniform(1500, 8000):.2f}"

def gen_ciudad(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        return pick(CIUDADES_INVALIDAS)
    return pick(CIUDADES_VALIDAS)

def gen_estado(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        return pick(ESTADOS_INVALIDOS)
    return pick(ESTADOS_VALIDOS)

def gen_fecha_registro(idx: int, old_set: set, fmt_set: set) -> str:
    if idx in fmt_set:
        # Formato incorrecto
        d = random.randint(1, 28)
        m = random.randint(1, 12)
        y = random.randint(2020, 2024)
        kind = random.randint(0, 3)
        if kind == 0:
            return f"{d:02d}/{m:02d}/{y}"
        elif kind == 1:
            return f"{m:02d}-{d:02d}-{y}"
        elif kind == 2:
            return f"{y}{m:02d}{d:02d}"
        else:
            return f"{d:02d}.{m:02d}.{y}"
    if idx in old_set:
        return random_date(date(2010, 1, 1), date(2010, 12, 31))
    return random_date(date(2020, 1, 1), date(2024, 12, 31))

def gen_fecha_ultima_compra(idx: int, null_set: set) -> str:
    if idx in null_set:
        return ""
    return random_date(date(2022, 1, 1), date(2024, 12, 31))

def gen_monto(idx: int, null_set: set, neg_set: set) -> str:
    if idx in null_set:
        return ""
    if idx in neg_set:
        return f"{random.uniform(-500, -1):.2f}"
    return f"{random.uniform(10, 5000):.2f}"

def gen_categoria(idx: int, null_set: set, bad_set: set) -> str:
    if idx in null_set:
        return ""
    if idx in bad_set:
        return pick(CATEGORIAS_INVALIDAS)
    return pick(CATEGORIAS_VALIDAS)

def gen_nit(idx: int, dup_map: dict, bad_set: set) -> str:
    if idx in bad_set:
        kind = random.randint(0, 2)
        if kind == 0:
            return "".join(random.choices(string.ascii_letters + string.digits, k=9))
        elif kind == 1:
            return f"{''.join(random.choices(string.digits, k=5))}-{''.join(random.choices(string.digits, k=4))}"
        else:
            return "".join(random.choices(string.digits, k=random.randint(4, 7)))
    if idx in dup_map:
        return dup_map[idx]
    return "".join(random.choices(string.digits, k=9))

def gen_pais(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        return pick(PAISES_INVALIDOS)
    return pick(PAISES_VALIDOS)

def gen_score(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        kind = random.randint(0, 1)
        if kind == 0:
            return str(random.randint(-200, 0))
        else:
            return str(random.randint(1000, 2000))
    return str(random.randint(300, 850))

def gen_tipo(idx: int, null_set: set, bad_set: set) -> str:
    if idx in null_set:
        return ""
    if idx in bad_set:
        return pick(TIPOS_INVALIDOS)
    return pick(TIPOS_VALIDOS)

def gen_canal(idx: int, null_set: set) -> str:
    if idx in null_set:
        return ""
    return pick(CANALES_VALIDOS)

def gen_compras(idx: int, neg_set: set) -> str:
    if idx in neg_set:
        return str(random.randint(-20, -1))
    return str(random.randint(1, 50))

def gen_dias(idx: int, outlier_set: set) -> str:
    if idx in outlier_set:
        return str(random.randint(1001, 3000))
    return str(random.randint(1, 365))

def gen_region(idx: int, bad_set: set) -> str:
    if idx in bad_set:
        return pick(REGIONES_INVALIDAS)
    return pick(REGIONES_VALIDAS)

# ─────────────────────────────────────────────────────────────────────────────
# Índices de problemas (muestras sin reemplazo, distribuidas aleatoriamente)
# ─────────────────────────────────────────────────────────────────────────────

all_idx = list(range(N))

def sample(n: int, exclude: set = None) -> set:
    pool = [i for i in all_idx if exclude is None or i not in exclude]
    return set(random.sample(pool, n))

# cliente_id duplicados: 10 IDs se repiten
DUP_IDS = [50, 150, 300, 450, 600, 750, 900, 1200, 1500, 2000]
# Posiciones donde insertar duplicados (evitar las posiciones originales)
dup_positions = sample(len(DUP_IDS), exclude=set(DUP_IDS))

nombre_null       = sample(80)
email_bad         = sample(120)
tel_bad           = sample(90)
edad_neg          = sample(50)
edad_high         = sample(30, exclude=edad_neg)
salario_outlier   = sample(60)
ciudad_bad        = sample(100)
estado_bad        = sample(80)
fecha_old         = sample(60)
fecha_fmt         = sample(40, exclude=fecha_old)
fuc_null          = sample(150)
monto_null        = sample(150)
monto_neg         = sample(40, exclude=monto_null)
cat_null          = sample(60)
cat_bad           = sample(40, exclude=cat_null)
pais_bad          = sample(30)
score_bad         = sample(70)
tipo_null         = sample(40)
tipo_bad          = sample(30, exclude=tipo_null)
canal_null        = sample(50)
compras_neg       = sample(20)
dias_outlier      = sample(25)
region_bad        = sample(45)

# NIT: 80 duplicados y 50 formatos incorrectos
nit_dup_source = [random.randint(100000000, 999999999) for _ in range(40)]
nit_dup_positions = sample(80)
nit_dup_map = {idx: str(nit_dup_source[i % 40]) for i, idx in enumerate(sorted(nit_dup_positions))}
nit_bad = sample(50, exclude=nit_dup_positions)

# ─────────────────────────────────────────────────────────────────────────────
# Construcción del dataset
# ─────────────────────────────────────────────────────────────────────────────

COLUMNS = [
    "cliente_id", "nombre", "email", "telefono", "edad", "salario",
    "ciudad", "estado_cliente", "fecha_registro", "fecha_ultima_compra",
    "monto_ultima_compra", "categoria_cliente", "nit_empresa", "pais",
    "score_credito", "tipo_cliente", "canal_adquisicion", "numero_compras",
    "dias_ultimo_contacto", "region",
]

# IDs base: 1..N; reemplazar posiciones dup con los IDs duplicados
base_ids = list(range(1, N + 1))
for pos, dup_id in zip(sorted(dup_positions), DUP_IDS):
    base_ids[pos] = dup_id

rows = []
for i in range(N):
    cid   = base_ids[i]
    nom   = gen_nombre(i, nombre_null)
    mail  = gen_email(i, email_bad)
    tel   = gen_telefono(i, tel_bad)
    edad  = gen_edad(i, edad_neg, edad_high)
    sal   = gen_salario(i, salario_outlier)
    ciu   = gen_ciudad(i, ciudad_bad)
    est   = gen_estado(i, estado_bad)
    freg  = gen_fecha_registro(i, fecha_old, fecha_fmt)
    fuc   = gen_fecha_ultima_compra(i, fuc_null)
    mto   = gen_monto(i, monto_null, monto_neg)
    cat   = gen_categoria(i, cat_null, cat_bad)
    nit   = gen_nit(i, nit_dup_map, nit_bad)
    pais  = gen_pais(i, pais_bad)
    score = gen_score(i, score_bad)
    tipo  = gen_tipo(i, tipo_null, tipo_bad)
    canal = gen_canal(i, canal_null)
    comp  = gen_compras(i, compras_neg)
    dias  = gen_dias(i, dias_outlier)
    reg   = gen_region(i, region_bad)

    rows.append("\t".join(str(v) for v in [
        cid, nom, mail, tel, edad, sal,
        ciu, est, freg, fuc,
        mto, cat, nit, pais,
        score, tipo, canal, comp,
        dias, reg,
    ]))

# ─────────────────────────────────────────────────────────────────────────────
# Escritura del archivo
# ─────────────────────────────────────────────────────────────────────────────

with open(OUTPUT, "w", encoding="utf-8") as f:
    f.write("\t".join(COLUMNS) + "\n")
    f.write("\n".join(rows) + "\n")

# ─────────────────────────────────────────────────────────────────────────────
# Resumen de problemas insertados
# ─────────────────────────────────────────────────────────────────────────────

print(f"\n{'='*55}")
print(f"  Dataset generado: {OUTPUT.name}")
print(f"  Registros: {N:,}")
print(f"{'='*55}")
print(f"  {'Columna':<28} {'Problemas':>10}  Tipo")
print(f"  {'-'*52}")
resumen = [
    ("cliente_id",          len(DUP_IDS),              "IDs duplicados"),
    ("nombre",              len(nombre_null),           "valores nulos"),
    ("email",               len(email_bad),             "formatos inválidos"),
    ("telefono",            len(tel_bad),               "formatos incorrectos"),
    ("edad",                len(edad_neg)+len(edad_high),"negativos + >120"),
    ("salario",             len(salario_outlier),       "outliers extremos"),
    ("ciudad",              len(ciudad_bad),            "variantes/errores"),
    ("estado_cliente",      len(estado_bad),            "valores inválidos"),
    ("fecha_registro",      len(fecha_old)+len(fecha_fmt),"antiguas + formato incorrecto"),
    ("fecha_ultima_compra", len(fuc_null),              "valores nulos"),
    ("monto_ultima_compra", len(monto_null)+len(monto_neg),"nulos + negativos"),
    ("categoria_cliente",   len(cat_null)+len(cat_bad), "nulos + inválidos"),
    ("nit_empresa",         len(nit_dup_map)+len(nit_bad),"duplicados + formato incorrecto"),
    ("pais",                len(pais_bad),              "valores inválidos"),
    ("score_credito",       len(score_bad),             "fuera de rango"),
    ("tipo_cliente",        len(tipo_null)+len(tipo_bad),"nulos + inválidos"),
    ("canal_adquisicion",   len(canal_null),            "valores nulos"),
    ("numero_compras",      len(compras_neg),           "valores negativos"),
    ("dias_ultimo_contacto",len(dias_outlier),          "outliers >1000"),
    ("region",              len(region_bad),            "valores inválidos"),
]
total = 0
for col, n_prob, tipo in resumen:
    print(f"  {col:<28} {n_prob:>10}  {tipo}")
    total += n_prob
print(f"  {'-'*52}")
print(f"  {'TOTAL problemas':<28} {total:>10}")
print(f"{'='*55}\n")
