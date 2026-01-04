import json
import pandas as pd
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Dashboard JSON",
    layout="wide"
)

st.title("Dashboard de Análise de JSON")

# Upload do arquivo JSON
uploaded_file = st.file_uploader(
    "Faça upload do arquivo JSON",
    type=["json"]
)

if uploaded_file is None:
    st.info("Envie um arquivo JSON para iniciar a análise.")
    st.stop()

# Leitura do JSON
try:
    dados = json.load(uploaded_file)
except Exception as erro:
    st.error(f"Erro ao ler o arquivo JSON: {erro}")
    st.stop()

# Função para localizar a lista principal de registros
def encontrar_registros(obj):
    if isinstance(obj, list):
        return obj

    if isinstance(obj, dict):
        listas = []
        for chave, valor in obj.items():
            if isinstance(valor, list) and valor and isinstance(valor[0], dict):
                listas.append((chave, valor, len(valor)))

        if listas:
            listas.sort(key=lambda x: x[2], reverse=True)
            chave, lista, _ = listas[0]
            st.caption(f"Registros detectados em: dados['{chave}']")
            return lista

    return []

registros = encontrar_registros(dados)

# Normalização do JSON em tabela
if registros:
    df = pd.json_normalize(registros, sep=".")
else:
    df = pd.json_normalize(dados)

st.subheader("Pré-visualização dos dados")
st.dataframe(df.head(50), use_container_width=True)

st.divider()

# Seleção de colunas para métricas
st.subheader("Configuração de métricas")

colunas = ["(não usar)"] + list(df.columns)

col_valor = st.selectbox("Coluna de valor (R$)", colunas)
col_distancia = st.selectbox("Coluna de distância (km)", colunas)
col_tipo = st.selectbox("Coluna de tipo (ex: Truck / Veicular)", colunas)
col_prestador = st.selectbox("Coluna de prestador", colunas)
col_data = st.selectbox("Coluna de data", colunas)

# Conversões seguras
def converter_numerico(col):
    return pd.to_numeric(col, errors="coerce")

if col_valor != "(não usar)":
    df[col_valor] = converter_numerico(df[col_valor])

if col_distancia != "(não usar)":
    df[col_distancia] = converter_numerico(df[col_distancia])

if col_data != "(não usar)":
    df[col_data] = pd.to_datetime(df[col_data], errors="coerce")

# KPIs
st.subheader("Indicadores principais")

k1, k2, k3, k4 = st.columns(4)

k1.metric("Quantidade de registros", len(df))

if col_valor != "(não usar)":
    total = df[col_valor].sum()
    k2.metric("Valor total (R$)", f"{total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
else:
    k2.metric("Valor total (R$)", "-")

if col_valor != "(não usar)":
    media = df[col_valor].mean()
    k3.metric("Ticket médio (R$)", f"{media:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
else:
    k3.metric("Ticket médio (R$)", "-")

if col_distancia != "(não usar)":
    dist_media = df[col_distancia].mean()
    k4.metric("Distância média (km)", f"{dist_media:.1f}".replace(".", ","))
else:
    k4.metric("Distância média (km)", "-")

st.divider()

# Gráficos
c1, c2 = st.columns(2)

with c1:
    st.subheader("Top prestadores")
    if col_prestador != "(não usar)":
        ranking = df[col_prestador].astype(str).value_counts().head(10)
        st.bar_chart(ranking)
    else:
        st.info("Selecione uma coluna de prestador.")

with c2:
    st.subheader("Valor por tipo")
    if col_tipo != "(não usar)" and col_valor != "(não usar)":
        tabela = df.groupby(col_tipo)[col_valor].sum().sort_values(ascending=False)
        st.bar_chart(tabela)
    else:
        st.info("Selecione coluna de tipo e valor.")

# Série temporal
st.subheader("Evolução no tempo")

if col_data != "(não usar)" and col_valor != "(não usar)":
    serie = (
        df.dropna(subset=[col_data])
          .groupby(pd.Grouper(key=col_data, freq="D"))[col_valor]
          .sum()
    )
    st.line_chart(serie)
else:
    st.info("Selecione colunas de data e valor para ver a evolução.")
