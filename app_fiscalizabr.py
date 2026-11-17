import streamlit as st
import pandas as pd
import plotly.express as px
import unicodedata
from pathlib import Path

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Plataforma de Auditoria em Viagens Públicas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. PALETA DE CORES E CSS
ROXO = "#7B2CBF"
TEAL = "#0E7C6B"
LARANJA = "#F58220"
AZUL = "#0044CC"
TEXTO_FORTE = "#1E293B"
TEXTO_MEDIO = "#475569"

st.markdown(f"""
<style>
    header[data-testid="stHeader"] {{ background-color: #EBECEF !important; }}
    .stApp {{ background-color: #EBECEF !important; color: {TEXTO_FORTE} !important; }}

    /* Barra Lateral Branca Clean */
    [data-testid="stSidebar"] {{
        background-color: #FFFFFF !important;
        border-right: 1px solid #CBD5E1 !important;
    }}
    [data-testid="stSidebar"] * {{ color: {TEXTO_FORTE} !important; }}
    
    [data-baseweb="select"] > div {{
        background-color: #F8FAFC !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
    }}

    /* Botão de Restaurar Filtros */
    div.stButton > button {{
        background-color: #F8FAFC !important;
        color: {ROXO} !important;
        border: 1px solid {ROXO} !important;
        border-radius: 8px !important;
        font-weight: 700 !important;
        transition: 0.2s;
    }}
    div.stButton > button:hover {{
        background-color: {ROXO} !important;
        color: #FFFFFF !important;
    }}

    /* Cabeçalho Principal */
    .main-header {{
        background-color: #FFFFFF;
        padding: 18px 26px;
        border-radius: 10px;
        border-bottom: 3px solid {ROXO};
        box-shadow: 0 2px 6px rgba(0,0,0,0.05);
        margin-bottom: 16px;
    }}
    .main-title {{
        font-size: 23px;
        font-weight: 800;
        color: {TEXTO_FORTE};
        margin: 0;
    }}

    /* Abas no Topo */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 36px;
        background-color: transparent;
        border-bottom: 2px solid #CBD5E1;
        margin-bottom: 18px;
    }}
    .stTabs [data-baseweb="tab"] {{
        height: 46px;
        padding: 0 14px;
    }}
    .stTabs [data-baseweb="tab"] p {{
        font-size: 15.5px !important;
        font-weight: 700 !important;
        color: {TEXTO_MEDIO} !important;
    }}
    .stTabs [aria-selected="true"] {{
        border-bottom: 3px solid {AZUL} !important;
    }}
    .stTabs [aria-selected="true"] p {{
        color: {AZUL} !important;
    }}

    /* Cartões de KPI */
    .kpi-card {{
        background-color: #FFFFFF;
        border-radius: 10px;
        padding: 16px 18px;
        border: 1px solid #CBD5E1;
        border-top: 5px solid {TEAL};
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        margin-bottom: 16px;
        min-height: 112px;
    }}
    .kpi-card.roxo {{ border-top-color: {ROXO}; }}
    .kpi-card.laranja {{ border-top-color: {LARANJA}; }}
    .kpi-card.azul {{ border-top-color: {AZUL}; }}
    .kpi-title {{ font-size: 11.5px; color: {TEXTO_MEDIO}; text-transform: uppercase; font-weight: 700; margin-bottom: 4px; }}
    .kpi-value {{ font-size: 24px; font-weight: 800; color: {TEXTO_FORTE}; line-height: 1.2; }}
    .kpi-value-sm {{ font-size: 16.5px; font-weight: 800; color: {TEXTO_FORTE}; line-height: 1.25; margin-top: 2px; }}
    .kpi-sub {{ font-size: 11.5px; color: {TEAL}; font-weight: 600; margin-top: 5px; }}

    /* Nota de Rodapé Metodológica */
    .footer-note {{
        background-color: #FFFFFF;
        border-left: 4px solid {ROXO};
        padding: 14px 18px;
        border-radius: 8px;
        border-top: 1px solid #CBD5E1;
        border-right: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        font-size: 13px;
        color: {TEXTO_MEDIO};
        margin-top: 20px;
        margin-bottom: 20px;
        line-height: 1.5;
    }}
    .footer-note b {{ color: {TEXTO_FORTE}; }}

    /* Moldura dos Gráficos SEM SCROLL INTERNO */
    [data-testid="stPlotlyChart"] {{
        background-color: #FFFFFF;
        border-radius: 10px;
        border: 1px solid #CBD5E1;
        box-shadow: 0 2px 6px rgba(0,0,0,0.04);
        padding: 0px !important;
        overflow: hidden !important;
        margin-bottom: 16px;
    }}
    [data-testid="stPlotlyChart"] > div {{
        overflow: hidden !important;
    }}
</style>
""", unsafe_allow_html=True)

