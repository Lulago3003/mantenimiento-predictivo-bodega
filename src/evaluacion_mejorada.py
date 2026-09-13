"""
Evaluacion mejorada Chronos-Bolt vs TimesFM 2.5 vs naive.

Mejoras sobre el protocolo original:
  1. Rolling-origin con muchas ventanas, no una sola.
  2. Barrido de horizontes operacionalmente utiles (submuestreando la serie),
     no 64 segundos.
  3. Metricas probabilisticas (pinball loss, cobertura del intervalo 80%),
     que es lo que importa para deteccion de anomalias, ademas de MAE/RMSE/MAPE.
  4. Se evalua tambien la columna 'Temperature', mejor proxy de refrigeracion
     que 'Thermocouple'.
  5. El naive tambien produce intervalos (random walk empirico), para que la
     comparacion probabilistica sea justa.
"""
import numpy as np, pandas as pd, torch, warnings
warnings.filterwarnings("ignore")

CUANTILES = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
IQ_LO, IQ_MED, IQ_HI = 0, 4, 8          # indices de 0.1, 0.5, 0.9
MAX_VENTANAS = 60

# k = factor de submuestreo (la serie es 1 Hz), C = contexto, H = horizonte
CONFIGS = [
    (1,  512, 64),
    (5,  384, 64),
    (15, 256, 64),
    (30, 160, 64),
    (50,  96, 64),
]

df = pd.read_csv("anomaly-free.csv", sep=";")

from chronos import BaseChronosPipeline
import timesfm

pipe = BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", device_map="cpu")
tfm = timesfm.TimesFM_2p5_200M_torch.from_pretrained("google/timesfm-2.5-200m-pytorch")


def naive_probabilistico(ctx, H):
    """Punto = ultimo valor. Intervalos = cuantiles empiricos de las
    diferencias a h pasos observadas dentro del contexto (random walk)."""
    out = np.empty((H, len(CUANTILES)), dtype=np.float64)
    for h in range(1, H + 1):
        d = ctx[h:] - ctx[:-h] if h < len(ctx) else np.array([0.0])
        out[h - 1] = ctx[-1] + np.quantile(d, CUANTILES)
    return out


def pinball(real, q):
    """real: (n,H)  q: (n,H,Q) -> perdida pinball media en unidades de la senal"""
    tau = np.array(CUANTILES).reshape(1, 1, -1)
    e = real[:, :, None] - q
    return np.maximum(tau * e, (tau - 1) * e).mean()


def evaluar(serie, H, C, k):
    need = C + H
    if len(serie) < need + 5:
        return None
    n = min(MAX_VENTANAS, len(serie) - need)
    org = np.unique(np.linspace(C, len(serie) - H, n, dtype=int))
    ctx = [serie[o - C:o] for o in org]
    real = np.stack([serie[o:o + H] for o in org]).astype(np.float64)

    qc, _ = pipe.predict_quantiles(inputs=[torch.tensor(c) for c in ctx],
                                   prediction_length=H, quantile_levels=CUANTILES)
    q_chr = qc.float().numpy().astype(np.float64)

    tfm.compile(timesfm.ForecastConfig(max_context=C, max_horizon=H,
                                       normalize_inputs=True,
                                       use_continuous_quantile_head=True))
    _, qt = tfm.forecast(horizon=H, inputs=ctx)
    q_tfm = np.asarray(qt)[:, :H, 1:10].astype(np.float64)   # canales 1..9 = q0.1..q0.9

    q_nai = np.stack([naive_probabilistico(c.astype(np.float64), H) for c in ctx])

    filas = []
    for nombre, q in [("Naive", q_nai), ("Chronos-Bolt", q_chr), ("TimesFM 2.5", q_tfm)]:
        med = q[:, :, IQ_MED]
        err = med - real
        dentro = (real >= q[:, :, IQ_LO]) & (real <= q[:, :, IQ_HI])
        filas.append({
            "k": k, "horiz_min": H * k / 60, "ventanas": len(org), "Modelo": nombre,
            "MAE": np.abs(err).mean(),
            "RMSE": np.sqrt((err ** 2).mean()),
            "MAPE": np.abs(err / real).mean() * 100,
            "Pinball": pinball(real, q),
            "Cob80%": dentro.mean() * 100,
            "Ancho80": (q[:, :, IQ_HI] - q[:, :, IQ_LO]).mean(),
        })
    return filas


for columna in ["Thermocouple", "Temperature"]:
    base = df[columna].astype("float32").to_numpy()
    print(f"\n{'='*104}\nSERIE: {columna}   (rango {base.min():.2f} a {base.max():.2f})\n{'='*104}")
    todas = []
    for k, C, H in CONFIGS:
        r = evaluar(base[::k], H, C, k)
        if r:
            todas += r
    t = pd.DataFrame(todas)
    print(t.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print(f"\n--- {columna}: mejora vs naive (%) por horizonte ---")
    for hm in sorted(t["horiz_min"].unique()):
        s = t[t["horiz_min"] == hm].set_index("Modelo")
        nb_mae, nb_pin = s.loc["Naive", "MAE"], s.loc["Naive", "Pinball"]
        print(f"  horiz {hm:5.1f} min | "
              f"Chronos MAE {(1-s.loc['Chronos-Bolt','MAE']/nb_mae)*100:+6.1f}% "
              f"pinball {(1-s.loc['Chronos-Bolt','Pinball']/nb_pin)*100:+6.1f}%  ||  "
              f"TimesFM MAE {(1-s.loc['TimesFM 2.5','MAE']/nb_mae)*100:+6.1f}% "
              f"pinball {(1-s.loc['TimesFM 2.5','Pinball']/nb_pin)*100:+6.1f}%")
