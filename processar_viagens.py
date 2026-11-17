import pandas as pd
import re
import gc
import unicodedata
from pathlib import Path

# ---------------------------------------------------------
# DEFINA AQUI APENAS OS ANOS QUE QUER PROCESSAR
# ---------------------------------------------------------
ANOS_ESCOLHIDOS = {'2019', '2020', '2021', '2022', '2023', '2024', '2025'}

def normalizar(txt):
    txt = str(txt).replace('\ufeff', '').replace('"', '').strip().lower()
    txt = ''.join(
        c for c in unicodedata.normalize('NFD', txt)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'\s+', ' ', txt)

def ler_csv_seguro(caminho, cols_desejadas):
    mapa = {normalizar(c): c for c in cols_desejadas}
    enc_usado = 'latin1'
    for enc in ['latin1', 'utf-8-sig', 'cp1252']:
        try:
            cabecalho = pd.read_csv(caminho, sep=';', encoding=enc, nrows=0).columns.tolist()
            enc_usado = enc
            break
        except Exception:
            continue

    cols_ler = []
    renomear = {}
    for c_real in cabecalho:
        c_norm = normalizar(c_real)
        if c_norm in mapa:
            cols_ler.append(c_real)
            renomear[c_real] = mapa[c_norm]
        elif 'identificador' in c_norm and 'viagem' in c_norm:
            cols_ler.append(c_real)
            renomear[c_real] = 'Identificador do processo de viagem'

    df = pd.read_csv(
        caminho, sep=';', encoding=enc_usado,
        usecols=cols_ler, decimal=',', low_memory=False
    )
    df = df.rename(columns=renomear)

    if 'Identificador do processo de viagem' in df.columns:
        df['Identificador do processo de viagem'] = (
            df['Identificador do processo de viagem']
            .astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        )
    return df

PASTA_BASE = Path(__file__).resolve().parent
arquivos_viagem = sorted(PASTA_BASE.rglob("*_Viagem.csv"))
if not arquivos_viagem:
    arquivos_viagem = sorted(Path.cwd().rglob("*_Viagem.csv"))

arq_resumo = PASTA_BASE / "Base_Viagens_Resumo_PowerBI.csv"
arq_anomalias = PASTA_BASE / "Base_Viagens_Top1000_Anomalias_PowerBI.csv"

resumos_anuais = []
candidatos_anomalias = []

cols_viagem = [
    'Identificador do processo de viagem', 'Situação', 'Viagem Urgente',
    'Nome do órgão superior', 'Nome órgão solicitante', 'Nome', 'Cargo',
    'Período - Data de início', 'Período - Data de fim', 'Destinos',
    'Motivo', 'Valor diárias', 'Valor passagens', 'Valor outros gastos'
]

