import json
import re
from collections import Counter
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dashboard Trello (Conteúdo dos Cards)", layout="wide")
st.title("Dashboard Trello — Conteúdo dos Cards (name + desc)")

# -----------------------------
# Upload
# -----------------------------
uploaded = st.file_uploader("Envie o JSON exportado do Trello", type=["json"])
if not uploaded:
    st.info("Envie o arquivo .json para iniciar.")
    st.stop()

try:
    data = json.load(uploaded)
except Exception as e:
    st.error(f"Erro ao ler JSON: {e}")
    st.stop()

# -----------------------------
# Extrair cards (sem actions)
# -----------------------------
cards = data.get("cards", [])

if not isinstance(cards, list) or not cards:
    st.error("Não encontrei data['cards'] no JSON. Confirme que é export do Trello (board).")
    st.stop()

df = pd.json_normalize(cards, sep=".")

# -----------------------------
# Limpeza e classificação (baseline)
# -----------------------------
def clean_text(s: str) -> str:
    s = "" if s is None else str(s)
    s = s.replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def norm_for_rules(s: str) -> str:
    s = "" if s is None else str(s).lower()
    s = re.sub(r"\s+", " ", s)
    return s

TRUCK_KW = ["caminhao", "caminhão", "axor", "atego", "mb", "mercedes", "scania", "volvo", "carreta", "bitrem", "truck"]
VEIC_KW  = ["carro", "passeio", "hb20", "onix", "gol", "palio", "civic", "corolla", "moto", "motocicleta", "utilitario", "utilitário"]

CATEGORIAS = {
    "Acidente": ["acidente", "colis", "batida", "capot", "tombou", "saiu da pista", "sinistro"],
    "Pane elétrica": ["pane eletrica", "pane elétrica", "bateria", "alternador", "não dá partida", "nao da partida", "curto", "fiação", "fiacao"],
    "Pane mecânica": ["pane mecanica", "pane mecânica", "motor", "cambio", "câmbio", "embreagem", "superaquec", "quebrou", "vazamento"],
    "Guincho/Remoção": ["guincho", "reboque", "remoção", "remocao", "plataforma", "prancha"],
    "Pneu": ["pneu", "estouro", "furou", "estepe", "calibr"],
    "Chave/Trava": ["chave", "trava", "trancou", "chaveiro"],
}

def classificar_tipo_veiculo(texto_norm: str) -> str:
    truck = any(k in texto_norm for k in TRUCK_KW)
    veic  = any(k in texto_norm for k in VEIC_KW)
    if truck and not veic:
        return "Truck"
    if veic and not truck:
        return "Veicular"
    if truck and veic:
        return "Misto"
    return "Não identificado"

def classificar_categoria(texto_norm: str) -> str:
    for cat, kws in CATEGORIAS.items():
        if any(k in texto_norm for k in kws):
            return cat
    return "Outros"

# -----------------------------
# Montar texto_total (name + desc)
# -----------------------------
name_col = "name" if "name" in df.columns else None
desc_col = "desc" if "desc" in df.columns else None
closed_col = "closed" if "closed" in df.columns else None

date_col = None
for cand in ["dateLastActivity", "dateClosed", "dateCompleted", "date"]:
    if cand in df.columns:
        date_col = cand
        break

df["title"] = df[name_col].fillna("").astype(str) if name_col else ""
df["desc_clean"] = df[desc_col].apply(clean_text) if desc_col else ""
df["texto_total"] = (df["title"] + "\n" + df["desc_clean"]).str.strip()
df["texto_norm"] = df["texto_total"].apply(norm_for_rules)

df["tipo_veiculo"] = df["texto_norm"].apply(classificar_tipo_veiculo)
df["categoria"] = df["texto_norm"].apply(classificar_categoria)

if date_col:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce", utc=True).dt.tz_convert(None)

# -----------------------------
# Sidebar: filtros
# -----------------------------
st.sidebar.header("Filtros")

