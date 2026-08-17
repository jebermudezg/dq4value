"""
Genera tests/maestro_clientes_500.xlsx con issues intencionales para la prueba
del ciclo de remediación end-to-end.

Issues sembrados:
  Similitud  - 18 grupos de duplicados difusos (razon_social con variantes tipográficas)
  Unicidad   - 4 cliente_id duplicados; 6 numero_documento duplicados
  Completitud- ~8% valores nulos distribuidos en varias columnas
  Catálogo   - departamento: variantes LIMA, Lima Metropolitana, "N/A"
               segmento: "Corp.", "Med. empresa", "PyME"
               estado: "activo", "ACTIVO", "Cancelado"
  Formato    - email: 15 sin @, con doble punto, sin dominio
  Consistencia- telefono: mix 9-dígito / +51 / 51-xxx-xxx / (01)xxx
               fecha_alta: ~20 en formato DD/MM/YYYY vs YYYY-MM-DD mayoritario
  Vigencia   - 8 fecha_alta < 2015-01-01
               5 fecha_ultima_compra < 2019-01-01
               3 fecha_ultima_compra > hoy
  Precisión  - numero_documento: 4 con 7 dígitos, 3 con 12 dígitos
  Exactitud  - linea_credito_pen: 5 negativos, 3 > 2,000,000
  Razonabilidad- 4 valores muy extremos (>IQR*3)
"""
import random, re
import pandas as pd
import numpy as np
from datetime import date, timedelta

random.seed(42)
np.random.seed(42)

DEPARTAMENTOS = ['Lima', 'Arequipa', 'La Libertad', 'Piura', 'Cusco',
                 'Lambayeque', 'Junín', 'Ancash', 'Ica', 'Tacna']
SEGMENTOS     = ['Corporativo', 'Mediana empresa', 'Pequeña empresa', 'Persona natural']
ESTADOS       = ['Activo', 'Inactivo', 'Suspendido']
DISTRITOS     = ['Miraflores','San Isidro','La Molina','Surco','Barranco',
                 'Lince','Pueblo Libre','Jesús María','San Borja','Chorrillos',
                 'Cayma','Yanahuara','Cerro Colorado','Hunter','Trujillo','Víctor Larco',
                 'Chiclayo','La Victoria','Piura','Castilla','Cusco','San Sebastián',
                 'Huancayo','El Tambo','Wanchaq','Chimbote','Nuevo Chimbote','Ica']
DOMINIOS      = ['gmail.com','hotmail.com','empresa.pe','correo.com','yahoo.com','outlook.com']
NOMBRES       = ['Carlos','María','José','Ana','Luis','Rosa','Juan','Carmen','Pedro','Laura',
                 'Miguel','Patricia','Ricardo','Sandra','Roberto','Isabel','Fernando','Silvia']
APELLIDOS     = ['García','López','Martínez','Rodríguez','Pérez','Sánchez','Torres','Flores',
                 'Rivera','Gómez','Díaz','Morales','Vargas','Castro','Reyes','Cruz']

def rand_empresa():
    tipos = ['S.A.C.','S.A.','E.I.R.L.','S.R.L.','S.A.C']
    industrias = ['Importaciones','Exportaciones','Inversiones','Servicios','Tecnología',
                  'Soluciones','Distribuciones','Comercializadora','Grupo','Consorcio',
                  'Constructora','Representaciones']
    nombres_base = ['Andina','Peruana','Continental','Nacional','Global','Andean',
                    'Pacífico','Horizonte','Estrella','Cóndor','Andes','Miraflores',
                    'Lima','Arequipa','Sur','Norte','Centro','Unida','Moderna','Nueva']
    return f"{random.choice(nombres_base)} {random.choice(industrias)} {random.choice(tipos)}"

def rand_ruc():
    return str(random.randint(10_000_000_0, 99_999_999_9))

def rand_dni():
    return str(random.randint(10_000_000, 99_999_999))

def rand_doc():
    return rand_ruc() if random.random() < 0.6 else rand_dni()

def rand_email(nombre):
    local = nombre.lower().replace(' ', '.') + str(random.randint(1, 99))
    return f"{local}@{random.choice(DOMINIOS)}"

def rand_telefono_clean():
    return f"9{random.randint(10_000_000, 99_999_999)}"