for arq_v in arquivos_viagem:
    m = re.search(r'(\d{4})', arq_v.name)
    ano = m.group(1) if m else "0000"
    
    # Pula imediatamente os anos que não estão na nossa seleção
    if ano not in ANOS_ESCOLHIDOS:
        continue

    pasta = arq_v.parent
    print(f"\n---> A processar ano selecionado: {ano} ({arq_v.name})...")

    df_v = ler_csv_seguro(arq_v, cols_viagem)
    if 'Situação' in df_v.columns:
        df_v = df_v[df_v['Situação'].astype(str).str.strip() == 'Realizada'].drop(columns=['Situação'])

    ids_ok = set(df_v['Identificador do processo de viagem'].dropna().unique())
    print(f"     Viagens realizadas: {len(df_v):,}")

    # Lê apenas Trecho (de forma otimizada) para pegar Meio de Transporte e UF
    arq_t = pasta / f"{ano}_Trecho.csv"
    if arq_t.exists():
        cols_t = ['Identificador do processo de viagem', 'Meio de transporte', 'Destino - País', 'Destino - UF']
        df_t = ler_csv_seguro(arq_t, cols_t)
        df_t = df_t[df_t['Identificador do processo de viagem'].isin(ids_ok)].drop_duplicates(
            subset=['Identificador do processo de viagem']
        )
        df_t = df_t.rename(columns={
            'Meio de transporte': 'Meio_Transporte',
            'Destino - País': 'Pais_Destino',
            'Destino - UF': 'UF_Destino'
        })
        df_v = pd.merge(df_v, df_t, on='Identificador do processo de viagem', how='left')
        del df_t
        gc.collect()

    # Datas e Cálculos
    df_v['Período - Data de início'] = pd.to_datetime(df_v['Período - Data de início'], format='%d/%m/%Y', errors='coerce')
    df_v['Período - Data de fim'] = pd.to_datetime(df_v['Período - Data de fim'], format='%d/%m/%Y', errors='coerce')
    df_v = df_v.dropna(subset=['Período - Data de início', 'Período - Data de fim'])

    df_v['Duracao_Dias'] = (df_v['Período - Data de fim'] - df_v['Período - Data de início']).dt.days.clip(lower=0)
    df_v['Ano'] = int(ano)
    df_v['Mes'] = df_v['Período - Data de início'].dt.month

    df_v['Fase_Pandemia'] = df_v['Ano'].apply(
        lambda a: '1. Pré-Pandemia (2019)' if a == 2019 else (
            '2. Pandemia (2020)' if a in [2020, 2021] else '3. Pós-Pandemia (2023-2025)'
        )
    )

    d_ini = df_v['Período - Data de início'].dt.dayofweek
    d_fim = df_v['Período - Data de fim'].dt.dayofweek
    fds = d_ini.isin([4, 5, 6]) | d_fim.isin([5, 6]) | (df_v['Duracao_Dias'] >= 7)
    df_v['Envolve_Fim_De_Semana'] = fds.map({True: 'Sim', False: 'Não'})

    df_v['Escopo_Viagem'] = df_v['Pais_Destino'].apply(
        lambda p: 'Internacional' if pd.notna(p) and str(p).strip() not in ['', 'Brasil'] else 'Nacional'
    ) if 'Pais_Destino' in df_v.columns else 'Nacional'

    for cf in ['Valor diárias', 'Valor passagens', 'Valor outros gastos']:
        df_v[cf] = pd.to_numeric(df_v.get(cf, 0.0), errors='coerce').fillna(0.0)

    df_v['Gasto_Total'] = (df_v['Valor diárias'] + df_v['Valor passagens'] + df_v['Valor outros gastos']).round(2)
    df_v['Custo_Medio_Diario'] = (df_v['Gasto_Total'] / df_v['Duracao_Dias'].replace(0, 1)).round(2)

    for ct in ['Motivo', 'Destinos', 'Nome']:
        if ct in df_v.columns:
            df_v[ct] = df_v[ct].astype(str).str.replace(r'[\r\n;]+', ' ', regex=True).str.strip()

    # Captura Top Outliers do ano
    cand = pd.concat([df_v.nlargest(300, 'Gasto_Total'), df_v.nlargest(300, 'Custo_Medio_Diario')]).drop_duplicates(
        subset=['Identificador do processo de viagem']
    )
    candidatos_anomalias.append(cand)

    # Agrupa Resumo Mensal para o Power BI
    cols_grp = [
        'Ano', 'Mes', 'Fase_Pandemia', 'Nome do órgão superior',
        'Meio_Transporte', 'Escopo_Viagem', 'UF_Destino',
        'Envolve_Fim_De_Semana', 'Viagem Urgente'
    ]
    for c in cols_grp:
        if c not in df_v.columns:
            df_v[c] = 'Não Informado'
    df_v[cols_grp] = df_v[cols_grp].fillna('Não Informado')

    res_ano = df_v.groupby(cols_grp, as_index=False).agg(
        Qtd_Viagens=('Identificador do processo de viagem', 'count'),
        Total_Dias=('Duracao_Dias', 'sum'),
        Total_Diarias=('Valor diárias', 'sum'),
        Total_Passagens=('Valor passagens', 'sum'),
        Total_Outros=('Valor outros gastos', 'sum'),
        Gasto_Total=('Gasto_Total', 'sum')
    )
    resumos_anuais.append(res_ano)
    print(f"     Ano {ano} finalizado!")
    del df_v
    gc.collect()

if resumos_anuais:
    pd.concat(resumos_anuais, ignore_index=True).to_csv(arq_resumo, index=False, sep=';', encoding='utf-8-sig', decimal=',')

if candidatos_anomalias:
    df_cand = pd.concat(candidatos_anomalias, ignore_index=True).drop_duplicates(subset=['Identificador do processo de viagem'])
    t700 = df_cand.nlargest(700, 'Gasto_Total')
    rest = df_cand[~df_cand['Identificador do processo de viagem'].isin(t700['Identificador do processo de viagem'])]
    t300 = rest.nlargest(300, 'Custo_Medio_Diario')
    pd.concat([t700, t300], ignore_index=True).to_csv(arq_anomalias, index=False, sep=';', encoding='utf-8-sig', decimal=',')

print("\nCONCLUÍDO RAPIDAMENTE!")
print(f"1. {arq_resumo.name}")
print(f"2. {arq_anomalias.name}")