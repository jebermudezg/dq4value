"""
engine/dashboard_gen.py
Generates a standalone HTML dashboard from DQ analysis results.
"""
import json
import math
from datetime import datetime


# ──────────────────────────────────────────────────────────────────────
# Colour helpers
# ──────────────────────────────────────────────────────────────────────

def _color(score: float) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 60:
        return "#ca8a04"
    return "#dc2626"


def _bg(score: float) -> str:
    if score >= 80:
        return "#dcfce7"
    if score >= 60:
        return "#fef9c3"
    return "#fee2e2"


def _label(score: float) -> str:
    if score >= 80:
        return "Buena calidad"
    if score >= 60:
        return "Requiere atención"
    return "Calidad crítica"


# ──────────────────────────────────────────────────────────────────────
# Gauge SVG
# ──────────────────────────────────────────────────────────────────────

def _gauge_path(score: float, cx: int = 100, cy: int = 100, r: int = 75) -> str:
    """
    Returns the SVG 'd' attribute for the score arc.
    Arc goes from (cx-r, cy) clockwise through the top to the score position.
    sweep=1 (positive angle direction) traces left → top → right.
    """
    s = max(0.0, min(float(score), 99.9))
    if s <= 0:
        return ""
    angle_rad = math.radians(180.0 + s * 1.8)
    end_x = cx + r * math.cos(angle_rad)
    end_y = cy + r * math.sin(angle_rad)
    return "M %d %d A %d %d 0 0 1 %.1f %.1f" % (cx - r, cy, r, r, end_x, end_y)


# ──────────────────────────────────────────────────────────────────────
# Natural language interpretation
# ──────────────────────────────────────────────────────────────────────

_DIM_DESCRIPTIONS = {
    "completitud":   "campos con valores nulos o vacíos",
    "unicidad":      "registros duplicados",
    "validez":       "valores fuera de catálogo o con formato incorrecto",
    "exactitud":     "valores fuera del rango numérico esperado",
    "consistencia":  "inconsistencias de formato (mayúsculas, espacios)",
    "similitud":     "registros con nombres muy parecidos que pueden ser duplicados semánticos",
    "razonabilidad": "valores estadísticamente anómalos",
    "vigencia":      "fechas fuera del rango temporal configurado",
    "precision":     "valores que no cumplen los criterios de longitud",
}


def _interpretation(score: float, peor_dim: str) -> str:
    desc = _DIM_DESCRIPTIONS.get(peor_dim, "problemas en la dimensión " + peor_dim)
    if score >= 80:
        return (
            "El dataset presenta <strong>buena calidad general</strong>. "
            "La dimensión con mayor oportunidad de mejora es <strong>%s</strong>, "
            "que detectó %s. Se recomienda monitoreo rutinario y revisión periódica."
            % (peor_dim, desc)
        )
    if score >= 60:
        return (
            "El dataset <strong>requiere atención</strong> antes de usarse en producción. "
            "El área más crítica es <strong>%s</strong>, que presenta %s. "
            "Revisa y corrige estos problemas antes de cualquier análisis."
            % (peor_dim, desc)
        )
    return (
        "El dataset presenta <strong>calidad crítica</strong>. "
        "El principal problema está en <strong>%s</strong>, con %s. "
        "<strong>No se recomienda usar estos datos</strong> en decisiones "
        "hasta completar la limpieza."
        % (peor_dim, desc)
    )


# ──────────────────────────────────────────────────────────────────────
# Section builders (return plain HTML strings, no f-strings needed)
# ──────────────────────────────────────────────────────────────────────

def _dim_bars(dims_sorted: list) -> str:
    html = ""
    for dim, s in dims_sorted:
        c = _color(s)
        html += (
            '<div style="margin-bottom:.75rem">'
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;margin-bottom:.3rem">'
            '<span style="font-size:.82rem;font-weight:600;color:#374151;'
            'text-transform:capitalize">%s</span>'
            '<span style="font-size:.82rem;font-weight:700;color:%s">%.1f%%</span>'
            '</div>'
            '<div style="background:#e2e8f0;border-radius:999px;height:10px;overflow:hidden">'
            '<div style="background:%s;height:100%%;width:%.1f%%;'
            'border-radius:999px"></div></div></div>'
            % (dim, c, s, c, s)
        )
    return html