def rand_date(start, end):
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))

start_alta    = date(2015, 1, 1)
end_alta      = date(2024, 12, 31)
start_compra  = date(2019, 1, 1)
end_compra    = date(2025, 6, 30)

# ─── Generate 500 base rows ──────────────────────────────────────────────────
N = 500
rows = []
for i in range(N):
    nombre = f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"
    empresa = rand_empresa()
    doc = rand_doc()
    dep = random.choice(DEPARTAMENTOS)
    fa = rand_date(start_alta, end_alta)
    fc = rand_date(max(start_compra, fa), end_compra)
    linea = round(random.expovariate(1/80_000), 2)
    linea = min(linea, 1_800_000)
    rows.append({
        'cliente_id':          i + 1,
        'razon_social':        empresa,
        'numero_documento':    doc,
        'nombre_contacto':     nombre,
        'distrito':            random.choice(DISTRITOS),
        'email':               rand_email(nombre),
        'telefono':            rand_telefono_clean(),
        'departamento':        dep,
        'segmento':            random.choice(SEGMENTOS),
        'estado':              random.choice(ESTADOS),
        'fecha_alta':          fa.isoformat(),
        'fecha_ultima_compra': fc.isoformat(),
        'linea_credito_pen':   linea,
    })

df = pd.DataFrame(rows)

# ─── Sembrar issues ──────────────────────────────────────────────────────────

# 1. Duplicados difusos en razon_social (18 grupos, 2-3 miembros c/u → ~35 filas afectadas)
variantes = {
    'Andina Importaciones S.A.C.': [
        'Andina Importaciones S.A.C',       # falta punto
        'Andina Importaciones SAC',          # sin puntos
        'ANDINA IMPORTACIONES S.A.C.',       # mayúsculas
    ],
    'Peruana Exportaciones S.A.': [
        'Peruana Exportaciones SA',
        'Peruana Exportaciones S.A',
    ],
    'Continental Tecnología E.I.R.L.': [
        'Continental Tecnologia E.I.R.L.',  # sin tilde
        'Continetal Tecnología E.I.R.L.',   # typo
    ],
    'Global Servicios S.R.L.': [
        'Global Servicios SRL',
        'Global Servicios S.R.L',
    ],
    'Nacional Inversiones S.A.C.': [
        'Nacional Inversiones SAC',
        'NACIONAL INVERSIONES S.A.C.',
    ],
    'Pacífico Distribuciones S.A.C.': [
        'Pacifico Distribuciones S.A.C.',   # sin tilde
        'Pacífico Distribuciones SAC',
    ],
    'Andean Soluciones S.A.C.': [
        'Andean Soluciones SAC',
        'Andean Solucioness S.A.C.',         # typo doble s
    ],
    'Lima Constructora S.A.': [
        'Lima Constructora SA',
        'Lima Cosntructora S.A.',            # typo
    ],
    'Sur Comercializadora E.I.R.L.': [
        'Sur Comercializadora EIRL',
        'Sur Comercializadora E.I.R.L',
    ],
    'Norte Representaciones S.A.C.': [
        'Norte Representaciones SAC',
        'Norte Representacones S.A.C.',      # typo
    ],
    'Centro Grupo S.R.L.': [
        'Centro Grupo SRL',
        'Cento Grupo S.R.L.',               # typo
    ],
    'Moderna Inversiones S.A.C.': [
        'Moderna Inversiones SAC',
        'Modena Inversiones S.A.C.',        # typo
    ],
    'Horizonte Tecnología S.A.': [
        'Horizonte Tecnologia S.A.',        # sin tilde
        'Horizonte Tecnología SA',
    ],
    'Estrella Servicios E.I.R.L.': [
        'Estrella Servicios EIRL',
    ],
    'Cóndor Exportaciones S.A.C.': [
        'Condor Exportaciones S.A.C.',      # sin tilde
        'Cóndor Exportaciones SAC',
    ],
    'Andes Importaciones S.R.L.': [
        'Andes Importaciones SRL',
    ],
    'Miraflores Inversiones S.A.C.': [
        'Miraflores Inversiones SAC',
        'Miraflres Inversiones S.A.C.',     # typo
    ],
    'Nueva Distribuciones E.I.R.L.': [
        'Nueva Distribuciones EIRL',
        'Nueva Distribuciones E.I.R.L',
    ],
}

