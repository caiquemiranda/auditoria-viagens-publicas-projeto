"""Camada agregada para o painel, derivada do Star Schema (data/fato_viagem_*.parquet + dim_*.parquet).

Por que existe: o plano gratuito do Streamlit Cloud tem pouca memória. Em vez de carregar 5 milhões de viagens,
o painel lê:
  cubo_viagens.npz         somas e contagens por ano × mês × órgão × destino × urgência × duração × transporte × atípico
                           (~400 mil linhas): responde totais, contagens, taxas, mapas e composição.
  valores_viagens_<ano>.npz  só o valor de cada viagem e as chaves de filtro (6 colunas compactas):
                           necessário para medianas e curva de Pareto, que não podem ser somadas.

Uso (a partir da pasta dashboard/):  python pipeline/gerar_agregados.py
"""
import os
from glob import glob

import numpy as np
import pandas as pd

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def main():
    fato = pd.concat([pd.read_parquet(a) for a in sorted(glob(os.path.join(DATA, "fato_viagem_*.parquet")))], ignore_index=True)
    dt = pd.read_parquet(os.path.join(DATA, "dim_tempo.parquet")).set_index("sk_tempo")
    fato["ano"] = dt["ano"].reindex(fato["sk_tempo"]).to_numpy().astype("int16")
    fato["mes"] = dt["mes"].reindex(fato["sk_tempo"]).to_numpy().astype("int8")
    dsi = dt["dia_semana"].reindex(fato["sk_tempo"]).to_numpy()
    fator = dt["fator_ipca"].reindex(fato["sk_tempo"]).to_numpy()
    dur = fato["dur"].to_numpy()

    fato["n"] = 1
    fato["total"] = fato["diarias"].astype(float) + fato["passagens"] + fato["outros"]
    fato["real"] = fato["total"] * fator
    fato["fds"] = ((dur >= 7) | ((dsi + dur - 1) >= 5)).astype("int32")      # viagem inclui sábado ou domingo
    fato["curta"] = (dur <= 3).astype("int32")                                # viagem de até 3 dias
    fato["curta_fds"] = ((dur <= 3) & (dsi >= 5)).astype("int32")            # ... iniciada no fim de semana

    chaves = ["ano", "mes", "sk_orgao", "sk_destino", "urgente", "sk_duracao", "sk_modal", "outlier"]
    medidas = ["n", "real", "total", "diarias", "passagens", "outros", "fds", "curta", "curta_fds"]
    cubo = fato.groupby(chaves, observed=True)[medidas].sum().reset_index()
    for c in ["sk_orgao", "sk_destino", "sk_duracao", "sk_modal"]:
        cubo[c] = cubo[c].astype("int16")
    cubo["n"] = cubo["n"].astype("int32")
    for c in ["fds", "curta", "curta_fds"]:
        cubo[c] = cubo[c].astype("int32")
    for c in ["real", "total", "diarias", "passagens", "outros"]:
        cubo[c] = cubo[c].astype("float64")

    # Formato NumPy comprimido (.npz), e não Parquet: carrega direto em arrays, sem o pool de memória do Arrow,
    # que retinha ~180 MB após a leitura e derrubava o app no plano gratuito do Streamlit Cloud.
    for a in glob(os.path.join(DATA, "cubo_viagens.*")) + glob(os.path.join(DATA, "valores_viagens*")):
        os.remove(a)
    np.savez_compressed(os.path.join(DATA, "cubo_viagens.npz"), **{c: cubo[c].to_numpy() for c in cubo.columns})

    valores = pd.DataFrame({
        "ano": fato["ano"].astype("int16"), "sk_orgao": fato["sk_orgao"].astype("int16"),
        "sk_destino": fato["sk_destino"].astype("int16"), "urgente": fato["urgente"].astype(bool),
        "real": fato["real"].astype("float32"), "total": fato["total"].astype("float32"),
    })
    for ano, v in valores.groupby("ano"):  # um arquivo por ano: cada um fica abaixo do limite de upload do GitHub
        np.savez_compressed(os.path.join(DATA, f"valores_viagens_{ano}.npz"), **{c: v[c].to_numpy() for c in v.columns})

    # conferência: o cubo precisa reproduzir exatamente os totais da tabela fato
    assert int(cubo["n"].sum()) == len(fato)
    assert abs(cubo["total"].sum() - fato["total"].sum()) < 1
    print(f"cubo: {len(cubo):,} linhas | valores: {len(valores):,} linhas | "
          f"total conferido: R$ {cubo['total'].sum() / 1e9:.3f} bi")


if __name__ == "__main__":
    main()
