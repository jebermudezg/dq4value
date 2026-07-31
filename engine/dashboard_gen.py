"""
engine/dashboard_gen.py
Generates a self-contained HTML dashboard from DQ analysis results.
"""
import json
import math
from datetime import datetime
from engine.nombres import nombre_negocio

# ─────────────────────────────────────────────
# Constants  (unified amber palette: #B45309 / #FEF3C7 / #92400E)
# ─────────────────────────────────────────────
_CIRC = 452.39          # 2π × r=72  (full-circle gauge circumference)
_C_GREEN  = "#16A34A"
_C_AMBER  = "#B45309"   # unified amber — NOT #D97706
_C_RED    = "#DC2626"
_C_GREEN_LT  = "#DCFCE7"
_C_AMBER_LT  = "#FEF3C7"   # unified amber-lt — NOT #FEF9C3
_C_RED_LT    = "#FEE2E2"
_C_GREEN_TXT = "#166534"
_C_AMBER_TXT = "#92400E"   # unified amber-txt — NOT #854D0E
_C_RED_TXT   = "#991B1B"


# ─────────────────────────────────────────────
# Colour helpers
# ─────────────────────────────────────────────
def _score_color(s: float) -> str:
    if s >= 80: return _C_GREEN
    if s >= 60: return _C_AMBER
    return _C_RED

def _score_bg(s: float) -> str:
    if s >= 80: return _C_GREEN_LT
    if s >= 60: return _C_AMBER_LT
    return _C_RED_LT

def _score_txt(s: float) -> str:
    if s >= 80: return _C_GREEN_TXT
    if s >= 60: return _C_AMBER_TXT
    return _C_RED_TXT

def _score_label(s: float) -> str:
    if s >= 80: return "Buena calidad"
    if s >= 60: return "Requiere atención"
    return "Calidad crítica"

def _dashoffset(s: float) -> str:
    return "%.2f" % (_CIRC * (1 - min(max(s, 0), 100) / 100))


# ─────────────────────────────────────────────
# Remediation descriptions
# ─────────────────────────────────────────────
_REMED = {
    "similitud": (
        "👥", "Similitud",
        "Registros con al menos un valor similar detectado. Posibles duplicados "
        "difusos — requieren validación manual antes de deduplicar."
    ),
    "consistencia": (
        "🔤", "Consistencia",
        "Registros con formatos mezclados (texto, fechas o categorías). "
        "Estandarizar formatos en el sistema origen."
    ),
    "validez": (
        "✅", "Validez",
        "Registros con valores fuera del catálogo permitido o con formato "
        "inválido detectado."
    ),
    "exactitud": (
        "📏", "Exactitud",
        "Registros con valores numéricos fuera del rango configurado. "
        "Revisar reglas de validación en la fuente."
    ),
    "completitud": (
        "🗂", "Completitud",
        "Registros con campos obligatorios nulos o vacíos. "
        "Fortalecer controles de captura en el sistema origen."
    ),
    "unicidad": (
        "🔁", "Unicidad",
        "Registros duplicados exactos detectados. "
        "Ejecutar proceso de deduplicación en el maestro de datos."
    ),
    "razonabilidad": (
        "📊", "Razonabilidad",
        "Registros con valores estadísticamente atípicos (outliers). "
        "Verificar si son errores de captura o casos reales."
    ),
    "vigencia": (
        "📅", "Vigencia",
        "Registros con fechas fuera del rango de vigencia configurado. "
        "Actualizar o depurar registros obsoletos."
    ),
    "precision": (
        "📐", "Precisión",
        "Registros con longitud o decimales fuera del estándar esperado. "
        "Revisar reglas de formato en la captura."
    ),
    "integridad_referencial": (
        "🔗", "Integridad Referencial",
        "Registros con valores que no existen en el catálogo maestro de referencia."
    ),
}

def _remed_info(dim: str):
    return _REMED.get(dim, (
        "⚠️", dim.capitalize(),
        "Registros con problemas detectados en la dimensión %s." % dim
    ))