def _kpi_grid(total_reg, total_prob, pct_limpios, peor_dim, scores_per_dim) -> str:
    clean = total_reg - total_prob
    c_pct = _color(pct_limpios)
    peor_score = scores_per_dim.get(peor_dim, 0.0)
    return (
        '<div class="kpi-grid">'
        '<div class="card">'
        '<div class="card-title">Total registros</div>'
        '<div class="card-value">%s</div>'
        '<div class="card-sub">filas analizadas</div>'
        '</div>'
        '<div class="card">'
        '<div class="card-title">Con problemas</div>'
        '<div class="card-value" style="color:#dc2626">%s</div>'
        '<div class="card-sub">registros únicos afectados</div>'
        '</div>'
        '<div class="card">'
        '<div class="card-title">Registros limpios</div>'
        '<div class="card-value" style="color:%s">%.1f%%</div>'
        '<div class="card-sub">%s sin problemas</div>'
        '</div>'
        '<div class="card">'
        '<div class="card-title">Peor dimensión</div>'
        '<div class="card-value" style="font-size:1.1rem;text-transform:capitalize;'
        'color:#dc2626">%s</div>'
        '<div class="card-sub">%.1f%% promedio</div>'
        '</div>'
        '</div>'
        % (
            "{:,}".format(total_reg),
            "{:,}".format(total_prob),
            c_pct, pct_limpios,
            "{:,}".format(clean),
            peor_dim,
            peor_score,
        )
    )


def _col_cards(cols_sorted: list, col_avg: dict) -> str:
    html = '<div class="col-cards-grid">'
    for col, dim_scores in cols_sorted:
        worst = min(dim_scores.values()) if dim_scores else 100.0
        bc = _color(worst)
        avg = round(col_avg[col], 1)
        rows = ""
        for dim, s in sorted(dim_scores.items(), key=lambda x: x[1]):
            c = _color(s)
            rows += (
                '<div style="display:flex;justify-content:space-between;'
                'align-items:center;padding:.3rem 0;border-bottom:1px solid #f1f5f9">'
                '<span style="font-size:.78rem;color:#64748b;text-transform:capitalize">%s</span>'
                '<span style="font-size:.78rem;font-weight:700;color:%s">%.1f%%</span>'
                '</div>'
                % (dim, c, s)
            )
        html += (
            '<div style="background:#fff;border-radius:12px;border:2px solid %s;'
            'padding:1rem;box-shadow:0 1px 3px rgba(0,0,0,.06)">'
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;margin-bottom:.75rem">'
            '<span style="font-weight:700;color:#1e293b;font-size:.9rem">%s</span>'
            '<span style="font-size:.95rem;font-weight:800;color:%s">%.1f%%</span>'
            '</div>%s</div>'
            % (bc, col, bc, avg, rows)
        )
    html += '</div>'
    return html


def _donut_section(issues_per_dim: dict, scores_per_dim: dict) -> str:
    if not issues_per_dim:
        return ""
    labels  = json.dumps([str(k) for k in issues_per_dim.keys()])
    data    = json.dumps(list(issues_per_dim.values()))
    colors  = json.dumps([_color(scores_per_dim.get(k, 50)) for k in issues_per_dim.keys()])

    rows = ""
    for d, c in sorted(issues_per_dim.items(), key=lambda x: -x[1]):
        col = _color(scores_per_dim.get(d, 50))
        rows += (
            '<div style="display:flex;justify-content:space-between;align-items:center;'
            'padding:.4rem 0;border-bottom:1px solid #f8fafc">'
            '<span style="font-size:.82rem;text-transform:capitalize;color:#374151">%s</span>'
            '<span style="font-size:.82rem;font-weight:700;color:%s">%s problemas</span>'
            '</div>'
            % (d, col, "{:,}".format(c))
        )

    chart_script = (
        '<script>'
        '(function(){'
        'var c=document.getElementById("donutChart");'
        'if(!c)return;'
        'new Chart(c.getContext("2d"),{'
        'type:"doughnut",'
        'data:{labels:%s,datasets:[{data:%s,backgroundColor:%s,borderWidth:2,borderColor:"#fff"}]},'
        'options:{plugins:{legend:{position:"bottom",labels:{font:{size:11},padding:12}}},'
        'cutout:"65%%"}'
        '});'
        '})();'
        '</script>'
        % (labels, data, colors)
    )

    return (
        '<div class="grid-2" style="margin-bottom:1.5rem">'
        '<div class="card">'
        '<div class="card-title">Distribución de problemas por dimensión</div>'
        '<canvas id="donutChart" style="max-height:220px"></canvas>'
        + chart_script +
        '</div>'
        '<div class="card">'
        '<div class="card-title">Conteo de problemas por dimensión</div>'
        + rows +
        '</div>'
        '</div>'
    )


