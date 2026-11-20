"""Pipeline: zips brutos do Portal da Transparência (Viagens a Serviço) -> parquets compactos do dashboard.

Uso (a partir da pasta dashboard/):
    python pipeline/preparar_dados.py --zips ".."

Saídas em data/ — modelo dimensional (Star Schema):
    fato_viagem_<ano>.parquet  FATO: uma linha por viagem REALIZADA (medidas + chaves), sem nome/CPF/ID do viajante
    dim_tempo.parquet          DIMENSÃO calendário (data de início da viagem) + fator IPCA
    dim_orgao.parquet          DIMENSÃO órgão superior
    dim_destino.parquet        DIMENSÃO destino (escopo, UF, região, coordenadas)
    dim_modal.parquet          DIMENSÃO meio de transporte principal
    dim_duracao.parquet        DIMENSÃO faixa de duração
    casos_<ano>.parquet        casos para revisão (detalhe, com PCDP para conferência no Portal)
    resumo_situacao.parquet    viagens realizadas x não realizadas por ano (controle de qualidade)
"""
import argparse
import glob
import os
import re
import zipfile

import numpy as np
import pandas as pd

ENC = "latin1"

V_COLS = {
    "Identificador do processo de viagem": "id",
    "Número da Proposta (PCDP)": "pcdp",
    "Situação": "situacao",
    "Viagem Urgente": "urgente",
    "Nome do órgão superior": "orgao",
    "Nome órgão solicitante": "orgao_solicitante",
    "Cargo": "cargo",
    "Período - Data de início": "ini",
    "Período - Data de fim": "fim",
    "Destinos": "destinos",
    "Valor diárias": "diarias",
    "Valor passagens": "passagens",
    "Valor devolução": "devolucao",
    "Valor outros gastos": "outros",
}

# prioridade para definir o modal principal da viagem (menor = mais relevante para custo)
MODAL_RANK = {
    "Aéreo": 0, "Marítimo": 1, "Fluvial": 2, "Ferroviário": 3, "Rodoviário": 4,
    "Veículo Oficial": 5, "Veículo Próprio": 6, "Inválido": 7,
}
RANK_MODAL = {v: k for k, v in MODAL_RANK.items()}

FAIXAS = [0, 1, 3, 7, 30, 90, 100000]
FAIXAS_ROT = ["1 dia", "2–3 dias", "4–7 dias", "8–30 dias", "31–90 dias", "> 90 dias"]

UF_RE = re.compile(r"/([A-Z]{2})$")


def money(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                         errors="coerce").fillna(0.0)


def escopo_e_uf(destinos: pd.Series):
    """Destinos = 'Cidade/UF' ou 'Cidade/País', separados por ', '."""
    d = destinos.fillna("").str.strip()
    sig = d.str.contains("sigilo", case=False)
    partes = d.str.split(", ")
    # internacional se algum destino NÃO termina em /UF
    def classifica(lst):
        ufs = [UF_RE.search(p.strip()) for p in lst if p.strip()]
        if not ufs:
            return "Não informado", "ND"
        nac = all(u is not None for u in ufs)
        first = ufs[0].group(1) if ufs[0] is not None else "EX"
        return ("Nacional" if nac else "Internacional"), first
    res = [classifica(lst) for lst in partes]
    esc = pd.Series([r[0] for r in res], index=d.index)
    uf = pd.Series([r[1] for r in res], index=d.index)
    esc[sig] = "Sigiloso"
    uf[sig] = "SG"
    return esc, uf