# ─────────────────────────────────────────────
# Section builders
# ─────────────────────────────────────────────

def _gauge_svg(score: float) -> str:
    """Gauge SVG + 3 scale badges. No interpretation text."""
    col   = _score_color(score)
    off   = _dashoffset(score)
    lbl   = _score_label(score)
    bg_c  = _score_bg(score)
    txt_c = _score_txt(score)
    return (
        '<div style="display:flex;flex-direction:column;align-items:center">'
        '<svg width="180" height="180" viewBox="0 0 180 180">'
        '<circle cx="90" cy="90" r="72" fill="none" stroke="#E2E8F0" '
        'stroke-width="14" stroke-dasharray="452.39 452.39"/>'
        '<circle cx="90" cy="90" r="72" fill="none" stroke="%s" '
        'stroke-width="14" stroke-dasharray="452.39 452.39" '
        'stroke-dashoffset="%s" stroke-linecap="round" '
        'transform="rotate(-90 90 90)"/>'
        '<text x="90" y="82" text-anchor="middle" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,system-ui,sans-serif" '
        'font-size="38" font-weight="800" fill="%s">%.1f</text>'
        '<text x="90" y="103" text-anchor="middle" '
        'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,system-ui,sans-serif" '
        'font-size="13" fill="#94A3B8">/ 100 puntos</text>'
        '</svg>'
        # active status badge
        '<span style="margin-top:.5rem;padding:.3rem 1rem;border-radius:999px;'
        'font-size:.78rem;font-weight:700;background:%s;color:%s">%s</span>'
        '</div>'
        % (col, off, col, score, bg_c, txt_c, lbl)
    )


def _dim_bars(dims_sorted: list, sim_meta: dict = None) -> str:
    html = ""
    for dim, s in dims_sorted:
        col = _score_color(s)
        bg  = _score_bg(s)
        txt = _score_txt(s)
        dim_label = (
            nombre_negocio(dim) +
            '<span style="font-size:0.7em;opacity:0.6;display:block">(%s)</span>'
            % dim.replace('_', ' ')
        )
        detail_html = ""
        if dim == 'similitud' and sim_meta:
            detail_html = (
                '<div style="font-size:.72rem;color:#64748B;margin-top:.3rem">'
                '%d grupos &middot; %d involucrados &middot; %d excedentes'
                '<br><span style="opacity:.75">%s &middot; umbral %s%%</span>'
                % (
                    sim_meta['grupos'], sim_meta['involucrados'], sim_meta['excedentes'],
                    sim_meta['algoritmo'], sim_meta['umbral'],
                )
            )
            excl_parts = []
            if sim_meta.get('dup_exactos'):
                excl_parts.append('%d dup. exactos excluidos' % sim_meta['dup_exactos'])
            if sim_meta.get('placeholders'):
                excl_parts.append('%d vacíos excluidos' % sim_meta['placeholders'])
            if excl_parts:
                detail_html += (
                    '<br><span style="opacity:.6">%s</span>' % ' &middot; '.join(excl_parts)
                )
            detail_html += '</div>'

        html += (
            '<div style="margin-bottom:.9rem">'
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;margin-bottom:.35rem">'
            '<span style="font-size:.82rem;font-weight:600;color:#374151">%s</span>'
            '<span style="font-size:.8rem;font-weight:700;padding:.15rem .55rem;'
            'border-radius:6px;background:%s;color:%s">%.1f</span>'
            '</div>'
            '<div style="background:#F1F5F9;border-radius:999px;height:8px;overflow:hidden">'
            '<div style="background:%s;height:100%%;width:%.1f%%;'
            'border-radius:999px;transition:width .5s ease"></div>'
            '</div>%s</div>'
            % (dim_label, bg, txt, s, col, max(0.0, min(100.0, s)), detail_html)
        )
    return html


