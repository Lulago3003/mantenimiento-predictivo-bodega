# -*- coding: utf-8 -*-
"""Construye dashboard/index.html desde datos_dashboard.json.
Graficas en SVG en linea (sin librerias ni CDN) + capa de hover y vista de tabla."""
import json, html

D = json.load(open("datos_dashboard.json"))
EQ = D["equipos"]
PASO_MIN = 0.5                      # 30 s por paso
W, H = 880, 310
PL, PR, PT, PB = 60, 20, 22, 32

esc = lambda v, a, b, c, d: (c + d) / 2 if abs(b - a) < 1e-9 else c + (v - a) * (d - c) / (b - a)
t_lab = lambda k: f"{k:+.0f} min" if k else "ahora"


def grafica(e):
    hist, med, lo, hi = e["historico"], e["pronostico"], e["banda_lo"], e["banda_hi"]
    lim = e["hechos"]["limite_alarma_C"]
    nh, nf = len(hist), len(med)
    tot = nh + nf
    vals = hist + med + lo + hi + [lim]
    vmin, vmax = min(vals), max(vals)
    m = (vmax - vmin) * 0.16 or 0.1
    vmin, vmax = vmin - m, vmax + m
    X = lambda i: esc(i, 0, tot - 1, PL, W - PR)
    Y = lambda v: esc(v, vmin, vmax, H - PB, PT)

    s = [f'<svg viewBox="0 0 {W} {H}" class="chart" preserveAspectRatio="xMidYMid meet" '
         f'role="img" aria-label="Histórico y pronóstico de {html.escape(e["nombre"])}">']
    for k in range(5):                                   # rejilla solida, un tono sobre el fondo
        v = vmin + (vmax - vmin) * k / 4
        y = Y(v)
        s.append(f'<line x1="{PL}" y1="{y:.1f}" x2="{W-PR}" y2="{y:.1f}" class="gl"/>')
        s.append(f'<text x="{PL-9}" y="{y+3.5:.1f}" class="ax" text-anchor="end">{v:.2f}</text>')
    for k in range(0, tot, 32):                          # eje de tiempo
        s.append(f'<text x="{X(k):.1f}" y="{H-11}" class="ax" text-anchor="middle">'
                 f'{t_lab((k-nh+1)*PASO_MIN)}</text>')

    ph = " ".join(f"{X(nh-1+i):.1f},{Y(v):.1f}" for i, v in enumerate(hi))
    pl = " ".join(f"{X(nh-1+i):.1f},{Y(v):.1f}" for i, v in reversed(list(enumerate(lo))))
    s.append(f'<polygon points="{ph} {pl}" class="band"/>')
    s.append(f'<line x1="{PL}" y1="{Y(lim):.1f}" x2="{W-PR}" y2="{Y(lim):.1f}" class="lim"/>')
    # etiqueta del umbral a la izquierda, sobre un respaldo del color de la superficie
    txt = f"límite de alarma {lim}"
    tw = len(txt) * 5.6 + 10
    ty = Y(lim) - 7
    s.append(f'<rect x="{PL+5}" y="{ty-10:.1f}" width="{tw:.0f}" height="14" rx="3" '
             f'fill="var(--surf)" opacity=".92"/>')
    s.append(f'<text x="{PL+10}" y="{ty:.1f}" class="limt" text-anchor="start">{txt}</text>')
    s.append(f'<line x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}" class="base"/>')
    xa = X(nh - 1)
    s.append(f'<line x1="{xa:.1f}" y1="{PT}" x2="{xa:.1f}" y2="{H-PB}" class="div"/>')

    s.append('<polyline class="hist" points="' +
             " ".join(f"{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(hist)) + '"/>')
    s.append('<polyline class="fc" points="' +
             " ".join(f"{X(nh-1+i):.1f},{Y(v):.1f}" for i, v in enumerate(med)) + '"/>')

    # etiquetas directas selectivas: solo la lectura actual y el final del pronostico
    s.append(f'<circle cx="{xa:.1f}" cy="{Y(hist[-1]):.1f}" r="4.5" fill="var(--s1)" class="pt"/>')
    s.append(f'<text x="{xa-9:.1f}" y="{Y(hist[-1])-11:.1f}" class="dlab" fill="var(--s1)" '
             f'text-anchor="end">{hist[-1]:.2f}</text>')
    xf, yf = X(tot - 1), Y(med[-1])
    s.append(f'<circle cx="{xf:.1f}" cy="{yf:.1f}" r="4.5" fill="var(--s2)" class="pt"/>')
    s.append(f'<text x="{xf-7:.1f}" y="{yf-12:.1f}" class="dlab" fill="var(--s2)" '
             f'text-anchor="end">{med[-1]:.2f}</text>')

    s.append('<g class="cross"><line y1="'+str(PT)+'" y2="'+str(H-PB)+'"/>'
             '<circle r="5" class="pt"/></g>')
    s.append("</svg>")

    pts = ([{"x": round(X(i), 1), "y": round(Y(v), 1), "v": v, "f": 0,
             "t": t_lab((i-nh+1)*PASO_MIN)} for i, v in enumerate(hist)] +
           [{"x": round(X(nh-1+i), 1), "y": round(Y(v), 1), "v": v, "f": 1,
             "t": t_lab((i+1)*PASO_MIN), "lo": lo[i], "hi": hi[i]}
            for i, v in enumerate(med)])
    return "".join(s), pts


def tabla(e):
    nh = len(e["historico"])
    f = ["<table><thead><tr><th>Tiempo</th><th>Pronóstico</th><th>Mínimo</th>"
         "<th>Máximo</th><th>Estado</th></tr></thead><tbody>"]
    lim = e["hechos"]["limite_alarma_C"]
    for i in range(0, len(e["pronostico"]), 4):
        v, a, b = e["pronostico"][i], e["banda_lo"][i], e["banda_hi"][i]
        est = "sobre el límite" if b >= lim else "dentro de rango"
        f.append(f"<tr><td>{t_lab((i+1)*PASO_MIN)}</td><td>{v:.3f}</td><td>{a:.3f}</td>"
                 f"<td>{b:.3f}</td><td>{est}</td></tr>")
    return "".join(f) + "</tbody></table>"


salas, paneles, jsdata = [], [], {}
for i, e in enumerate(EQ):
    h, al = e["hechos"], e["estado"] == "ALERTA"
    svg, pts = grafica(e)
    jsdata[str(i)] = {"pts": pts}
    npec = 4 if i == 0 else 3
    peces = "".join('<svg viewBox="0 0 120 50" style="opacity:%.2f"><use href="#tuna"/></svg>'
                    % (0.92 - j * 0.17) for j in range(npec))
    salas.append(f'''
    <button class="sala {'act' if i==0 else ''} {'alert' if al else ''}" data-i="{i}">
      <div class="s-top"><span class="s-n">{html.escape(e["nombre"])}</span>
        <span class="chip {'c-al' if al else 'c-ok'}">
          <svg><use href="#ico-{'al' if al else 'ok'}"/></svg>{e["estado"]}</span></div>
      <div class="s-v">{h["temperatura_actual_C"]}<span class="u">u</span></div>
      <div class="s-d">{html.escape(h["tendencia"])} · {h["deriva_C_por_hora"]}/h ·
        límite {h["limite_alarma_C"]}</div>
      <div class="peces">{peces}</div>
    </button>''')

    ver = ("La lectura actual ya supera el límite de alarma."
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
        <div><h2>{html.escape(e["nombre"])}</h2>
          <p class="sub">sensor {html.escape(e["sensor"])} · histórico 60 min ·
             pronóstico {int(h["horizonte_min"])} min</p></div>
        <div class="ver"><div class="est {'e-al' if al else 'e-ok'}">
          <svg style="width:13px;height:13px"><use href="#ico-{'al' if al else 'ok'}"/></svg>
          {e["estado"]}</div><em>{html.escape(ver)}</em></div>
      </div>
      <div class="vistas"><button class="on" data-v="grafica">Gráfica</button>
        <button data-v="tabla">Tabla</button></div>
      <div class="chartbox" data-c="{i}">{svg}<div class="tip"></div></div>
      <div class="leg">
        <span><i class="g1"></i>lectura registrada</span>
        <span><i class="g2"></i>pronóstico TimesFM 2.5</span>
        <span><i class="g3"></i>intervalo de confianza 80%</span>
        <span><i class="g4"></i>límite de alarma</span>
      </div>
      <div class="tabla">{tabla(e)}</div>
      <div class="cols">
        <table class="datos">{"".join(f"<tr><td>{html.escape(k)}</td><td>{html.escape(str(v))}</td></tr>" for k,v in filas)}</table>
        <div class="rep">
          <div class="rep-h">Reporte generado automáticamente
            <span class="ok">✓ {'sin cifras inventadas' if not e["guardarrail"] else 'revisar'}</span></div>
          <p>{html.escape(e["reporte"])}</p>
          <div class="rep-f">TimesFM 2.5 {e["t_pronostico"]}s · redacción {e["t_slm"]}s ·
            el estado, el veredicto y la tabla los calcula el código, no el modelo de lenguaje</div>
        </div>
      </div>
    </section>''')

n_al = sum(1 for e in EQ if e["estado"] == "ALERTA")
lat = EQ[0]["t_pronostico"] + EQ[0]["t_slm"]
P = open("plantilla_dashboard.html", encoding="utf-8").read()
out = (P.replace("{{SALAS}}", "".join(salas)).replace("{{PANELES}}", "".join(paneles))
        .replace("{{JSDATA}}", json.dumps(jsdata, separators=(",", ":")))
        .replace("{{NEQ}}", str(len(EQ))).replace("{{NAL}}", str(n_al))
        .replace("{{HOR}}", str(int(EQ[0]["hechos"]["horizonte_min"])))
        .replace("{{LAT}}", f"{lat:.1f}").replace("{{GEN}}", D["generado"])
        .replace("{{SLM}}", D["modelo_slm"]))
open("dashboard/index.html", "w", encoding="utf-8").write(out)
print(f"dashboard/index.html generado ({len(out)//1024} KB)")