def processa_ano(zpath: str, outdir: str):
    zf = zipfile.ZipFile(zpath)
    names = {n.split("_", 1)[1].replace(".csv", ""): n for n in zf.namelist()}
    ano = int(os.path.basename(zpath)[:4])
    print(f"[{ano}] lendo Viagem...", flush=True)
    v = pd.read_csv(zf.open(names["Viagem"]), sep=";", encoding=ENC, dtype=str,
                    usecols=list(V_COLS), keep_default_na=False)
    v = v.rename(columns=V_COLS)

    resumo = v["situacao"].value_counts().rename_axis("situacao").reset_index(name="n")
    resumo["ano"] = ano

    v = v[v["situacao"] == "Realizada"].drop_duplicates("id", keep="first").copy()
    for c in ["diarias", "passagens", "devolucao", "outros"]:
        v[c] = money(v[c])
    v["ini"] = pd.to_datetime(v["ini"], format="%d/%m/%Y", errors="coerce")
    v["fim"] = pd.to_datetime(v["fim"], format="%d/%m/%Y", errors="coerce")
    v = v[v["ini"].notna() & v["fim"].notna()]
    v["dur"] = ((v["fim"] - v["ini"]).dt.days + 1).clip(lower=1)

    print(f"[{ano}] lendo Trecho...", flush=True)
    t = pd.read_csv(zf.open(names["Trecho"]), sep=";", encoding=ENC, dtype=str,
                    usecols=[0, 11], keep_default_na=False)
    t.columns = ["id", "modal"]
    t["r"] = t["modal"].map(MODAL_RANK).fillna(7).astype("int8")
    modal = t.groupby("id")["r"].min().map(RANK_MODAL)
    v["modal"] = v["id"].map(modal).fillna("Sem trecho")

    v["escopo"], v["uf"] = escopo_e_uf(v["destinos"])
    v["urgente"] = v["urgente"].eq("SIM")
    v["total"] = v["diarias"] + v["passagens"] + v["outros"]
    v["custo_dia"] = v["total"] / v["dur"]
    v["faixa_dur"] = pd.cut(v["dur"], FAIXAS, labels=FAIXAS_ROT)

    # ---- regra de outlier: custo por dia muito acima dos pares
    # pares = mesmo ano + escopo (nacional/internacional) + faixa de duração + com/sem trecho aéreo.
    # Custos são assimétricos (log-normais), então o IQR é calculado sobre log(custo/dia).
    v["aereo"] = v["modal"].eq("Aéreo")
    pos = v["custo_dia"] > 0
    v["log_cd"] = np.where(pos, np.log(v["custo_dia"].where(pos, 1)), np.nan)
    chaves = ["escopo", "faixa_dur", "aereo"]
    g = v[pos].groupby(chaves, observed=True)["log_cd"]
    q = g.quantile([.25, .5, .75]).unstack()
    q.columns = ["q1", "q2", "q3"]
    v = v.join(q, on=chaves)
    v["outlier"] = pos & (v["log_cd"] > v["q3"] + 3 * (v["q3"] - v["q1"])) & (v["total"] >= 1000)
    v["razao_mediana"] = v["custo_dia"] / np.exp(v["q2"])

    base = pd.DataFrame({
        "ano": np.int16(ano),
        "data_ini": v["ini"].dt.normalize(),
        "dur": v["dur"].clip(upper=32000).astype("int16"),
        "faixa_dur": v["faixa_dur"].astype(str),
        "orgao": v["orgao"],
        "urgente": v["urgente"],
        "escopo": v["escopo"],
        "uf": v["uf"],
        "modal": v["modal"],
        "diarias": v["diarias"].astype("float32"),
        "passagens": v["passagens"].astype("float32"),
        "outros": v["outros"].astype("float32"),
        "devolucao": v["devolucao"].astype("float32"),
        "outlier": v["outlier"],
        "razao_mediana": v["razao_mediana"].astype("float32"),
    })
    for c in ["faixa_dur", "orgao", "escopo", "uf", "modal"]:
        base[c] = base[c].astype(str)

    # ---- casos para revisão (sem nome/CPF; PCDP permite conferir no Portal)
    cand = pd.concat([
        v[v["outlier"]].nlargest(1500, "total"),
        v.nlargest(300, "total"),
    ]).drop_duplicates("id")
    casos = pd.DataFrame({
        "ano": ano,
        "pcdp": cand["pcdp"],
        "orgao": cand["orgao"],
        "orgao_solicitante": cand["orgao_solicitante"],
        "cargo": cand["cargo"].replace({"": "Não informado", "Sem informação": "Não informado"}),
        "inicio": cand["ini"].dt.date,
        "fim": cand["fim"].dt.date,
        "dur": cand["dur"],
        "escopo": cand["escopo"],
        "destinos": cand["destinos"].str.slice(0, 120),
        "urgente": cand["urgente"],
        "modal": cand["modal"],
        "total": cand["total"].round(2),
        "custo_dia": cand["custo_dia"].round(2),
        "razao_mediana": cand["razao_mediana"].round(1),
        "outlier": cand["outlier"],
    })
    casos.to_parquet(os.path.join(outdir, f"casos_{ano}.parquet"), compression="zstd", index=False)
    print(f"[{ano}] ok: {len(base):,} viagens, R$ {base[['diarias','passagens','outros']].sum().sum()/1e9:.2f} bi, "
          f"{base['outlier'].sum():,} outliers", flush=True)
    return resumo, base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zips", default="..", help="pasta com os arquivos AAAA_*_Viagens.zip")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    zips = sorted(glob.glob(os.path.join(a.zips, "20[0-9][0-9]_*_Viagens.zip")))
    res = [processa_ano(z, a.out) for z in zips]
    pd.concat([r[0] for r in res]).to_parquet(os.path.join(a.out, "resumo_situacao.parquet"), index=False)
    monta_star_schema(pd.concat([r[1] for r in res], ignore_index=True), a.out)