def _kpi_card(title: str, value: str, sub: str, value_color: str = "#1E293B") -> str:
    return (
        '<div style="background:#fff;border-radius:12px;padding:1.25rem 1.4rem;'
        'box-shadow:0 1px 4px rgba(0,0,0,.07);border:1px solid #F1F5F9">'
        '<div style="font-size:.7rem;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:.07em;margin-bottom:.5rem">%s</div>'
        '<div style="font-size:1.75rem;font-weight:800;color:%s;line-height:1.1">%s</div>'
        '<div style="font-size:.78rem;color:#64748B;margin-top:.3rem">%s</div>'
        '</div>'
        % (title, value_color, value, sub)
    )


def _col_cards(cols_sorted: list, col_avg: dict) -> str:
    html = (
        '<div style="display:grid;grid-template-columns:'
        'repeat(auto-fill,minmax(200px,1fr));gap:1rem;margin-bottom:1.75rem">'
    )
    for col, dim_scores in cols_sorted:
        worst = min(dim_scores.values()) if dim_scores else 100.0
        avg   = round(col_avg[col], 1)
        bc    = _score_color(worst)
        dim_rows = ""
        for dim, s in sorted(dim_scores.items(), key=lambda x: x[1]):
            c = _score_color(s)
            b = _score_bg(s)
            t = _score_txt(s)
            dim_label = (
                nombre_negocio(dim) +
                '<span style="font-size:0.7em;opacity:0.6;display:block">(%s)</span>'
                % dim.replace('_', ' ')
            )
            dim_rows += (
                '<div style="display:flex;justify-content:space-between;'
                'align-items:center;padding:.28rem 0;'
                'border-bottom:1px solid #F8FAFC">'
                '<span style="font-size:.76rem;color:#64748B">%s</span>'
                '<span style="font-size:.75rem;font-weight:700;padding:.1rem .45rem;'
                'border-radius:5px;background:%s;color:%s">%.1f</span>'
                '</div>'
                % (dim_label, b, t, s)
            )
        html += (
            '<div style="background:#fff;border-radius:12px;'
            'border-top:3px solid %s;padding:1rem;'
            'box-shadow:0 1px 4px rgba(0,0,0,.07);border-left:1px solid #F1F5F9;'
            'border-right:1px solid #F1F5F9;border-bottom:1px solid #F1F5F9">'
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;margin-bottom:.7rem">'
            '<span style="font-weight:700;color:#1E293B;font-size:.88rem;'
            'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'
            'max-width:65%%">%s</span>'
            '<span style="font-size:.95rem;font-weight:800;color:%s">%.1f</span>'
            '</div>%s</div>'
            % (bc, col, bc, avg, dim_rows)
        )
    html += '</div>'
    return html