df_f = df.copy()

if date_col and df_f[date_col].notna().any():
    min_d = df_f[date_col].min()
    max_d = df_f[date_col].max()
    d1, d2 = st.sidebar.date_input("Período", value=(min_d.date(), max_d.date()))
    df_f = df_f[(df_f[date_col].dt.date >= d1) & (df_f[date_col].dt.date <= d2)]

cats = sorted(df_f["categoria"].unique().tolist())
sel_cats = st.sidebar.multiselect("Categoria", cats, default=cats)
df_f = df_f[df_f["categoria"].isin(sel_cats)]

tipos = sorted(df_f["tipo_veiculo"].unique().tolist())
sel_tipos = st.sidebar.multiselect("Tipo de veículo", tipos, default=tipos)
df_f = df_f[df_f["tipo_veiculo"].isin(sel_tipos)]

# -----------------------------
# Abas
# -----------------------------
tab1, tab2, tab3 = st.tabs(["Dados", "Indicadores", "Texto (insights)"])

with tab1:
    st.subheader("Prévia dos cards (conteúdo tratado)")
    cols_show = []
    for c in ["id", "name", "closed", date_col, "tipo_veiculo", "categoria"]:
        if c and c in df_f.columns and c not in cols_show:
            cols_show.append(c)

    st.dataframe(df_f[cols_show + ["texto_total"]].head(50), use_container_width=True, height=420)

    csv = df_f.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV (filtrado)", csv, file_name="cards_tratados_filtrado.csv", mime="text/csv")

with tab2:
    st.subheader("Indicadores principais")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de cards (filtrado)", f"{len(df_f):,}".replace(",", "."))

    if closed_col:
        fechados = int(df_f[closed_col].fillna(False).astype(bool).sum())
        abertos = len(df_f) - fechados
        c2.metric("Abertos", f"{abertos:,}".replace(",", "."))
        c3.metric("Fechados", f"{fechados:,}".replace(",", "."))
        pct = (fechados / len(df_f) * 100) if len(df_f) else 0
        c4.metric("% Fechados", f"{pct:.1f}%".replace(".", ","))
    else:
        c2.metric("Abertos", "-")
        c3.metric("Fechados", "-")
        c4.metric("% Fechados", "-")

    st.divider()

    colA, colB = st.columns(2)
    with colA:
        st.subheader("Cards por categoria")
        st.bar_chart(df_f["categoria"].value_counts())

    with colB:
        st.subheader("Truck vs Veicular")
        st.bar_chart(df_f["tipo_veiculo"].value_counts())

    if date_col:
        st.divider()
        st.subheader(f"Evolução mensal ({date_col})")
        serie = df_f.dropna(subset=[date_col]).groupby(pd.Grouper(key=date_col, freq="M")).size().sort_index()
        st.line_chart(serie)

with tab3:
    st.subheader("Insights do texto (palavras frequentes)")

    texto = " ".join(df_f["texto_norm"].fillna("").tolist())
    tokens = re.findall(r"[a-zà-ú0-9]{3,}", texto, flags=re.IGNORECASE)

    stop = set([
        "para","com","não","nao","uma","que","por","sem","mais","muito","onde","foi","vai","já","ja",
        "dos","das","ele","ela","seu","sua","nos","nós","sim","aos","de","do","da","em","no","na",
        "um","e","ou","ao","à","as","os","o","a","boa","tarde","dia","noite","favor","preciso",
        "segue","ola","olá","atendimento","protocolo","informacoes","informações","veiculo","veículo"
    ])

    tokens = [t.lower() for t in tokens if t.lower() not in stop]
    top = Counter(tokens).most_common(40)

    top_df = pd.DataFrame(top, columns=["termo", "freq"])
    st.dataframe(top_df, use_container_width=True, height=420)

    st.caption("Se quiser, eu adiciono um painel de 'exemplos' (cards que mais citam cada termo/categoria).")
