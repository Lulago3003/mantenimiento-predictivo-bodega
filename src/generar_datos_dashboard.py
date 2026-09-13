# -*- coding: utf-8 -*-
"""Ejecuta el pipeline real (TimesFM + SLM) para los 4 equipos del demo
y guarda todo en datos_dashboard.json para alimentar el dashboard web."""
import json, time, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, torch
import reporte_slm as rs

df = pd.read_csv("anomaly-free.csv", sep=";")

# 4 equipos derivados de distintos tramos/sensores del mismo dataset de demo.
# El umbral de cada uno se fija cerca del rango real para producir una mezcla
# de estados (normal / alerta) y que el demo muestre ambos casos.
EQUIPOS = [
    ("Cuarto frío principal", "Temperature",  9405, 91.00),
    ("Blast freezer 1",       "Temperature",  7000, 89.30),
    ("Blast freezer 2",       "Thermocouple", 9405, 29.45),
    ("Blast freezer 3",       "Thermocouple", 6500, 29.10),
]

CTX_GRAFICA = 120     # puntos de historico que se dibujan

print("Cargando SLM una sola vez...")
mid, tok, mod = rs.cargar_slm()
DEV = rs.DISPOSITIVO


def redactar_rapido(hechos):
    datos = "\n".join(f"- {x}" for x in rs.hechos_en_palabras(hechos))
    msgs = [{"role": "user", "content": rs.PROMPT.format(datos=datos)}]
    e = tok.apply_chat_template(msgs, add_generation_prompt=True,
                               return_tensors="pt", return_dict=True).to(DEV)
    n = e["input_ids"].shape[-1]
    t0 = time.time()
    with torch.no_grad():
        o = mod.generate(**e, max_new_tokens=340, do_sample=False,
                         pad_token_id=tok.eos_token_id)
    return tok.decode(o[0][n:], skip_special_tokens=True).strip(), time.time() - t0


salida = {"equipos": [], "generado": time.strftime("%Y-%m-%d %H:%M")}

for nombre, col, fin, limite in EQUIPOS:
    serie = df[col].astype("float32").to_numpy()[:fin]
    rs.EQUIPO, rs.LIMITE_ALARMA, rs.COLUMNA = nombre, limite, col

    t0 = time.time()
    ctx, med, lo, hi = rs.pronosticar(serie)
    t_fc = time.time() - t0
    hechos = rs.extraer_hechos(ctx, med, lo, hi, serie)
    texto, t_slm = redactar_rapido(hechos)

    alerta = hechos["supera_limite"] or hechos["temperatura_actual_C"] > hechos["limite_alarma_C"]
    salida["equipos"].append({
        "nombre": nombre,
        "sensor": col,
        "estado": "ALERTA" if alerta else "NORMAL",
        "hechos": hechos,
        "reporte": " ".join(l.replace("**", "") for l in texto.split("\n") if l.strip()),
        "historico": [round(float(v), 3) for v in ctx[-CTX_GRAFICA:]],
        "pronostico": [round(float(v), 3) for v in med],
        "banda_lo": [round(float(v), 3) for v in lo],
        "banda_hi": [round(float(v), 3) for v in hi],
        "t_pronostico": round(t_fc, 2),
        "t_slm": round(t_slm, 2),
        "guardarrail": rs.verificar(texto, hechos),
    })
    print(f"  {nombre:24s} {salida['equipos'][-1]['estado']:7s} "
          f"({t_fc:.1f}s + {t_slm:.1f}s)")

salida["modelo_slm"] = mid
salida["dispositivo"] = DEV
json.dump(salida, open("datos_dashboard.json", "w"), ensure_ascii=False, indent=1)
print(f"\nGuardado datos_dashboard.json ({len(salida['equipos'])} equipos)")