# Assign duplicate groups to existing rows
dup_idx = random.sample(range(N), sum(1 + len(v) for v in variantes.values()))
ptr = 0
for canonical, variants_list in variantes.items():
    total = 1 + len(variants_list)
    group_idxs = dup_idx[ptr:ptr+total]
    ptr += total
    all_names = [canonical] + variants_list
    for gi, ni in zip(group_idxs, all_names):
        df.at[gi, 'razon_social'] = ni

# 2. Duplicados de cliente_id (4 pares)
dup_id_rows = random.sample(range(N), 8)
for i in range(0, 8, 2):
    df.at[dup_id_rows[i+1], 'cliente_id'] = df.at[dup_id_rows[i], 'cliente_id']

# 3. Duplicados de numero_documento (6 pares)
dup_doc_rows = random.sample(range(N), 12)
for i in range(0, 12, 2):
    df.at[dup_doc_rows[i+1], 'numero_documento'] = df.at[dup_doc_rows[i], 'numero_documento']

# 4. Completitud: nulos en varias columnas (~8%)
cols_nulos = {
    'razon_social': 3, 'nombre_contacto': 8, 'distrito': 6,
    'email': 10, 'telefono': 12, 'linea_credito_pen': 5,
    'fecha_ultima_compra': 7, 'numero_documento': 4,
}
for col, n in cols_nulos.items():
    idxs = random.sample(range(N), n)
    df.loc[idxs, col] = None

# 5. Catálogo departamento: variantes inválidas
dep_bad = {
    'LIMA': 12,
    'Lima Metropolitana': 8,
    'N/A': 5,
    'Arequipa ': 4,    # trailing space (evil)
    '--': 3,
}
dep_pool = df[df['departamento'].notna()].index.tolist()
random.shuffle(dep_pool)
ptr = 0
for val, cnt in dep_bad.items():
    for ix in dep_pool[ptr:ptr+cnt]:
        df.at[ix, 'departamento'] = val
    ptr += cnt

# 6. Catálogo segmento: variantes inválidas
seg_bad = {'Corp.': 8, 'Med. empresa': 6, 'PyME': 5, 'pyme': 4, 'CORPORATIVO': 5}
seg_pool = df[df['segmento'].notna()].index.tolist()
random.shuffle(seg_pool)
ptr = 0
for val, cnt in seg_bad.items():
    for ix in seg_pool[ptr:ptr+cnt]:
        df.at[ix, 'segmento'] = val
    ptr += cnt

# 7. Catálogo estado: variantes
est_bad = {'activo': 8, 'ACTIVO': 5, 'Cancelado': 6, 'inactivo': 7, 'suspendido': 4}
est_pool = df.index.tolist()
random.shuffle(est_pool)
ptr = 0
for val, cnt in est_bad.items():
    for ix in est_pool[ptr:ptr+cnt]:
        df.at[ix, 'estado'] = val
    ptr += cnt

# 8. Email inválidos: sin @, doble punto, sin dominio
email_bad_idxs = random.sample(df[df['email'].notna()].index.tolist(), 15)
email_bads = [
    lambda e: e.replace('@', ''),              # sin @
    lambda e: e.replace('.', '..', 1),         # doble punto
    lambda e: e.split('@')[0] + '@',           # sin dominio
    lambda e: e.replace('@', ' @ '),           # espacios
    lambda e: e + '..',                        # doble punto al final
]
for i, ix in enumerate(email_bad_idxs):
    df.at[ix, 'email'] = email_bads[i % len(email_bads)](str(df.at[ix, 'email']))

# 9. Teléfonos: formatos mezclados
tel_idxs = df[df['telefono'].notna()].index.tolist()
random.shuffle(tel_idxs)
# 20 con prefijo +51
for ix in tel_idxs[:20]:
    df.at[ix, 'telefono'] = '+51' + str(df.at[ix, 'telefono'])
# 15 con 51-
for ix in tel_idxs[20:35]:
    t = str(df.at[ix, 'telefono'])
    df.at[ix, 'telefono'] = f"51-{t[:3]}-{t[3:]}"
# 10 con (01)
for ix in tel_idxs[35:45]:
    t = str(df.at[ix, 'telefono'])
    df.at[ix, 'telefono'] = f"(01){t}"
