"""
Comparacion zero-shot: Chronos-Bolt (Amazon) vs TimesFM 2.5 (Google)
Serie: "Thermocouple" del benchmark SKAB (anomaly-free.csv), proxy de temperatura
mientras llega la data real de la bodega de atun.

Protocolo: ultimos 512 puntos como contexto, siguientes 64 como horizonte.
Metricas: MAE, RMSE, MAPE contra los valores reales y contra baseline naive
(persistencia = ultimo valor del contexto repetido).
"""

import numpy as np
import pandas as pd
import torch

CSV = "anomaly-free.csv"
COLUMNA = "Thermocouple"
CONTEXTO = 512
HORIZONTE = 64


def cargar_serie():
    df = pd.read_csv(CSV, sep=";", parse_dates=["datetime"])
    return df[COLUMNA].astype("float32").to_numpy()


def metricas(y_real, y_pred):
    err = y_pred - y_real
    mae = float(np.mean(np.abs(err)))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mape = float(np.mean(np.abs(err / y_real)) * 100)
    return mae, rmse, mape


def pronostico_chronos(contexto, horizonte):
    from chronos import BaseChronosPipeline

    pipe = BaseChronosPipeline.from_pretrained(
        "amazon/chronos-bolt-small", device_map="cpu", torch_dtype=torch.float32
    )
    cuantiles, _media = pipe.predict_quantiles(
        inputs=torch.tensor(contexto),
        prediction_length=horizonte,
        quantile_levels=[0.1, 0.5, 0.9],
    )
    # mediana (q0.5) como pronostico puntual
    return cuantiles[0, :, 1].numpy()


def pronostico_timesfm(contexto, horizonte):
    import timesfm

    modelo = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        "google/timesfm-2.5-200m-pytorch"
    )
    modelo.compile(
        timesfm.ForecastConfig(
            max_context=CONTEXTO,
            max_horizon=horizonte,
            normalize_inputs=True,
            use_continuous_quantile_head=True,
        )
    )
    punto, _cuantiles = modelo.forecast(horizon=horizonte, inputs=[contexto])
    return np.asarray(punto[0])


def main():
    serie = cargar_serie()
    print(f"Serie '{COLUMNA}': {len(serie)} puntos")

    contexto = serie[-(CONTEXTO + HORIZONTE): -HORIZONTE]
    real = serie[-HORIZONTE:]
    print(f"Contexto: {len(contexto)} puntos | Horizonte: {len(real)} puntos")

    predicciones = {
        "Naive (persistencia)": np.repeat(contexto[-1], HORIZONTE),
        "Chronos-Bolt (small)": pronostico_chronos(contexto, HORIZONTE),
        "TimesFM 2.5 (200M)": pronostico_timesfm(contexto, HORIZONTE),
    }

    filas = []
    for nombre, pred in predicciones.items():
        mae, rmse, mape = metricas(real, pred)
        filas.append({"Modelo": nombre, "MAE": mae, "RMSE": rmse, "MAPE (%)": mape})

    tabla = pd.DataFrame(filas)
    print("\n=== METRICAS (horizonte 64 pasos) ===")
    print(tabla.to_string(index=False, float_format=lambda x: f"{x:.6f}"))

    base = tabla.loc[tabla["Modelo"].str.startswith("Naive"), "MAE"].iloc[0]
    print("\nMejora en MAE vs baseline naive:")
    for _, r in tabla.iterrows():
        if not r["Modelo"].startswith("Naive"):
            print(f"  {r['Modelo']}: {(1 - r['MAE'] / base) * 100:+.2f}%")


if __name__ == "__main__":
    main()