def _issues_section(issues_per_dim: dict, scores_per_dim: dict) -> str:
    """Two-panel row: left = horizontal bars by issue count, right = text list."""
    if not issues_per_dim:
        return ""
    items = sorted(issues_per_dim.items(), key=lambda x: -x[1])   # most → least
    max_cnt = max(c for _, c in items) if items else 1

    # ── Left panel: horizontal bars ──
    bars_html = ""
    for d, c in items:
        s   = scores_per_dim.get(d, 50.0)
        col = _score_color(s)
        bg  = _score_bg(s)
        txt = _score_txt(s)
        pct = round(c / max_cnt * 100, 1)
        dim_label = (
            nombre_negocio(d) +
            '<span style="font-size:0.7em;opacity:0.6;display:block">(%s)</span>'
            % d.replace('_', ' ')
        )
        bars_html += (
            '<div style="margin-bottom:.85rem">'
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;margin-bottom:.3rem">'
            '<span style="font-size:.81rem;font-weight:600;color:#374151">%s</span>'
            '<span style="font-size:.78rem;font-weight:700;padding:.15rem .5rem;'
            'border-radius:6px;background:%s;color:%s">%s</span>'
            '</div>'
            '<div style="background:#F1F5F9;border-radius:999px;height:8px;overflow:hidden">'
            '<div style="background:%s;height:100%%;width:%.1f%%;'
            'border-radius:999px"></div>'
            '</div></div>'
            % (dim_label, bg, txt, "{:,}".format(c), col, pct)
        )

    # ── Right panel: text rows with count badges ──
    rows_html = ""
    for d, c in items:
        s   = scores_per_dim.get(d, 50.0)
        bg  = _score_bg(s)
        txt = _score_txt(s)
        dim_label = (
            nombre_negocio(d) +
            '<span style="font-size:0.7em;opacity:0.6;display:block">(%s)</span>'
            % d.replace('_', ' ')
        )
        rows_html += (
            '<div style="display:flex;justify-content:space-between;'
            'align-items:center;padding:.45rem 0;border-bottom:1px solid #F8FAFC">'
            '<span style="font-size:.81rem;color:#374151;'
            'font-weight:500">%s</span>'
            '<span style="font-size:.79rem;font-weight:700;padding:.15rem .55rem;'
            'border-radius:6px;background:%s;color:%s">%s</span>'
            '</div>'
            % (dim_label, bg, txt, "{:,}".format(c))
        )

    return (
        '<div style="display:grid;grid-template-columns:1fr 1fr;'
        'gap:1rem;margin-bottom:1.75rem">'
        '<div style="background:#fff;border-radius:12px;padding:1.4rem;'
        'box-shadow:0 1px 4px rgba(0,0,0,.07);border:1px solid #F1F5F9">'
        '<div style="font-size:.7rem;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:.07em;margin-bottom:.85rem">'
        'Distribuci&#243;n de problemas por dimensi&#243;n</div>'
        + bars_html +
        '</div>'
        '<div style="background:#fff;border-radius:12px;padding:1.4rem;'
        'box-shadow:0 1px 4px rgba(0,0,0,.07);border:1px solid #F1F5F9">'
        '<div style="font-size:.7rem;font-weight:600;color:#94A3B8;'
        'text-transform:uppercase;letter-spacing:.07em;margin-bottom:.75rem">'
        'Problemas detectados</div>'
        + rows_html +
        '</div></div>'
    )


def _remediation_cards(top3_dims: list, scores_per_dim: dict,
                       issues_per_dim: dict, sim_meta: dict = None) -> str:
    html = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);'
        'gap:1rem;margin-bottom:1.75rem">'
    )
    for dim, _ in top3_dims:
        icon, title, tip = _remed_info(dim)
        s   = scores_per_dim.get(dim, 0.0)
        cnt = issues_per_dim.get(dim, 0)
        col = _score_color(s)
        bg  = _score_bg(s)
        txt = _score_txt(s)
        if dim == 'similitud' and sim_meta:
            display_cnt   = sim_meta.get('grupos', cnt)
            cnt_label     = 'grupos por consolidar'
        else:
            display_cnt   = cnt
            cnt_label     = 'problemas'
        html += (
            '<div style="background:#fff;border-radius:12px;padding:1.3rem;'
            'border-left:4px solid %s;'
            'box-shadow:0 1px 4px rgba(0,0,0,.07)">'
            '<div style="display:flex;align-items:flex-start;'
            'gap:.65rem;margin-bottom:.75rem">'
            '<span style="font-size:1.4rem;line-height:1">%s</span>'
            '<div style="flex:1;min-width:0">'
            '<div style="font-weight:700;color:#1E293B;font-size:.9rem;'
            'margin-bottom:.3rem">%s</div>'
            '<div style="display:flex;gap:.4rem;align-items:center;flex-wrap:wrap">'
            # score badge with colored background
            '<span style="font-size:.73rem;font-weight:700;padding:.15rem .5rem;'
            'border-radius:5px;background:%s;color:%s">%.1f</span>'
            # count badge with colored background
            '%s'
            '</div></div></div>'
            '<p style="font-size:.79rem;color:#64748B;line-height:1.55;margin:0">%s</p>'
            '</div>'
            % (
                col, icon, title,
                bg, txt, s,
                ('<span style="font-size:.73rem;font-weight:700;padding:.15rem .5rem;'
                 'border-radius:5px;background:%s;color:%s">%s %s</span>'
                 % (bg, txt, "{:,}".format(display_cnt), cnt_label)) if display_cnt else "",
                tip,
            )
        )
    html += '</div>'
    return html


