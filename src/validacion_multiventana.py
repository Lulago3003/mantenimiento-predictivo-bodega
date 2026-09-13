"""
Validacion rolling-origin: Chronos-Bolt vs TimesFM 2.5 vs naive.
Misma serie y mismo protocolo (contexto 512 / horizonte 64) que
comparar_chronos_timesfm.py, pero repetido sobre multiples ventanas
a lo largo de toda la serie, no solo la ultima.
"""

import numpy as np
import pandas as pd
import torch

CSV, COLUMNA = "anomaly-free.csv", "Thermocouple"
CONTEXTO, HORIZONTE = 512, 64
N_VENTANAS = 40

serie = pd.read_csv(CSV, sep=";")[COLUMNA].astype("float32").to_numpy()

origenes = np.linspace(CONTEXTO, len(serie) - HORIZONTE, N_VENTANAS, dtype=int)
contextos = [serie[o - CONTEXTO:o] for o in origenes]
reales = np.stack([serie[o:o + HORIZONTE] for o in origenes])
print(f"{len(origenes)} ventanas | contexto {CONTEXTO} | horizonte {HORIZONTE}")

# --- Chronos-Bolt ---
from chronos import BaseChronosPipeline

pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", device_map="cpu")
q, _ = pipe.predict_quantiles(
    inputs=[torch.tensor(c) for c in contextos],
    prediction_length=HORIZONTE,
    quantile_levels=[0.1, 0.5, 0.9],
)
pred_chronos = q[:, :, 1].float().numpy()

# --- TimesFM 2.5 ---
import timesfm

m = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")
m.compile(timesfm.ForecastConfig(max_context=CONTEXTO, max_horizon=HORIZONTE,
                                 normalize_inputs=True, use_continuous_quantile_head=True))
punto, _ = m.forecast(horizon=HORIZONTE, inputs=contextos)
pred_timesfm = np.asarray(punto)[:, :HORIZONTE]

# --- Naive ---
pred_naive = np.repeat(np.array([c[-1] for c in contextos])[:, None], HORIZONTE, axis=1)

preds = {"Naive (persistencia)": pred_naive,
         "Chronos-Bolt (small)": pred_chronos,
         "TimesFM 2.5 (200M)": pred_timesfm}

def por_ventana(real, pred):
    e = pred - real
    return (np.abs(e).mean(1),
            np.sqrt((e ** 2).mean(1)),
            (np.abs(e / real).mean(1) * 100))

res, mae_v = [], {}
for nombre, p in preds.items():
    mae, rmse, mape = por_ventana(reales, p)
    mae_v[nombre] = mae
    res.append({"Modelo": nombre, "MAE": mae.mean(), "RMSE": rmse.mean(),
                "MAPE (%)": mape.mean(), "MAE mediano": np.median(mae)})

tabla = pd.DataFrame(res)
print(f"\n=== METRICAS PROMEDIO SOBRE {N_VENTANAS} VENTANAS ===")
print(tabla.to_string(index=False, float_format=lambda x: f"{x:.5f}"))

base = mae_v["Naive (persistencia)"]
print("\nMejora en MAE vs naive (promedio) y tasa de victorias por ventana:")
for nombre in ["Chronos-Bolt (small)", "TimesFM 2.5 (200M)"]:
    v = mae_v[nombre]
    print(f"  {nombre}: {(1 - v.mean()/base.mean())*100:+.1f}% | gana en "
          f"{(v < base).sum()}/{N_VENTANAS} ventanas")

c, t = mae_v["Chronos-Bolt (small)"], mae_v["TimesFM 2.5 (200M)"]
print(f"\nChronos vs TimesFM: Chronos gana en {(c < t).sum()}/{N_VENTANAS} ventanas")