# 3. DICIONÁRIO DE COORDENADAS E TRADUTOR DE UF
COORD_UF = {
    'AC': (-9.02, -70.81, 'Acre'), 'AL': (-9.57, -36.78, 'Alagoas'),
    'AM': (-3.41, -65.85, 'Amazonas'), 'AP': (1.41, -51.77, 'Amapá'),
    'BA': (-12.57, -41.70, 'Bahia'), 'CE': (-5.49, -39.32, 'Ceará'),
    'DF': (-15.79, -47.88, 'Distrito Federal'), 'ES': (-19.18, -40.30, 'Espírito Santo'),
    'GO': (-15.82, -49.83, 'Goiás'), 'MA': (-4.96, -45.27, 'Maranhão'),
    'MG': (-18.51, -44.55, 'Minas Gerais'), 'MS': (-20.77, -54.78, 'Mato Grosso do Sul'),
    'MT': (-12.68, -56.92, 'Mato Grosso'), 'PA': (-3.41, -52.14, 'Pará'),
    'PB': (-7.24, -36.78, 'Paraíba'), 'PE': (-8.81, -36.95, 'Pernambuco'),
    'PI': (-7.71, -42.72, 'Piauí'), 'PR': (-24.89, -51.55, 'Paraná'),
    'RJ': (-22.90, -43.17, 'Rio de Janeiro'), 'RN': (-5.40, -36.95, 'Rio Grande do Norte'),
    'RO': (-10.83, -63.34, 'Rondônia'), 'RR': (2.73, -62.07, 'Roraima'),
    'RS': (-30.03, -51.23, 'Rio Grande do Sul'), 'SC': (-27.24, -50.21, 'Santa Catarina'),
    'SE': (-10.57, -37.38, 'Sergipe'), 'SP': (-23.55, -46.63, 'São Paulo'),
    'TO': (-10.17, -48.29, 'Tocantins')
}

MAPA_NOMES_UF = {}
for sigla, (_, _, nome_est) in COORD_UF.items():
    MAPA_NOMES_UF[sigla] = sigla
    nome_sem_acento = ''.join(
        c for c in unicodedata.normalize('NFD', nome_est.upper())
        if unicodedata.category(c) != 'Mn'
    )
    MAPA_NOMES_UF[nome_sem_acento] = sigla

def padronizar_uf(val):
    if pd.isna(val):
        return None
    s = str(val).strip().upper()
    s_norm = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    if s_norm in MAPA_NOMES_UF:
        return MAPA_NOMES_UF[s_norm]
    if '/' in s_norm:
        partes = [p.strip() for p in s_norm.split('/')]
        for p in reversed(partes):
            if p in MAPA_NOMES_UF:
                return MAPA_NOMES_UF[p]
    return None