# ─────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────

def generate_dashboard_html(
    analysis_results: dict,
    filename: str,
    fecha: str,
    etiqueta: str = "",
    descripcion: str = "",
) -> str:
    """
    Generates a self-contained HTML dashboard.

    analysis_results must contain:
        score_general, total_registros, total_problemas,
        scores_por_columna (dict[col, dict[dim, float]]),
        issues_df (pandas DataFrame, optional).
    """
    score      = round(float(analysis_results["score_general"]), 1)
    total_reg  = int(analysis_results["total_registros"])
    total_prob = int(analysis_results["total_problemas"])
    spc        = analysis_results["scores_por_columna"]
    issues_df  = analysis_results.get("issues_df")

    pct_clean  = round((total_reg - total_prob) / total_reg * 100, 1) if total_reg else 100.0

    # ── Per-dimension averages ──
    dim_lists: dict = {}
    for col_scores in spc.values():
        for d, s in col_scores.items():
            dim_lists.setdefault(d, []).append(float(s))
    scores_per_dim = {d: round(sum(v) / len(v), 1) for d, v in dim_lists.items()}

    dims_sorted  = sorted(scores_per_dim.items(), key=lambda x: x[1])  # worst → best
    peor_dim     = dims_sorted[0][0] if dims_sorted else "—"
    peor_score   = dims_sorted[0][1] if dims_sorted else 0.0

    # ── Issues by dimension ──
    issues_per_dim: dict = {}
    if issues_df is not None and not issues_df.empty and "dimension" in issues_df.columns:
        for d, cnt in issues_df["dimension"].value_counts().items():
            issues_per_dim[str(d)] = int(cnt)

    # ── Column averages & sorting ──
    col_avg: dict = {}
    for col, ds in spc.items():
        vals = list(ds.values())
        col_avg[col] = sum(vals) / len(vals) if vals else 100.0
    cols_sorted = sorted(spc.items(), key=lambda x: col_avg[x[0]])

    # ── Derived display values ──
    sc_col    = _score_color(score)
    sc_bg     = _score_bg(score)
    sc_txt    = _score_txt(score)
    sc_label  = _score_label(score)
    gen_time  = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Etiqueta badge
    ETQ_STYLES = {
        "Maestro de datos":      "background:#DBEAFE;color:#1E40AF",
        "Dataset transaccional": "background:#DCFCE7;color:#166534",
        "Dataset para IA":       "background:#EDE9FE;color:#5B21B6",
        "Otro":                  "background:#F3F4F6;color:#374151",
    }
    etq_html = ""
    if etiqueta:
        es = ETQ_STYLES.get(etiqueta, "background:#F3F4F6;color:#374151")
        etq_html = (
            '<span style="display:inline-block;padding:.2rem .75rem;'
            'border-radius:999px;font-size:.75rem;font-weight:600;%s">%s</span>'
            % (es, etiqueta)
        )

    desc_html = ""
    if descripcion:
        desc_html = (
            '<div style="font-size:.79rem;color:#94A3B8;margin-top:.3rem">%s</div>'
            % descripcion
        )

    # ── Similitud metadata (for dim bar detail) ──
    sim_meta: dict = {}
    if issues_df is not None and not issues_df.empty and 'dimension' in issues_df.columns:
        sim_rows = issues_df[issues_df['dimension'] == 'similitud']
        if not sim_rows.empty and 'sim_total_grupos' in sim_rows.columns:
            r = sim_rows.iloc[0]
            sim_meta = {
                'grupos':       int(r.get('sim_total_grupos', 0)),
                'involucrados': int(r.get('sim_total_involucrados', 0)),
                'excedentes':   int(r.get('sim_total_excedentes', 0)),
                'dup_exactos':  int(r.get('sim_dup_exactos_excluidos', 0)),
                'placeholders': int(r.get('sim_placeholders_excluidos', 0)),
                'algoritmo':    str(r.get('sim_algoritmo', '')),
                'umbral':       r.get('sim_umbral', ''),
            }

    # ── Build HTML sections ──
    gauge_html     = _gauge_svg(score)
    dim_bars_html  = _dim_bars(dims_sorted, sim_meta)
    col_cards_html = _col_cards(cols_sorted, col_avg)
    issues_html    = _issues_section(issues_per_dim, scores_per_dim)
    remed_html     = _remediation_cards(dims_sorted[:3], scores_per_dim, issues_per_dim, sim_meta)

    kpi_html = (
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);'
        'gap:1rem;margin-bottom:1.75rem">'
        + _kpi_card("Total registros",   "{:,}".format(total_reg),  "filas analizadas")
        + _kpi_card("Con problemas",      "{:,}".format(total_prob),
                    "registros únicos afectados", _C_RED)
        + _kpi_card("Registros limpios",  "%.1f%%" % pct_clean,
                    "{:,} sin problemas".format(total_reg - total_prob),
                    _score_color(pct_clean))
        + _kpi_card("Peor dimensión",
                    '<span style="font-size:1.1rem">%s</span>'
                    '<span style="font-size:0.7em;opacity:0.6;display:block">(%s)</span>'
                    % (nombre_negocio(peor_dim), peor_dim.replace('_', ' ')),
                    "%.1f promedio" % peor_score, _C_RED)
        + '</div>'
    )

    # ────────────────────────────────────────────────────────────────
    # HTML template  (plain string — no f-string, avoids CSS {} clash)
    # ────────────────────────────────────────────────────────────────
    tmpl = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1.0">
  <title>Dashboard de Calidad &middot; %%FILENAME%%</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ccircle cx='42' cy='42' r='28' fill='none' stroke='%232563EB' stroke-width='6'/%3E%3Cpolyline points='20,42 26,42 30,36 33,21 36,58 39,34 43,42 62,42' fill='none' stroke='%232563EB' stroke-width='5' stroke-linecap='round' stroke-linejoin='round'/%3E%3Cline x1='63' y1='63' x2='84' y2='84' stroke='%232563EB' stroke-width='8' stroke-linecap='round'/%3E%3C/svg%3E" />
  <style>
    *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif;
         background:#F1F5F9;color:#1E293B;-webkit-font-smoothing:antialiased}
    .page{max-width:1120px;margin:0 auto;padding:1.5rem 1.25rem}
    .hdr{background:linear-gradient(135deg,#1E293B 0%,#0F172A 100%);
         border-radius:16px;padding:1.75rem 2.25rem;margin-bottom:1.5rem;
         display:flex;justify-content:space-between;align-items:center;
         flex-wrap:wrap;gap:1rem;box-shadow:0 4px 20px rgba(0,0,0,.25)}
    .hdr-brand{font-size:.72rem;font-weight:700;color:#94A3B8;
               text-transform:uppercase;letter-spacing:.1em;margin-bottom:.5rem}
    .hdr-title{font-size:1.2rem;font-weight:800;color:#F8FAFC;margin-bottom:.35rem;
               overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:600px}
    .hdr-meta{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap}
    .hdr-meta-item{font-size:.78rem;color:#CBD5E1}
    .hdr-right{text-align:right;flex-shrink:0}
    .hdr-score-num{font-size:3rem;font-weight:900;line-height:1;letter-spacing:-.02em}
    .hdr-score-sub{font-size:.72rem;color:#94A3B8;margin-top:.2rem;font-weight:500}
    .section-lbl{font-size:.68rem;font-weight:700;color:#94A3B8;
                 text-transform:uppercase;letter-spacing:.1em;margin-bottom:1rem}
    .two-col{display:grid;grid-template-columns:220px 1fr;gap:1rem;
             align-items:start;margin-bottom:1.75rem}
    .card{background:#fff;border-radius:12px;padding:1.4rem;
          box-shadow:0 1px 4px rgba(0,0,0,.07);border:1px solid #F1F5F9}
    .footer{text-align:center;padding:1.75rem 1rem;color:#94A3B8;font-size:.77rem;
            border-top:1px solid #E2E8F0;margin-top:.5rem;line-height:1.6}
    @media(max-width:720px){
      .two-col{grid-template-columns:1fr}
      .hdr{flex-direction:column;text-align:center}
      .hdr-right{text-align:center}
      .hdr-title{white-space:normal;font-size:1rem}
    }
    @media(max-width:600px){
      [style*="grid-template-columns:repeat(4"]{grid-template-columns:1fr 1fr!important}
      [style*="grid-template-columns:repeat(3"]{grid-template-columns:1fr 1fr!important}
      [style*="grid-template-columns:1fr 1fr"]{grid-template-columns:1fr!important}
    }
  </style>
</head>
<body>
<div class="page">

  <!-- ══ HEADER ══ -->
  <div class="hdr">
    <div class="hdr-left" style="flex:1;min-width:0">
      <div class="hdr-brand">DQ4Value &nbsp;&bull;&nbsp; Reporte de Calidad de Datos</div>
      <div class="hdr-title">%%FILENAME%%</div>
      <div class="hdr-meta">
        <span class="hdr-meta-item">&#128197; %%FECHA%%</span>
        %%ETQ%%
      </div>
      %%DESC%%
    </div>
    <div class="hdr-right">
      <div class="hdr-score-num" style="color:%%SC_COL%%">%%SCORE%%</div>
      <div style="font-size:.72rem;margin:.2rem 0 .4rem;
                  padding:.2rem .75rem;border-radius:999px;
                  display:inline-block;background:%%SC_BG%%;color:%%SC_TXT%%">
        %%SC_LABEL%%
      </div>
      <div class="hdr-score-sub">Score general del dataset</div>
    </div>
  </div>

  <!-- ══ GAUGE + DIMENSION BARS ══ -->
  <div class="two-col">
    <div class="card" style="text-align:center">
      <div class="section-lbl" style="text-align:left">Score general</div>
      %%GAUGE%%
    </div>
    <div class="card">
      <div class="section-lbl">Score por dimensi&#243;n &mdash; peor a mejor</div>
      %%DIM_BARS%%
    </div>
  </div>

  <!-- ══ KPIs ══ -->
  %%KPIS%%

  <!-- ══ ISSUES BARS ══ -->
  %%ISSUES%%

  <!-- ══ COLUMN CARDS ══ -->
  <div class="section-lbl">&#128203;&nbsp; Score por columna analizada</div>
  %%COL_CARDS%%

  <!-- ══ REMEDIATION ══ -->
  <div class="section-lbl">&#128295;&nbsp; Principales &#225;reas de remediaci&#243;n</div>
  %%REMED%%

  <!-- ══ FOOTER ══ -->
  <div class="footer">
    <strong style="color:#475569">DQ4Value</strong>
    &mdash; ayuda a entender, explicar y accionar la calidad de tus datos.<br>
    Dashboard generado el %%GENTIME%%
  </div>

</div>
</body>
</html>"""

    return (
        tmpl
        .replace("%%FILENAME%%",  filename)
        .replace("%%FECHA%%",     fecha)
        .replace("%%ETQ%%",       etq_html)
        .replace("%%DESC%%",      desc_html)
        .replace("%%SC_COL%%",    sc_col)
        .replace("%%SC_BG%%",     sc_bg)
        .replace("%%SC_TXT%%",    sc_txt)
        .replace("%%SCORE%%",     str(score))
        .replace("%%SC_LABEL%%",  sc_label)
        .replace("%%GAUGE%%",     gauge_html)
        .replace("%%DIM_BARS%%",  dim_bars_html)
        .replace("%%KPIS%%",      kpi_html)
        .replace("%%ISSUES%%",    issues_html)
        .replace("%%COL_CARDS%%", col_cards_html)
        .replace("%%REMED%%",     remed_html)
        .replace("%%GENTIME%%",   gen_time)
    )
