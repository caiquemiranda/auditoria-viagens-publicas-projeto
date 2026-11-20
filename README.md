# Radar de Viagens Públicas

Painel de auditoria das viagens a serviço do Governo Federal (2019 a 2026, sendo 2026 parcial).
Responde quanto se gasta, quem gasta, como gasta e quais viagens merecem revisão.

**Fonte:** Portal da Transparência (CGU), Viagens a Serviço:
https://portaldatransparencia.gov.br/download-de-dados/viagens

## Estrutura

```
app.py                       painel Streamlit (6 páginas)
data/                        modelo em Star Schema (~50 MB, Parquet, sem nome nem CPF)
  fato_viagem_<ano>.parquet    tabela fato: 1 linha por viagem realizada
  dim_tempo / dim_orgao / dim_destino / dim_modal / dim_duracao .parquet   dimensões
  casos_<ano>.parquet          detalhe dos casos para revisão (com PCDP)
pipeline/preparar_dados.py   gera data/ a partir dos zips brutos do Portal
tratamento_e_analise.ipynb   processo completo: dados brutos -> código -> resultado -> insights (já executado)
tratamento_e_analise.html    o mesmo documento, para abrir no navegador
requirements.txt
.streamlit/config.toml       tema
```

## Rodar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy no Streamlit Community Cloud

1. Suba esta pasta para um repositório no GitHub. Todos os arquivos de `data/` têm menos de 10 MB.
2. Em share.streamlit.io, crie o app (ou use o já existente) apontando para `app.py`.
   - Se o app já existe com outro arquivo principal, renomeie `app.py` ou ajuste o *Main file path* em *Settings*.
3. A cada commit, o Streamlit Cloud redeploya sozinho. Se não redeployar, use *Reboot app*.

## Regerar os dados

Os zips brutos (~1 GB, 7 GB descompactados) **não vão para o GitHub**: cada um passa do limite de 100 MB.
Baixe-os no Portal, coloque-os em `dados_brutos/` (já ignorada pelo `.gitignore`) e rode:

```bash
python pipeline/preparar_dados.py --zips dados_brutos
```

## Modelo de dados (Star Schema)

| Tabela | Grão | Conteúdo |
|---|---|---|
| fato_viagem | 1 viagem realizada | chaves sk_* · diárias, passagens, outros, devolução, duração, urgente, outlier |
| dim_tempo | 1 dia | ano, mês, trimestre, dia da semana, fator IPCA |
| dim_orgao | 1 órgão superior | nome |
| dim_destino | escopo + UF | UF, região, coordenadas |
| dim_modal | 1 meio de transporte | meio, categoria |
| dim_duracao | 1 faixa | faixa, dias mín/máx |

## Principais regras

- Apenas viagens **realizadas**. Gasto = diárias + passagens + outros gastos.
- Valores podem ser corrigidos pelo **IPCA** (R$ de dez/2025).
- **Caso atípico:** log(custo/dia) acima de Q3 + 3×IQR entre viagens parecidas (mesmo ano, escopo, faixa de duração e com/sem avião), com valor ≥ R$ 1.000.
- **Urgência** só a partir de 2021: antes de jun/2020 o campo não era preenchido.
- **LGPD:** nome, CPF e identificador do viajante são descartados no tratamento.