def fmt_moeda_br(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# 4. CARREGAMENTO DOS DADOS
@st.cache_data
def carregar_dados():
    pasta = Path(__file__).resolve().parent
    opcoes_res = [
        pasta / "Base_Viagens_Resumo_PowerBI.csv.gz",
        pasta / "Base_Viagens_Resumo_PowerBI.csv",
        pasta / "Base_Viagens_10Anos_Resumo_PowerBI.csv.gz",
        pasta / "Base_Viagens_10Anos_Resumo_PowerBI.csv"
    ]
    opcoes_anom = [
        pasta / "Base_Viagens_Top1000_Anomalias_PowerBI.csv.gz",
        pasta / "Base_Viagens_Top1000_Anomalias_PowerBI.csv"
    ]

    arq_res = next((p for p in opcoes_res if p.exists()), opcoes_res[0])
    arq_anom = next((p for p in opcoes_anom if p.exists()), opcoes_anom[0])

    df_res = pd.read_csv(arq_res, sep=';', decimal=',', encoding='utf-8-sig')
    df_anom = pd.read_csv(arq_anom, sep=';', decimal=',', encoding='utf-8-sig')
    df_res['Sigla_UF'] = df_res['UF_Destino'].apply(padronizar_uf)
    return df_res, df_anom

try:
    df_resumo, df_anomalias = carregar_dados()
except Exception as e:
    st.error(f"Erro ao carregar os arquivos de dados: {e}")
    st.stop()

# 5. GERENCIAMENTO DE ESTADO DOS FILTROS
anos_disp = sorted(df_resumo['Ano'].dropna().unique().astype(int))
ano_min, ano_max = int(min(anos_disp)), int(max(anos_disp))
orgaos_disp = ["Todos os Ministérios"] + sorted(df_resumo['Nome do órgão superior'].dropna().unique().astype(str))

if "filtro_anos" not in st.session_state:
    st.session_state.filtro_anos = (ano_min, ano_max)
if "filtro_escopo" not in st.session_state:
    st.session_state.filtro_escopo = "Todos (Nacional + Internacional)"
if "filtro_fds" not in st.session_state:
    st.session_state.filtro_fds = "Todos"
if "filtro_orgao" not in st.session_state:
    st.session_state.filtro_orgao = "Todos os Ministérios"

def limpar_todos_filtros():
    st.session_state.filtro_anos = (ano_min, ano_max)
    st.session_state.filtro_escopo = "Todos (Nacional + Internacional)"
    st.session_state.filtro_fds = "Todos"
    st.session_state.filtro_orgao = "Todos os Ministérios"

with st.sidebar:
    st.markdown("### 🎯 Filtros de Auditoria")
    st.divider()

    intervalo_anos = st.slider(
        "Intervalo de Anos",
        min_value=ano_min,
        max_value=ano_max,
        step=1,
        key="filtro_anos"
    )

    escopo_opcao = st.selectbox(
        "Escopo da Viagem",
        options=["Todos (Nacional + Internacional)", "Nacional", "Internacional"],
        key="filtro_escopo"
    )

    fds_opcao = st.selectbox(
        "Envolve Fim de Semana?",
        options=["Todos", "Sim (Inicia/Termina no Fim de Semana)", "Não (Apenas Dias Úteis)"],
        key="filtro_fds"
    )

    orgao_opcao = st.selectbox(
        "Órgão Superior (Opcional)",
        options=orgaos_disp,
        key="filtro_orgao"
    )

    st.divider()
    st.button(
        "🔄 Restaurar Todos os Filtros",
        on_click=limpar_todos_filtros,
        use_container_width=True
    )

# Filtragem das bases
df_f = df_resumo[(df_resumo['Ano'] >= intervalo_anos[0]) & (df_resumo['Ano'] <= intervalo_anos[1])].copy()
df_a = df_anomalias[(df_anomalias['Ano'] >= intervalo_anos[0]) & (df_anomalias['Ano'] <= intervalo_anos[1])].copy()

if escopo_opcao != "Todos (Nacional + Internacional)":
    df_f = df_f[df_f['Escopo_Viagem'] == escopo_opcao]
    if 'Escopo_Viagem' in df_a.columns:
        df_a = df_a[df_a['Escopo_Viagem'] == escopo_opcao]

if fds_opcao.startswith("Sim"):
    df_f = df_f[df_f['Envolve_Fim_De_Semana'] == "Sim"]
    df_a = df_a[df_a['Envolve_Fim_De_Semana'] == "Sim"]
elif fds_opcao.startswith("Não"):
    df_f = df_f[df_f['Envolve_Fim_De_Semana'] == "Não"]
    df_a = df_a[df_a['Envolve_Fim_De_Semana'] == "Não"]

if orgao_opcao != "Todos os Ministérios":
    df_f = df_f[df_f['Nome do órgão superior'] == orgao_opcao]
    df_a = df_a[df_a['Nome do órgão superior'] == orgao_opcao]

# 6. CABEÇALHO PRINCIPAL E NAVEGAÇÃO POR ABAS
st.markdown("""
<div class="main-header">
    <div class="main-title">Plataforma de Auditoria em Viagens Públicas</div>
</div>
""", unsafe_allow_html=True)

aba1, aba2 = st.tabs([
    "📊 1. Visão Histórica e Execução Orçamentária",
    "🚨 2. Radar de Anomalias e Principais Ofensores"
])

PLOTLY_CONFIG = {'displayModeBar': False, 'responsive': True}

def formatar_grafico(fig, altura=355):
    fig.update_layout(
        template="plotly_white",
        plot_bgcolor='#FFFFFF',
        paper_bgcolor='#FFFFFF',
        font=dict(family="Segoe UI, sans-serif", color=TEXTO_FORTE, size=12),
        title=dict(font=dict(size=14.5, color=TEXTO_FORTE), x=0.02, y=0.94),
        xaxis=dict(
            tickfont=dict(color=TEXTO_FORTE, size=11),
            title_font=dict(color=TEXTO_MEDIO, size=11.5),
            gridcolor='#E2E8F0'
        ),
        yaxis=dict(
            tickfont=dict(color=TEXTO_FORTE, size=11),
            title_font=dict(color=TEXTO_MEDIO, size=11.5),
            gridcolor='#E2E8F0'
        ),
        legend=dict(
            font=dict(color=TEXTO_FORTE, size=11),
            title_font=dict(color=TEXTO_FORTE, size=11),
            bgcolor='rgba(255,255,255,0.85)'
        ),
        hoverlabel=dict(
            bgcolor="#1E293B",
            font_size=12.5,
            font_family="Segoe UI, sans-serif",
            font_color="#FFFFFF",
            bordercolor="#334155"
        ),
        margin=dict(t=65, b=28, l=20, r=25),
        height=altura
    )
    return fig

# =========================================================
# ABA 1: VISÃO GERAL E MAPA DO BRASIL
# =========================================================
with aba1:
    gasto_total = df_f['Gasto_Total'].sum()
    qtd_viagens = df_f['Qtd_Viagens'].sum()
    ticket_medio = gasto_total / qtd_viagens if qtd_viagens > 0 else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="kpi-card roxo">
            <div class="kpi-title">💰 Gasto Total Liquidado</div>
            <div class="kpi-value">R$ {gasto_total/1e9:,.2f} Bi</div>
            <div class="kpi-sub">Soma de diárias, passagens e taxas</div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">🎫 Ticket Médio por Viagem</div>
            <div class="kpi-value">{fmt_moeda_br(ticket_medio)}</div>
            <div class="kpi-sub">Desembolso médio por processo</div>
        </div>""", unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="kpi-card laranja">
            <div class="kpi-title">✈️ Volume de Viagens</div>
            <div class="kpi-value">{qtd_viagens/1e6:,.2f} Mi</div>
            <div class="kpi-sub">{qtd_viagens:,.0f} viagens realizadas</div>
        </div>""", unsafe_allow_html=True)

    col_esq, col_dir = st.columns([1.15, 1])

    with col_esq:
        df_ano = df_f.groupby('Ano', as_index=False).agg(
            Gasto_Total=('Gasto_Total', 'sum'),
            Qtd_Viagens=('Qtd_Viagens', 'sum')
        )
        df_ano['Gasto_Bi'] = df_ano['Gasto_Total'] / 1e9
        df_ano['Gasto_Fmt'] = df_ano['Gasto_Total'].apply(fmt_moeda_br)

        fig_ano = px.bar(
            df_ano, x='Ano', y='Gasto_Bi',
            custom_data=['Gasto_Fmt', 'Qtd_Viagens'],
            text=df_ano['Gasto_Bi'].apply(lambda x: f"R$ {x:,.2f} Bi"),
            title="<b>Evolução Anual de Gastos</b><br><sup>Despesa anual consolidada (em R$ Bilhões)</sup>",
            color_discrete_sequence=[TEAL]
        )
        fig_ano.update_traces(
            textposition='outside',
            textfont=dict(color=TEXTO_FORTE, size=11),
            hovertemplate="<b>Ano: %{x}</b><br>Gasto Total: <b>%{customdata[0]}</b><br>Qtd. Viagens: %{customdata[1]:,.0f}<extra></extra>"
        )
        fig_ano = formatar_grafico(fig_ano, 360)
        max_ano = df_ano['Gasto_Bi'].max() if not df_ano.empty else 1
        fig_ano.update_layout(
            xaxis=dict(type='category', title=''),
            yaxis=dict(title='R$ Bilhões', range=[0, max_ano * 1.25])
        )
        st.plotly_chart(fig_ano, use_container_width=True, config=PLOTLY_CONFIG)

        df_org = df_f.groupby('Nome do órgão superior', as_index=False).agg(
            Gasto_Total=('Gasto_Total', 'sum'),
            Qtd_Viagens=('Qtd_Viagens', 'sum')
        ).nlargest(8, 'Gasto_Total').sort_values('Gasto_Total')
        df_org['Gasto_Bi'] = df_org['Gasto_Total'] / 1e9
        df_org['Gasto_Fmt'] = df_org['Gasto_Total'].apply(fmt_moeda_br)

        fig_org = px.bar(
            df_org, x='Gasto_Bi', y='Nome do órgão superior', orientation='h',
            custom_data=['Gasto_Fmt', 'Qtd_Viagens'],
            text=df_org['Gasto_Bi'].apply(lambda x: f"R$ {x:,.2f} Bi"),
            title="<b>Top 8 Ministérios por Despesa</b><br><sup>Órgãos superiores com maior orçamento consumido</sup>",
            color_discrete_sequence=[ROXO]
        )
        fig_org.update_traces(
            textposition='outside',
            textfont=dict(color=TEXTO_FORTE, size=11),
            hovertemplate="<b>%{y}</b><br>Gasto Acumulado: <b>%{customdata[0]}</b><br>Viagens: %{customdata[1]:,.0f}<extra></extra>"
        )
        fig_org = formatar_grafico(fig_org, 370)
        max_org = df_org['Gasto_Bi'].max() if not df_org.empty else 1
        fig_org.update_layout(
            xaxis=dict(title='R$ Bilhões', range=[0, max_org * 1.32]),
            yaxis=dict(title='')
        )
        st.plotly_chart(fig_org, use_container_width=True, config=PLOTLY_CONFIG)

    with col_dir:
        df_uf = df_f.dropna(subset=['Sigla_UF']).groupby('Sigla_UF', as_index=False).agg(
            Gasto_Total=('Gasto_Total', 'sum'),
            Qtd_Viagens=('Qtd_Viagens', 'sum')
        )

        if df_uf.empty and 'Destinos' in df_a.columns:
            df_temp = df_a.copy()
            df_temp['Sigla_UF'] = df_temp['Destinos'].apply(padronizar_uf)
            df_uf = df_temp.dropna(subset=['Sigla_UF']).groupby('Sigla_UF', as_index=False).agg(
                Gasto_Total=('Gasto_Total', 'sum'),
                Qtd_Viagens=('Identificador do processo de viagem', 'count')
            )

        df_uf['lat'] = df_uf['Sigla_UF'].map(lambda u: COORD_UF[u][0])
        df_uf['lon'] = df_uf['Sigla_UF'].map(lambda u: COORD_UF[u][1])
        df_uf['Nome_Estado'] = df_uf['Sigla_UF'].map(lambda u: f"{COORD_UF[u][2]} ({u})")
        df_uf['Gasto_Fmt'] = df_uf['Gasto_Total'].apply(fmt_moeda_br)

        if hasattr(px, 'scatter_map'):
            fig_mapa = px.scatter_map(
                df_uf, lat='lat', lon='lon',
                size='Gasto_Total', color='Gasto_Total',
                custom_data=['Nome_Estado', 'Gasto_Fmt', 'Qtd_Viagens'],
                color_continuous_scale=[TEAL, ROXO, LARANJA],
                size_max=40, zoom=3.1, center=dict(lat=-15.0, lon=-52.5),
                map_style="carto-positron",
                title="<b>Concentração Geográfica de Gastos por UF</b><br><sup>Tamanho e cor do círculo indicam o volume financeiro no estado</sup>"
            )
        else:
            fig_mapa = px.scatter_geo(
                df_uf, lat='lat', lon='lon',
                size='Gasto_Total', color='Gasto_Total',
                custom_data=['Nome_Estado', 'Gasto_Fmt', 'Qtd_Viagens'],
                color_continuous_scale=[TEAL, ROXO, LARANJA],
                size_max=40, scope='south america',
                title="<b>Concentração Geográfica de Gastos por UF</b>"
            )

        fig_mapa.update_traces(
            hovertemplate="<b>📍 %{customdata[0]}</b><br>Gasto Total: <b>%{customdata[1]}</b><br>Viagens: %{customdata[2]:,.0f}<extra></extra>"
        )
        fig_mapa = formatar_grafico(fig_mapa, 360)
        fig_mapa.update_layout(margin=dict(t=62, b=10, l=10, r=10), coloraxis_showscale=False)
        st.plotly_chart(fig_mapa, use_container_width=True, config=PLOTLY_CONFIG)

        df_meio = df_f.groupby('Meio_Transporte', as_index=False)['Gasto_Total'].sum().nlargest(5, 'Gasto_Total')
        df_meio['Gasto_Fmt'] = df_meio['Gasto_Total'].apply(fmt_moeda_br)

        fig_meio = px.pie(
            df_meio, names='Meio_Transporte', values='Gasto_Total', hole=0.55,
            custom_data=['Gasto_Fmt'],
            title="<b>Distribuição por Modal de Transporte</b><br><sup>Participação percentual de cada meio utilizado</sup>",
            color_discrete_sequence=[ROXO, TEAL, LARANJA, AZUL, '#64748B']
        )
        fig_meio.update_traces(
            textfont=dict(color='#FFFFFF', size=11),
            hovertemplate="<b>Modal: %{label}</b><br>Gasto Total: <b>%{customdata[0][0]}</b><br>Participação: %{percent}<extra></extra>"
        )
        fig_meio = formatar_grafico(fig_meio, 370)
        fig_meio.update_layout(
            legend_title_text="<b>Modal:</b>",
            legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02)
        )
        st.plotly_chart(fig_meio, use_container_width=True, config=PLOTLY_CONFIG)