# 8 con guiones internos
for ix in tel_idxs[45:53]:
    t = str(df.at[ix, 'telefono'])
    df.at[ix, 'telefono'] = f"{t[:3]}-{t[3:6]}-{t[6:]}"

# 10. Fechas: ~20 en DD/MM/YYYY
date_pool = df[df['fecha_alta'].notna()].index.tolist()
random.shuffle(date_pool)
for ix in date_pool[:20]:
    d = df.at[ix, 'fecha_alta']
    if d and isinstance(d, str) and '-' in d:
        parts = d.split('-')
        if len(parts) == 3:
            df.at[ix, 'fecha_alta'] = f"{parts[2]}/{parts[1]}/{parts[0]}"

# 11. fecha_alta antes de 2015 (8 filas)
early_pool = df[df['fecha_alta'].notna()].index.tolist()
early_idxs = random.sample(early_pool, 8)
for ix in early_idxs:
    old_date = rand_date(date(2010, 1, 1), date(2014, 12, 31))
    df.at[ix, 'fecha_alta'] = old_date.isoformat()

# 12. fecha_ultima_compra antes de 2019 (5 filas)
compra_pool = df[df['fecha_ultima_compra'].notna()].index.tolist()
old_compra_idxs = random.sample(compra_pool, 5)
for ix in old_compra_idxs:
    df.at[ix, 'fecha_ultima_compra'] = rand_date(date(2016, 1, 1), date(2018, 12, 31)).isoformat()

# 13. fecha_ultima_compra en el futuro (3 filas)
future_idxs = random.sample(compra_pool, 3)
for ix in future_idxs:
    df.at[ix, 'fecha_ultima_compra'] = rand_date(date(2026, 1, 1), date(2027, 12, 31)).isoformat()

# 14. numero_documento con longitud incorrecta: 4 de 7 dígitos, 3 de 12
doc_pool = df[df['numero_documento'].notna()].index.tolist()
random.shuffle(doc_pool)
for ix in doc_pool[:4]:
    df.at[ix, 'numero_documento'] = str(random.randint(1_000_000, 9_999_999))  # 7 dígitos
for ix in doc_pool[4:7]:
    df.at[ix, 'numero_documento'] = str(random.randint(100_000_000_000, 999_999_999_999))  # 12

# 15. linea_credito_pen: 5 negativos, 3 > 2,000,000, 4 extremos
linea_pool = df[df['linea_credito_pen'].notna()].index.tolist()
random.shuffle(linea_pool)
for ix in linea_pool[:5]:
    df.at[ix, 'linea_credito_pen'] = -round(random.uniform(1000, 50000), 2)
for ix in linea_pool[5:8]:
    df.at[ix, 'linea_credito_pen'] = round(random.uniform(2_100_000, 5_000_000), 2)
for ix in linea_pool[8:12]:
    df.at[ix, 'linea_credito_pen'] = round(random.uniform(1_500_000, 1_900_000), 2)  # extremos altos (IQR)

df.to_excel('tests/maestro_clientes_500.xlsx', index=False)
print(f"✅ tests/maestro_clientes_500.xlsx generado ({len(df)} filas, {len(df.columns)} cols)")

# Resumen de issues sembrados
print("\nIssues sembrados:")
print(f"  Similitud   : ~{sum(1+len(v) for v in variantes.values())} filas en {len(variantes)} grupos difusos")
print(f"  ID dupl.    : {len(dup_id_rows)//2} pares")
print(f"  Doc dupl.   : {len(dup_doc_rows)//2} pares")
print(f"  Nulos total : {df.isnull().sum().sum()}")
print(f"  Dep. inval. : {sum(dep_bad.values())}")
print(f"  Seg. inval. : {sum(seg_bad.values())}")
print(f"  Est. inval. : {sum(est_bad.values())}")
print(f"  Email inval.: 15")
print(f"  Tel. format : ~53 con prefijos/separadores")
print(f"  Fechas DD/MM: 20")
print(f"  Fecha < 2015: 8")
print(f"  Compra < 2019: 5")
print(f"  Compra futura: 3")
print(f"  Doc 7 dígitos: 4 | 12 dígitos: 3")
print(f"  Línea negativa: 5 | > 2M: 3 | extremos: 4")