_REMEDIATION = {
    "completitud": (
        "🗂", "Campos vacíos o nulos",
        "Identifica los registros con valores faltantes usando la tabla de problemas. "
        "Establece reglas de validación en el proceso de captura para que estos campos sean obligatorios.",
    ),
    "unicidad": (
        "🔁", "Registros duplicados",
        "Revisa los registros reportados como duplicados y decide cuál conservar. "
        "Implementa controles de unicidad en la carga de datos.",
    ),
    "validez": (
        "✅", "Valores fuera de catálogo",
        "Compara los valores encontrados con la lista de valores válidos. "
        "Actualiza el catálogo si el negocio ha cambiado, o corrige los valores erróneos en la fuente.",
    ),
    "exactitud": (
        "📏", "Valores fuera de rango",
        "Revisa los valores que están fuera del rango configurado. "
        "Pueden ser errores de captura o casos excepcionales que ameritan documentación.",
    ),
    "consistencia": (
        "🔤", "Formato inconsistente",
        "Estandariza el formato en la fuente: aplica UPPER() o LOWER() según corresponda, "
        "elimina espacios dobles con TRIM(), y define un estándar de capitalización.",
    ),
    "similitud": (
        "👥", "Posibles duplicados semánticos",
        "Revisa los pares de registros reportados. Consolida los que son el mismo registro "
        "escrito diferente. Ajusta el umbral si hay falsos positivos.",
    ),
    "razonabilidad": (
        "📊", "Valores estadísticamente anómalos",
        "Revisa los outliers detectados. Valida si son errores de captura o casos "
        "legítimos de negocio. Si son legítimos, documéntalos como excepciones conocidas.",
    ),
    "vigencia": (
        "📅", "Fechas fuera de rango",
        "Revisa las fechas reportadas como inválidas. Confirma si el rango configurado "
        "es correcto y corrige o actualiza las fechas erróneas.",
    ),
    "precision": (
        "📐", "Longitud fuera de parámetros",
        "Revisa los valores con longitud incorrecta. Puede indicar truncamiento "
        "en la migración de datos o errores de captura.",
    ),
}


def _remediation_cards(dims_sorted_top3: list, scores_per_dim: dict) -> str:
    html = '<div class="grid-3" style="margin-bottom:1.5rem">'
    for dim, _ in dims_sorted_top3:
        icon, title, tip = _REMEDIATION.get(
            dim, ("⚠️", dim.capitalize(), "Revisa los registros con problemas en la dimensión %s." % dim)
        )
        col = _color(scores_per_dim.get(dim, 0))
        s   = scores_per_dim.get(dim, 0)
        html += (
            '<div style="background:#fff;border-radius:12px;padding:1.25rem;'
            'border-left:4px solid %s;box-shadow:0 1px 3px rgba(0,0,0,.06)">'
            '<div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.6rem">'
            '<span style="font-size:1.3rem">%s</span>'
            '<div>'
            '<div style="font-weight:700;color:#1e293b;font-size:.88rem">%s</div>'
            '<div style="font-size:.75rem;color:%s;font-weight:600;text-transform:capitalize">'
            '%s &middot; %.1f%%</div>'
            '</div></div>'
            '<p style="font-size:.8rem;color:#64748b;line-height:1.55;margin:0">%s</p>'
            '</div>'
            % (col, icon, title, col, dim, s, tip)
        )
    html += '</div>'
    return html


# ──────────────────────────────────────────────────────────────────────
# Main public function
# ──────────────────────────────────────────────────────────────────────