# =========================================================
# ABA 2: RADAR DE ANOMALIAS + NOTA DE RODAPÉ METODOLÓGICA
# =========================================================
with aba2:
    maior_gasto = df_a['Gasto_Total'].max() if not df_a.empty else 0
    maior_diaria = df_a['Custo_Medio_Diario'].max() if not df_a.empty else 0
    pct_fds = (df_a['Envolve_Fim_De_Semana'] == 'Sim').mean() * 100 if not df_a.empty else 0

    if not df_a.empty:
        df_top_min = df_a.groupby('Nome do órgão superior', as_index=False).agg(
            Gasto=('Gasto_Total', 'sum'),
            Qtd=('Identificador do processo de viagem', 'count')
        ).sort_values('Gasto', ascending=False)
        min_ofensor_nome = df_top_min.iloc[0]['Nome do órgão superior']
        min_ofensor_gasto = fmt_moeda_br(df_top_min.iloc[0]['Gasto'])
        min_ofensor_qtd = int(df_top_min.iloc[0]['Qtd'])
    else:
        min_ofensor_nome = "Nenhum registro"
        min_ofensor_gasto = "R$ 0,00"
        min_ofensor_qtd = 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="kpi-card azul">
            <div class="kpi-title">🏛️ Principal Ministério Ofensor</div>
            <div class="kpi-value-sm">{min_ofensor_nome[:34]}</div>
            <div class="kpi-sub">{min_ofensor_gasto} ({min_ofensor_qtd} anomalias)</div>
        </div>""", unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="kpi-card laranja">
            <div class="kpi-title">🚨 Maior Viagem Individual</div>
            <div class="kpi-value">{fmt_moeda_br(maior_gasto)}</div>
            <div class="kpi-sub">Teto registrado no lote de anomalias</div>
        </div>""", unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="kpi-card roxo">
            <div class="kpi-title">🔥 Maior Custo por Dia</div>
            <div class="kpi-value">{fmt_moeda_br(maior_diaria)}/dia</div>
            <div class="kpi-sub">Recorde de gasto médio diário</div>
        </div>""", unsafe_allow_html=True)
    with k4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-title">📅 Anomalias no Fim de Semana</div>
            <div class="kpi-value">{pct_fds:.1f}%</div>
            <div class="kpi-sub">Das {len(df_a)} viagens atípicas selecionadas</div>
        </div>""", unsafe_allow_html=True)

    a_esq, a_dir = st.columns([1.15, 1])

    with a_esq:
        df_scatter = df_a[df_a['Duracao_Dias'] <= 180].copy()
        df_scatter['Gasto_Fmt'] = df_scatter['Gasto_Total'].apply(fmt_moeda_br)
        df_scatter['Diaria_Fmt'] = df_scatter['Custo_Medio_Diario'].apply(fmt_moeda_br)
        df_scatter['Motivo_Curto'] = df_scatter['Motivo'].astype(str).apply(lambda t: t[:95] + '...' if len(t) > 95 else t)
        df_scatter['Cargo_Limpo'] = df_scatter['Cargo'].fillna('Não Informado').replace('None', 'Não Informado')
        df_scatter['FDS_Legenda'] = df_scatter['Envolve_Fim_De_Semana'].map({
            'Sim': 'Sim (Inclui Sáb/Dom)',
            'Não': 'Não (Apenas Dias Úteis)'
        })

        fig_scatter = px.scatter(
            df_scatter,
            x='Duracao_Dias',
            y='Gasto_Total',
            color='FDS_Legenda',
            size='Custo_Medio_Diario',
            custom_data=[
                'Nome do órgão superior', 'Nome', 'Cargo_Limpo', 'Destinos',
                'Gasto_Fmt', 'Diaria_Fmt', 'Envolve_Fim_De_Semana', 'Motivo_Curto'
            ],
            color_discrete_map={'Sim (Inclui Sáb/Dom)': LARANJA, 'Não (Apenas Dias Úteis)': TEAL},
            title="<b>Matriz de Dispersão: Duração (até 180 dias) vs. Custo Total</b><br><sup>Tamanho do círculo = Custo Diário | Passe o mouse sobre um ponto para abrir a ficha</sup>"
        )
        fig_scatter.update_traces(
            hovertemplate=(
                "<b>🏛️ %{customdata[0]}</b><br>"
                "────────────────────────────────────<br>"
                "👤 <b>Servidor:</b> %{customdata[1]}<br>"
                "💼 <b>Cargo:</b> %{customdata[2]}<br>"
                "📍 <b>Destino:</b> %{customdata[3]}<br>"
                "🗓️ <b>Duração:</b> %{x} dias (Fim de Semana: %{customdata[6]})<br>"
                "💰 <b>Gasto Total:</b> %{customdata[4]}<br>"
                "🔥 <b>Custo Médio/Dia:</b> %{customdata[5]}<br>"
                "📝 <b>Motivo:</b> <i>%{customdata[7]}</i>"
                "<extra></extra>"
            )
        )
        fig_scatter = formatar_grafico(fig_scatter, 380)
        fig_scatter.update_layout(
            xaxis=dict(title='Duração da Viagem (Dias)'),
            yaxis=dict(title='Gasto Total (R$)'),
            legend_title_text="<b>Fim de Semana:</b>",
            legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="right", x=1)
        )
        st.plotly_chart(fig_scatter, use_container_width=True, config=PLOTLY_CONFIG)

    with a_dir:
        df_anom_org = df_a.groupby('Nome do órgão superior', as_index=False).agg(
            Qtd_Outliers=('Identificador do processo de viagem', 'count'),
            Gasto_Outliers=('Gasto_Total', 'sum')
        ).nlargest(6, 'Gasto_Outliers').sort_values('Gasto_Outliers')
        df_anom_org['Gasto_Mi'] = df_anom_org['Gasto_Outliers'] / 1e6
        df_anom_org['Gasto_Fmt'] = df_anom_org['Gasto_Outliers'].apply(fmt_moeda_br)

        fig_a_org = px.bar(
            df_anom_org, x='Gasto_Mi', y='Nome do órgão superior', orientation='h',
            custom_data=['Gasto_Fmt', 'Qtd_Outliers'],
            text=df_anom_org.apply(lambda r: f"R$ {r['Gasto_Mi']:,.1f} Mi ({int(r['Qtd_Outliers'])}x)", axis=1),
            title="<b>Top 6 Ministérios Ofensores (Gasto em Anomalias)</b><br><sup>Volume financeiro acumulado e nº de viagens no lote de outliers</sup>",
            color_discrete_sequence=[ROXO]
        )
        fig_a_org.update_traces(
            textposition='outside',
            textfont=dict(color=TEXTO_FORTE, size=11),
            hovertemplate="<b>%{y}</b><br>Soma das Anomalias: <b>%{customdata[0]}</b><br>Viagens Atípicas: %{customdata[1]} processos<extra></extra>"
        )
        fig_a_org = formatar_grafico(fig_a_org, 380)
        max_g = df_anom_org['Gasto_Mi'].max() if not df_anom_org.empty else 1
        fig_a_org.update_layout(
            xaxis=dict(title='Gasto em Anomalias (R$ Milhões)', range=[0, max_g * 1.38]),
            yaxis=dict(title='')
        )
        st.plotly_chart(fig_a_org, use_container_width=True, config=PLOTLY_CONFIG)

    b_esq, b_dir = st.columns([1.15, 1])

    with b_esq:
        df_serv = df_a.copy()
        df_serv['Cargo_Limpo'] = df_serv['Cargo'].fillna('Cargo Não Informado').replace('None', 'Cargo Não Informado')
        df_top_serv = df_serv.groupby(['Nome', 'Nome do órgão superior', 'Cargo_Limpo'], as_index=False).agg(
            Gasto_Total=('Gasto_Total', 'sum'),
            Qtd_Viagens=('Identificador do processo de viagem', 'count'),
            Maior_Diaria=('Custo_Medio_Diario', 'max')
        ).nlargest(6, 'Gasto_Total').sort_values('Gasto_Total')

        df_top_serv['Gasto_Mil'] = df_top_serv['Gasto_Total'] / 1e3
        df_top_serv['Gasto_Fmt'] = df_top_serv['Gasto_Total'].apply(fmt_moeda_br)
        df_top_serv['Diaria_Fmt'] = df_top_serv['Maior_Diaria'].apply(fmt_moeda_br)

        fig_serv = px.bar(
            df_top_serv, x='Gasto_Mil', y='Nome', orientation='h',
            custom_data=['Nome do órgão superior', 'Cargo_Limpo', 'Gasto_Fmt', 'Qtd_Viagens', 'Diaria_Fmt'],
            text=df_top_serv['Gasto_Fmt'],
            title="<b>Principais Ofensores Individuais (Top 6 Servidores)</b><br><sup>Servidores com maior soma financeira em viagens atípicas</sup>",
            color_discrete_sequence=[LARANJA]
        )
        fig_serv.update_traces(
            textposition='outside',
            textfont=dict(color=TEXTO_FORTE, size=11),
            hovertemplate=(
                "<b>👤 %{y}</b><br>"
                "🏛️ <b>Órgão:</b> %{customdata[0]}<br>"
                "💼 <b>Cargo:</b> %{customdata[1]}<br>"
                "💰 <b>Gasto Acumulado:</b> %{customdata[2]} (%{customdata[3]} viagem/ns)<br>"
                "🔥 <b>Pico Diário:</b> %{customdata[4]}/dia<extra></extra>"
            )
        )
        fig_serv = formatar_grafico(fig_serv, 320)
        max_s = df_top_serv['Gasto_Mil'].max() if not df_top_serv.empty else 1
        fig_serv.update_layout(
            xaxis=dict(title='Gasto Acumulado (R$ Mil)', range=[0, max_s * 1.35]),
            yaxis=dict(title='')
        )
        st.plotly_chart(fig_serv, use_container_width=True, config=PLOTLY_CONFIG)

    with b_dir:
        if 'Viagem Urgente' in df_a.columns:
            df_urg = df_a.copy()
            df_urg['Status_Urgencia'] = df_urg['Viagem Urgente'].astype(str).str.upper().map({
                'SIM': 'Urgente (Sem Antecedência)',
                'NÃO': 'Programada (Normal)',
                'NAO': 'Programada (Normal)'
            }).fillna('Não Informado')
            df_urg_grp = df_urg.groupby('Status_Urgencia', as_index=False)['Gasto_Total'].count()

            fig_urg = px.pie(
                df_urg_grp, names='Status_Urgencia', values='Gasto_Total', hole=0.55,
                title="<b>Proporção de Viagens Sem Antecedência</b><br><sup>Incidência de urgência entre as viagens mais caras</sup>",
                color='Status_Urgencia',
                color_discrete_map={
                    'Urgente (Sem Antecedência)': LARANJA,
                    'Programada (Normal)': TEAL,
                    'Não Informado': '#94A3B8'
                }
            )
            fig_urg.update_traces(
                textfont=dict(color='#FFFFFF', size=11),
                hovertemplate="<b>%{label}</b><br>Quantidade: <b>%{value} viagens</b> (%{percent})<extra></extra>"
            )
            fig_urg = formatar_grafico(fig_urg, 320)
            fig_urg.update_layout(
                legend_title_text="<b>Classificação:</b>",
                legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02)
            )
            st.plotly_chart(fig_urg, use_container_width=True, config=PLOTLY_CONFIG)

    # NOTA DE RODAPÉ METODOLÓGICA EXIGIDA PARA AUDITORIA
    st.markdown("""
    <div class="footer-note">
        <b>📌 Nota Metodológica de Auditoria (Radar de Outliers):</b> 
        As anomalias exibidas neste módulo correspondem à cauda estatística superior (Top 1.000 processos com maior despesa absoluta entre 2019 e 2025). 
        O <i>Custo Médio Diário</i> isola desproporções temporais (ex: viagens de poucas semanas com despesas diárias superiores a R$ 15 mil). 
        As flags de <i>Fim de Semana</i> e <i>Urgência</i> destacam processos de alto risco que exigem investigação de conformidade e verificação se o deslocamento presencial era indispensável frente às tecnologias de reuniões remotas.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("##### 📋 Ficha de Auditoria: Detalhamento das Viagens Mais Caras")
    colunas_tab = [
        'Ano', 'Nome do órgão superior', 'Nome', 'Cargo', 'Destinos',
        'Duracao_Dias', 'Envolve_Fim_De_Semana', 'Gasto_Total', 'Custo_Medio_Diario', 'Motivo'
    ]
    cols_ok = [c for c in colunas_tab if c in df_a.columns]
    df_ibir = df_a[cols_ok].sort_values('Gasto_Total', ascending=False).head(50).copy()
    df_ibir['Gasto_Total'] = df_ibir['Gasto_Total'].apply(fmt_moeda_br)
    df_ibir['Custo_Medio_Diario'] = df_ibir['Custo_Medio_Diario'].apply(fmt_moeda_br)
    df_ibir = df_ibir.rename(columns={
        'Nome do órgão superior': 'Órgão Superior',
        'Nome': 'Servidor',
        'Duracao_Dias': 'Duração (Dias)',
        'Envolve_Fim_De_Semana': 'Fim de Semana?',
        'Gasto_Total': 'Gasto Total',
        'Custo_Medio_Diario': 'Custo Médio/Dia'
    })

    st.dataframe(df_ibir, use_container_width=True, height=280, hide_index=True)