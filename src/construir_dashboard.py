# -*- coding: utf-8 -*-
"""Construye dashboard/index.html autocontenido desde datos_dashboard.json.
Las graficas se generan como SVG en linea: sin librerias, sin CDN, sin internet."""
import json, html

D = json.load(open("datos_dashboard.json"))
EQ = D["equipos"]

W, H = 880, 300
PL, PR, PT, PB = 58, 18, 18, 28

def escala(v, vmin, vmax, a, b):
    if vmax - vmin < 1e-9: return (a + b) / 2
    return a + (v - vmin) * (b - a) / (vmax - vmin)

def grafica(e):
    hist, med, lo, hi = e["historico"], e["pronostico"], e["banda_lo"], e["banda_hi"]
    lim = e["hechos"]["limite_alarma_C"]
    n_h, n_f = len(hist), len(med)
    total = n_h + n_f
    vals = hist + med + lo + hi + [lim]
    vmin, vmax = min(vals), max(vals)
    m = (vmax - vmin) * 0.15 or 0.1
    vmin, vmax = vmin - m, vmax + m
    X = lambda i: escala(i, 0, total - 1, PL, W - PR)
    Y = lambda v: escala(v, vmin, vmax, H - PB, PT)

    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet">']
    # rejilla y eje Y
    for k in range(5):
        v = vmin + (vmax - vmin) * k / 4
        y = Y(v)
        s.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" class="grid"/>')
        s.append(f'<text x="{PL-8}" y="{y+3.5:.1f}" class="axis" text-anchor="end">{v:.2f}</text>')
    # banda de confianza
    pts_hi = " ".join(f"{X(n_h-1+i):.1f},{Y(v):.1f}" for i, v in enumerate(hi))
    pts_lo = " ".join(f"{X(n_h-1+i):.1f},{Y(v):.1f}" for i, v in reversed(list(enumerate(lo))))
    s.append(f'<polygon points="{pts_hi} {pts_lo}" class="band"/>')
    # umbral
    s.append(f'<line x1="{PL}" y1="{Y(lim):.1f}" x2="{W-PR}" y2="{Y(lim):.1f}" class="limite"/>')
    s.append(f'<text x="{W-PR}" y="{Y(lim)-6:.1f}" class="limtxt" text-anchor="end">límite {lim}</text>')
    # historico
    s.append('<polyline class="hist" points="' +
             " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(hist)) + '"/>')
    # pronostico
    s.append('<polyline class="fc" points="' +
             " ".join(f"{X(n_h-1+i):.1f},{Y(v):.1f}" for i, v in enumerate(med)) + '"/>')
    # separador "ahora"
    xa = X(n_h - 1)
    s.append(f'<line x1="{xa:.1f}" y1="{PT}" x2="{xa:.1f}" y2="{H-PB}" class="ahora"/>')
    s.append(f'<text x="{xa+6:.1f}" y="{PT+12}" class="axis">ahora</text>')
    s.append(f'<circle cx="{xa:.1f}" cy="{Y(hist[-1]):.1f}" r="4" class="punto"/>')
    s.append(f'<text x="{PL}" y="{H-8}" class="axis">histórico</text>')
    s.append(f'<text x="{W-PR}" y="{H-8}" class="axis" text-anchor="end">'
             f'pronóstico {int(e["hechos"]["horizonte_min"])} min →</text>')
    s.append("</svg>")
    return "".join(s)

def sparkline(e):
    v = e["historico"][-40:] + e["pronostico"]
    vmin, vmax = min(v), max(v)
    X = lambda i: escala(i, 0, len(v) - 1, 0, 100)
    Y = lambda t: escala(t, vmin, vmax, 26, 4)
    cls = "spark-al" if e["estado"] == "ALERTA" else "spark-ok"
    return (f'<svg viewBox="0 0 100 30" class="spark"><polyline class="{cls}" points="' +
            " ".join(f"{X(i):.1f},{Y(t):.1f}" for i, t in enumerate(v)) + '"/></svg>')

n_alerta = sum(1 for e in EQ if e["estado"] == "ALERTA")
lat = EQ[0]["t_pronostico"] + EQ[0]["t_slm"]

tarjetas, paneles = [], []
for i, e in enumerate(EQ):
    h, al = e["hechos"], e["estado"] == "ALERTA"
    tarjetas.append(f'''
    <button class="eq {'act' if i==0 else ''}" data-i="{i}">
      <div class="eq-top">
        <span class="eq-n">{html.escape(e["nombre"])}</span>
        <span class="pill {'pa' if al else 'pn'}">{e["estado"]}</span>
      </div>
      <div class="eq-v">{h["temperatura_actual_C"]}<span class="u">u</span></div>
      {sparkline(e)}
      <div class="eq-t">{html.escape(h["tendencia"])} · {h["deriva_C_por_hora"]}/h</div>
    </button>''')

    veredicto = ("La lectura actual ya supera el límite de alarma."
                 if h["temperatura_actual_C"] > h["limite_alarma_C"] else
                 (f"Cruce del límite previsto en ~{int(h['minutos_hasta_limite'])} min."
                  if h["supera_limite"] else
                  f"Sin cruce del límite en los próximos {int(h['horizonte_min'])} min."))
    filas = [("Lectura actual", h["temperatura_actual_C"]),
             ("Límite de alarma", h["limite_alarma_C"]),
             ("Pronóstico final", h["pronostico_final_C"]),
             ("Rango previsto", f'{h["pronostico_min_C"]} – {h["pronostico_max_C"]}'),
             ("Tendencia", f'{h["tendencia"]} ({h["deriva_C_por_hora"]}/h)'),
             ("Banda de confianza", h["banda_confianza_C"]),
             ("Lecturas fuera de rango", f'{h["puntos_anomalos_ultima_ventana"]} de {h["puntos_evaluados"]}')]
    paneles.append(f'''
    <section class="panel {'act' if i==0 else ''}" data-p="{i}">
      <div class="p-head">
        <div>
          <h2>{html.escape(e["nombre"])}</h2>
          <p class="sub">sensor {html.escape(e["sensor"])} · horizonte {int(h["horizonte_min"])} min</p>
        </div>
        <div class="estado {'ea' if al else 'en'}">
          <span class="dot"></span>{e["estado"]}
          <em>{html.escape(veredicto)}</em>
        </div>
      </div>
      {grafica(e)}
      <div class="leyenda">
        <span><i class="l-hist"></i>histórico</span>
        <span><i class="l-fc"></i>pronóstico TimesFM</span>
        <span><i class="l-band"></i>confianza 80%</span>
        <span><i class="l-lim"></i>límite de alarma</span>
      </div>
      <div class="cols">
        <table>{"".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k,v in filas)}</table>
        <div class="rep">
          <div class="rep-h">Reporte generado automáticamente
            <span class="ok">✓ {'sin cifras inventadas' if not e["guardarrail"] else 'revisar'}</span>
          </div>
          <p>{html.escape(e["reporte"])}</p>
          <div class="rep-f">TimesFM 2.5 {e["t_pronostico"]}s · redacción {e["t_slm"]}s ·
          el estado y la tabla los calcula el código, no el modelo de lenguaje</div>
        </div>
      </div>
    </section>''')

PAGINA = open("plantilla_dashboard.html", encoding="utf-8").read()
out = (PAGINA.replace("{{TARJETAS}}", "".join(tarjetas))
             .replace("{{PANELES}}", "".join(paneles))
             .replace("{{NEQ}}", str(len(EQ)))
             .replace("{{NAL}}", str(n_alerta))
             .replace("{{HOR}}", str(int(EQ[0]["hechos"]["horizonte_min"])))
             .replace("{{LAT}}", f"{lat:.1f}")
             .replace("{{GEN}}", D["generado"])
             .replace("{{SLM}}", D["modelo_slm"]))
open("dashboard/index.html", "w", encoding="utf-8").write(out)
print(f"dashboard/index.html generado ({len(out)//1024} KB)")