def generate_dashboard_html(
    analysis_results: dict,
    filename: str,
    fecha: str,
    etiqueta: str = "",
    descripcion: str = "",
) -> str:
    """
    Generates a self-contained HTML dashboard from DQ analysis results.

    Expected keys in analysis_results:
        score_general, total_registros, total_problemas,
        scores_por_columna (dict[col, dict[dim, float]]),
        issues_df (pandas DataFrame, optional).
    """
    score        = round(float(analysis_results["score_general"]), 1)
    total_reg    = int(analysis_results["total_registros"])
    total_prob   = int(analysis_results["total_problemas"])
    spc          = analysis_results["scores_por_columna"]   # scores per column
    issues_df    = analysis_results.get("issues_df")

    pct_limpios  = round((total_reg - total_prob) / total_reg * 100, 1) if total_reg > 0 else 100.0

    # Aggregate per-dimension scores (average across columns)
    dim_lists: dict = {}
    for col_scores in spc.values():
        for dim, s in col_scores.items():
            dim_lists.setdefault(dim, []).append(float(s))
    scores_per_dim = {d: round(sum(v) / len(v), 1) for d, v in dim_lists.items()}

    dims_sorted   = sorted(scores_per_dim.items(), key=lambda x: x[1])
    peor_dim      = dims_sorted[0][0] if dims_sorted else "—"

    # Issues by dimension
    issues_per_dim: dict = {}
    if issues_df is not None and not issues_df.empty and "dimension" in issues_df.columns:
        for d, cnt in issues_df["dimension"].value_counts().items():
            issues_per_dim[str(d)] = int(cnt)

    # Column averages and sorting
    col_avg: dict = {}
    for col, ds in spc.items():
        vals = list(ds.values())
        col_avg[col] = sum(vals) / len(vals) if vals else 100.0
    cols_sorted = sorted(spc.items(), key=lambda x: col_avg[x[0]])

    # Score visuals
    sc_col   = _color(score)
    sc_label = _label(score)
    gp       = _gauge_path(score)
    interp   = _interpretation(score, peor_dim)

    # Etiqueta badge
    etq_styles = {
        "Maestro":        "background:#dbeafe;color:#1e40af",
        "Transaccional":  "background:#dcfce7;color:#166534",
        "Referencia":     "background:#fef9c3;color:#713f12",
    }
    etq_html = ""
    if etiqueta:
        es = etq_styles.get(etiqueta, "background:#f3f4f6;color:#374151")
        etq_html = (
            '&nbsp;<span style="padding:.2rem .7rem;border-radius:999px;'
            'font-size:.76rem;font-weight:600;%s">%s</span>' % (es, etiqueta)
        )

    desc_html = ""
    if descripcion:
        desc_html = (
            '<div style="margin-top:.4rem;font-size:.8rem;color:#cbd5e1">%s</div>'
            % descripcion
        )

    # Gauge SVG score arc
    gauge_arc = ""
    if gp:
        gauge_arc = (
            '<path d="%s" fill="none" stroke="%s" '
            'stroke-width="16" stroke-linecap="round"/>'
            % (gp, sc_col)
        )

    # Background arc: two 90° segments to guarantee top passage
    bg_arc = "M 25 100 A 75 75 0 0 1 100 25 A 75 75 0 0 1 175 100"

    # Build HTML sections
    dim_bars_html      = _dim_bars(dims_sorted)
    kpi_html           = _kpi_grid(total_reg, total_prob, pct_limpios, peor_dim, scores_per_dim)
    col_cards_html     = _col_cards(cols_sorted, col_avg)
    donut_html         = _donut_section(issues_per_dim, scores_per_dim)
    remediation_html   = _remediation_cards(dims_sorted[:3], scores_per_dim)

    gen_time = datetime.now().strftime("%d/%m/%Y %H:%M")

    # ── HTML template (plain string, no f-string — avoids CSS brace escaping) ──
    template = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Dashboard de Calidad &middot; %%TITLE%%</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
         background:#f1f5f9;color:#1e293b}
    .page{max-width:1100px;margin:0 auto;padding:1.5rem 1rem}
    .hdr{background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);
         border-radius:16px;padding:1.75rem 2rem;margin-bottom:1.5rem;
         display:flex;justify-content:space-between;align-items:center;
         flex-wrap:wrap;gap:1rem}
    .hdr-left h1{font-size:1.25rem;font-weight:800;color:#fff;margin-bottom:.35rem}
    .hdr-subtitle{font-size:.82rem;color:#94a3b8}
    .hdr-right{text-align:right}
    .hdr-score{font-size:2.8rem;font-weight:900;line-height:1;margin-bottom:.2rem}
    .hdr-score-label{font-size:.75rem;color:#94a3b8;font-weight:500}
    .card{background:#fff;border-radius:12px;padding:1.25rem 1.5rem;
          box-shadow:0 1px 3px rgba(0,0,0,.08)}
    .card-title{font-size:.72rem;font-weight:600;color:#94a3b8;
                text-transform:uppercase;letter-spacing:.06em;margin-bottom:.5rem}
    .card-value{font-size:1.6rem;font-weight:800;color:#1e293b}
    .card-sub{font-size:.78rem;color:#64748b;margin-top:.25rem}
    .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.5rem}
    .grid-3{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}
    .kpi-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:1rem;margin-bottom:1.5rem}
    .col-cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));
                    gap:1rem;margin-bottom:1.5rem}
    .section-title{font-size:.78rem;font-weight:700;color:#64748b;
                   text-transform:uppercase;letter-spacing:.08em;margin-bottom:.85rem}
    .footer{text-align:center;padding:1.5rem;color:#94a3b8;font-size:.78rem;
            border-top:1px solid #e2e8f0;margin-top:1rem}
    @media(max-width:700px){
      .grid-2,.grid-3,.kpi-grid{grid-template-columns:1fr 1fr}
      .hdr{flex-direction:column;text-align:center}
      .hdr-right{text-align:center}
    }
  </style>
</head>
<body>
<div class="page">

  <!-- HEADER -->
  <div class="hdr">
    <div class="hdr-left">
      <h1>&#128202; Dashboard de Calidad de Datos</h1>
      <div class="hdr-subtitle">
        <strong style="color:#e2e8f0">%%FILENAME%%</strong>
        &nbsp;&middot;&nbsp; %%FECHA%% %%ETQ%%
      </div>
      %%DESC%%
    </div>
    <div class="hdr-right">
      <div class="hdr-score" style="color:%%SC_COL%%">%%SCORE%%</div>
      <div class="hdr-score-label">%%SC_LABEL%%</div>
    </div>
  </div>

  <!-- GAUGE + DIMENSION BARS -->
  <div class="grid-2" style="align-items:start">
    <div class="card" style="text-align:center">
      <div class="card-title" style="text-align:left">Score general</div>
      <svg viewBox="0 0 200 115"
           style="width:100%;max-width:240px;margin:0 auto .75rem;display:block">
        <path d="%%BG_ARC%%"
              fill="none" stroke="#e2e8f0" stroke-width="16" stroke-linecap="round"/>
        %%GAUGE_ARC%%
        <text x="100" y="88" text-anchor="middle"
              font-size="28" font-weight="800" fill="%%SC_COL%%">%%SCORE%%</text>
        <text x="100" y="108" text-anchor="middle" font-size="11" fill="#94a3b8">
          / 100 puntos
        </text>
      </svg>
      <div style="font-size:.83rem;color:#64748b;line-height:1.6;
                  margin-top:.5rem;text-align:left">
        %%INTERP%%
      </div>
    </div>
    <div class="card">
      <div class="card-title">Score por dimensi&#243;n</div>
      %%DIM_BARS%%
    </div>
  </div>

  <!-- KPIs -->
  %%KPIS%%

  <!-- DONUT + ISSUE BREAKDOWN -->
  %%DONUT%%

  <!-- COLUMN CARDS -->
  <div style="margin-bottom:.85rem">
    <div class="section-title">&#128203; Score por columna analizada</div>
  </div>
  %%COL_CARDS%%

  <!-- REMEDIATION -->
  <div style="margin-bottom:.85rem">
    <div class="section-title">&#128295; Principales &#225;reas de remediaci&#243;n</div>
  </div>
  %%REMEDIATION%%

  <!-- FOOTER -->
  <div class="footer">
    <strong>DQ4Value</strong> &mdash;
    ayuda a entender, explicar y accionar la calidad de tus datos.<br>
    Generado el %%GENTIME%%
  </div>

</div>
</body>
</html>"""

    return (
        template
        .replace("%%TITLE%%",       filename)
        .replace("%%FILENAME%%",    filename)
        .replace("%%FECHA%%",       fecha)
        .replace("%%ETQ%%",         etq_html)
        .replace("%%DESC%%",        desc_html)
        .replace("%%SC_COL%%",      sc_col)
        .replace("%%SCORE%%",       str(score))
        .replace("%%SC_LABEL%%",    sc_label)
        .replace("%%BG_ARC%%",      bg_arc)
        .replace("%%GAUGE_ARC%%",   gauge_arc)
        .replace("%%INTERP%%",      interp)
        .replace("%%DIM_BARS%%",    dim_bars_html)
        .replace("%%KPIS%%",        kpi_html)
        .replace("%%DONUT%%",       donut_html)
        .replace("%%COL_CARDS%%",   col_cards_html)
        .replace("%%REMEDIATION%%", remediation_html)
        .replace("%%GENTIME%%",     gen_time)
    )