# IPCA anual (IBGE): leva valores de cada ano a preços de dez/2025; 2026 fica nominal (ano corrente)
IPCA = {2019: 4.31, 2020: 4.52, 2021: 10.06, 2022: 5.79, 2023: 4.62, 2024: 4.83, 2025: 4.26}
URG_DESDE = 2021  # campo "Viagem Urgente" só é preenchido de forma consistente a partir de jun/2020

UF_INFO = {  # sigla: (nome, região, lat, lon)
    "AC": ("Acre", "Norte", -9.0, -70.5), "AL": ("Alagoas", "Nordeste", -9.6, -36.6),
    "AP": ("Amapá", "Norte", 1.4, -51.8), "AM": ("Amazonas", "Norte", -4.2, -64.7),
    "BA": ("Bahia", "Nordeste", -12.5, -41.7), "CE": ("Ceará", "Nordeste", -5.2, -39.5),
    "DF": ("Distrito Federal", "Centro-Oeste", -15.8, -47.9), "ES": ("Espírito Santo", "Sudeste", -19.6, -40.7),
    "GO": ("Goiás", "Centro-Oeste", -15.9, -49.6), "MA": ("Maranhão", "Nordeste", -5.0, -45.3),
    "MT": ("Mato Grosso", "Centro-Oeste", -12.7, -55.9), "MS": ("Mato Grosso do Sul", "Centro-Oeste", -20.5, -54.8),
    "MG": ("Minas Gerais", "Sudeste", -18.5, -44.6), "PA": ("Pará", "Norte", -3.8, -52.5),
    "PB": ("Paraíba", "Nordeste", -7.1, -36.8), "PR": ("Paraná", "Sul", -24.6, -51.6),
    "PE": ("Pernambuco", "Nordeste", -8.4, -37.9), "PI": ("Piauí", "Nordeste", -7.7, -42.7),
    "RJ": ("Rio de Janeiro", "Sudeste", -22.3, -42.7), "RN": ("Rio Grande do Norte", "Nordeste", -5.8, -36.6),
    "RS": ("Rio Grande do Sul", "Sul", -29.7, -53.3), "RO": ("Rondônia", "Norte", -10.9, -62.8),
    "RR": ("Roraima", "Norte", 2.1, -61.4), "SC": ("Santa Catarina", "Sul", -27.3, -50.4),
    "SP": ("São Paulo", "Sudeste", -22.3, -48.7), "SE": ("Sergipe", "Nordeste", -10.6, -37.4),
    "TO": ("Tocantins", "Norte", -10.2, -48.3),
}
MODAL_CATEG = {"Aéreo": "Aéreo", "Rodoviário": "Terrestre", "Veículo Oficial": "Terrestre", "Veículo Próprio": "Terrestre",
               "Ferroviário": "Terrestre", "Fluvial": "Aquaviário", "Marítimo": "Aquaviário",
               "Inválido": "Não informado", "Sem trecho": "Não informado"}
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def monta_star_schema(stg: pd.DataFrame, outdir: str):
    """Separa a área de preparação em 1 tabela FATO + 5 DIMENSÕES ligadas por chaves substitutas (sk_*)."""
    fator = {a: float(np.prod([1 + IPCA[k] / 100 for k in IPCA if k > a])) for a in range(2015, 2031)}

    datas = pd.date_range(stg["data_ini"].min(), stg["data_ini"].max(), freq="D")
    dim_tempo = pd.DataFrame({"sk_tempo": datas.strftime("%Y%m%d").astype(int), "data": datas,
                              "ano": datas.year, "mes": datas.month, "nome_mes": [MESES[m - 1] for m in datas.month],
                              "trimestre": datas.quarter, "dia_semana": datas.weekday,
                              "nome_dia": [DIAS[d] for d in datas.weekday]})
    dim_tempo["fim_de_semana"] = dim_tempo["dia_semana"] >= 5
    dim_tempo["fator_ipca"] = dim_tempo["ano"].map(fator)
    dim_tempo["urgencia_confiavel"] = dim_tempo["ano"] >= URG_DESDE

    orgaos = sorted(stg["orgao"].unique())
    dim_orgao = pd.DataFrame({"sk_orgao": np.arange(1, len(orgaos) + 1, dtype="int16"), "orgao": orgaos})

    dest = stg[["escopo", "uf"]].drop_duplicates().sort_values(["escopo", "uf"]).reset_index(drop=True)
    dest.insert(0, "sk_destino", np.arange(1, len(dest) + 1, dtype="int16"))
    dest["nome_uf"] = dest["uf"].map(lambda u: UF_INFO[u][0] if u in UF_INFO else ("Exterior" if u == "EX" else "Não se aplica"))
    dest["regiao"] = dest["uf"].map(lambda u: UF_INFO[u][1] if u in UF_INFO else "—")
    dest["lat"] = dest["uf"].map(lambda u: UF_INFO[u][2] if u in UF_INFO else np.nan)
    dest["lon"] = dest["uf"].map(lambda u: UF_INFO[u][3] if u in UF_INFO else np.nan)
    dim_destino = dest

    modais = sorted(stg["modal"].unique())
    dim_modal = pd.DataFrame({"sk_modal": np.arange(1, len(modais) + 1, dtype="int16"), "modal": modais})
    dim_modal["categoria"] = dim_modal["modal"].map(MODAL_CATEG).fillna("Não informado")

    dim_duracao = pd.DataFrame({"sk_duracao": np.arange(1, len(FAIXAS_ROT) + 1, dtype="int16"), "faixa_dur": FAIXAS_ROT,
                                "dias_min": [f + 1 for f in FAIXAS[:-1]], "dias_max": FAIXAS[1:]})

    fato = stg.merge(dim_orgao, on="orgao").merge(dim_destino[["sk_destino", "escopo", "uf"]], on=["escopo", "uf"])
    fato = fato.merge(dim_modal[["sk_modal", "modal"]], on="modal").merge(dim_duracao[["sk_duracao", "faixa_dur"]], on="faixa_dur")
    assert len(fato) == len(stg), "chave de dimensão faltando"
    fato["sk_tempo"] = fato["data_ini"].dt.strftime("%Y%m%d").astype("int32")
    fato = fato[["sk_tempo", "sk_orgao", "sk_destino", "sk_modal", "sk_duracao", "urgente", "dur",
                 "diarias", "passagens", "outros", "devolucao", "outlier", "razao_mediana", "ano"]]

    for nome, d in [("dim_tempo", dim_tempo), ("dim_orgao", dim_orgao), ("dim_destino", dim_destino),
                    ("dim_modal", dim_modal), ("dim_duracao", dim_duracao)]:
        d.to_parquet(os.path.join(outdir, f"{nome}.parquet"), index=False)
    for ano, f in fato.groupby("ano"):
        f.drop(columns="ano").sort_values("sk_tempo").to_parquet(
            os.path.join(outdir, f"fato_viagem_{ano}.parquet"), compression="zstd", index=False)
    print(f"Star schema: fato {len(fato):,} linhas | dim_tempo {len(dim_tempo)} | dim_orgao {len(dim_orgao)} | "
          f"dim_destino {len(dim_destino)} | dim_modal {len(dim_modal)} | dim_duracao {len(dim_duracao)}", flush=True)


if __name__ == "__main__":
    main()
