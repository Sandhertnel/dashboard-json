import json
import re
from collections import Counter, defaultdict
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Assistência 24h — Pipeline Trello", layout="wide")
st.title("Assistência 24h — Dashboard da Pipeline (Trello)")
st.caption("Leitura e tratamento de conteúdo dos cards + status por listas do Trello.")

# -----------------------------
# Upload
# -----------------------------
uploaded = st.file_uploader("Envie o JSON exportado do Trello (board)", type=["json"])
if not uploaded:
    st.info("Envie o arquivo .json para iniciar.")
    st.stop()

try:
    data = json.load(uploaded)
except Exception as e:
    st.error(f"Erro ao ler JSON: {e}")
    st.stop()

cards = data.get("cards", [])
lists = data.get("lists", [])
actions = data.get("actions", [])
members = data.get("members", [])

if not isinstance(cards, list) or not cards:
    st.error("Não encontrei data['cards']. Confirme que é export do board do Trello.")
    st.stop()

# -----------------------------
# Mapas (listas e membros)
# -----------------------------
list_map = {l.get("id"): l.get("name") for l in lists if isinstance(l, dict)}
member_map = {m.get("id"): (m.get("fullName") or m.get("username") or m.get("id")) for m in members if isinstance(m, dict)}

# Comentários (se existirem) — no seu JSON existem poucos, mas vamos aproveitar
comments_map = defaultdict(list)
if isinstance(actions, list) and actions:
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "commentCard":
            d = a.get("data", {}) or {}
            card_id = d.get("idCard") or (d.get("card", {}) or {}).get("id")
            txt = d.get("text")
            if card_id and txt:
                comments_map[card_id].append(str(txt))

def join_comments(card_id: str) -> str:
    lst = comments_map.get(card_id, [])
    return "\n".join([t for t in lst if t.strip()])

# -----------------------------
# Normalização dos cards
# -----------------------------
df = pd.json_normalize(cards, sep=".")
# colunas relevantes
if "idList" in df.columns:
    df["status_lista"] = df["idList"].map(list_map).fillna("SEM LISTA")
else:
    df["status_lista"] = "SEM LISTA"

# membros (idMembers é lista)
if "idMembers" in df.columns:
    tmp = df[["id", "idMembers"]].copy()
    tmp["idMembers"] = tmp["idMembers"].apply(lambda x: x if isinstance(x, list) else [])
    tmp = tmp.explode("idMembers").dropna()
    if len(tmp):
        tmp["membro_nome"] = tmp["idMembers"].map(member_map).fillna(tmp["idMembers"].astype(str))
        memb_agg = tmp.groupby("id")["membro_nome"].apply(lambda x: ", ".join(sorted(set(x.astype(str)))))
        df["responsaveis"] = df["id"].map(memb_agg).fillna("")
    else:
        df["responsaveis"] = ""
else:
    df["responsaveis"] = ""

# datas
if "dateLastActivity" in df.columns:
    df["dateLastActivity"] = pd.to_datetime(df["dateLastActivity"], errors="coerce", utc=True).dt.tz_convert(None)
else:
    df["dateLastActivity"] = pd.NaT

if "dateClosed" in df.columns:
    df["dateClosed"] = pd.to_datetime(df["dateClosed"], errors="coerce", utc=True).dt.tz_convert(None)
else:
    df["dateClosed"] = pd.NaT

# -----------------------------
# Tratamento de texto (name + desc + comentários)
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

df["name"] = df.get("name", "").fillna("").astype(str)
df["desc"] = df.get("desc", "").fillna("").astype(str)
df["comments"] = df["id"].map(lambda cid: clean_text(join_comments(cid))).fillna("")

df["texto_total"] = (
    df["name"].apply(clean_text)
    + "\n"
    + df["desc"].apply(clean_text)
    + ("\n" + df["comments"]).fillna("")
).str.strip()

df["texto_norm"] = df["texto_total"].apply(norm_for_rules)

# -----------------------------
# Classificação (baseline) — você pode evoluir depois
# -----------------------------
TRUCK_KW = [
    "caminhao", "caminhão", "axor", "atego", "mb", "mercedes", "scania", "volvo", "carreta", "bitrem",
    "cavalo", "carreta", "truck", "implemento"
]
VEIC_KW = [
    "carro", "passeio", "hb20", "onix", "gol", "palio", "civic", "corolla", "moto", "motocicleta",
    "utilitario", "utilitário", "van", "fiorino"
]

CATEGORIAS = {
    "Acidente": ["acidente", "colis", "batida", "capot", "tombou", "tombamento", "saiu da pista", "sinistro"],
    "Guincho/Remoção": ["guincho", "reboque", "remoção", "remocao", "plataforma", "prancha", "rebocar"],
    "Pane elétrica": ["pane eletrica", "pane elétrica", "bateria", "alternador", "arranque", "não dá partida", "nao da partida", "curto", "fiacao", "fiação", "fusivel"],
    "Pane mecânica": ["pane mecanica", "pane mecânica", "motor", "cambio", "câmbio", "embreagem", "superaquec", "aquecendo", "ferveu", "vazamento", "travou", "quebrou"],
    "Pneu/Rodagem": ["pneu", "estouro", "furou", "furo", "estepe", "roda", "prisioneiro", "porca", "parafuso"],
    "Combustível": ["sem combustivel", "sem combustível", "pane seca", "falta de combustivel", "falta de combustível", "abastec", "diesel", "gasolina", "etanol"],
    "Chaveiro/Trava": ["chave", "chaveiro", "trava", "trancou", "perdeu a chave", "chave dentro", "imobilizador"],
    "Atolamento/Retirada": ["atol", "atolado", "lama", "areia", "buraco", "vala", "ribanceira", "fora da pista"],
    "Outros": []
}

def classificar_tipo_veiculo(texto_norm: str) -> str:
    truck = any(k in texto_norm for k in TRUCK_KW)
    veic = any(k in texto_norm for k in VEIC_KW)
    if truck and not veic:
        return "Truck"
    if veic and not truck:
        return "Veicular"
    if truck and veic:
        return "Misto"
    return "Não identificado"

def classificar_categoria(texto_norm: str) -> str:
    for cat, kws in CATEGORIAS.items():
        if cat == "Outros":
            continue
        if any(k in texto_norm for k in kws):
            return cat
    return "Outros"

df["tipo_veiculo"] = df["texto_norm"].apply(classificar_tipo_veiculo)
df["categoria"] = df["texto_norm"].apply(classificar_categoria)

# -----------------------------
# Definir “Concluído” pela lista (regra principal do seu processo)
# -----------------------------
STATUS_CONCLUIDO = "100% Concluído"
df["concluido"] = df["status_lista"].astype(str).str.strip().eq(STATUS_CONCLUIDO)

# -----------------------------
# Sidebar: filtros
# -----------------------------
st.sidebar.header("Filtros")

df_f = df.copy()

# período
if df_f["dateLastActivity"].notna().any():
    min_d = df_f["dateLastActivity"].min()
    max_d = df_f["dateLastActivity"].max()
    d1, d2 = st.sidebar.date_input("Período (dateLastActivity)", value=(min_d.date(), max_d.date()))
    df_f = df_f[(df_f["dateLastActivity"].dt.date >= d1) & (df_f["dateLastActivity"].dt.date <= d2)]

# status por lista
status_opts = sorted(df_f["status_lista"].astype(str).unique().tolist())
sel_status = st.sidebar.multiselect("Status (Lista)", status_opts, default=status_opts)
df_f = df_f[df_f["status_lista"].astype(str).isin(sel_status)]

# concluído
sel_conc = st.sidebar.multiselect("Concluído?", ["Concluído", "Não concluído"], default=["Concluído", "Não concluído"])
mask_conc = pd.Series([True] * len(df_f), index=df_f.index)
if "Concluído" in sel_conc and "Não concluído" not in sel_conc:
    mask_conc = df_f["concluido"] == True
elif "Não concluído" in sel_conc and "Concluído" not in sel_conc:
    mask_conc = df_f["concluido"] == False
df_f = df_f[mask_conc]

# categoria e tipo
cat_opts = sorted(df_f["categoria"].unique().tolist())
sel_cat = st.sidebar.multiselect("Categoria (texto)", cat_opts, default=cat_opts)
df_f = df_f[df_f["categoria"].isin(sel_cat)]

tipo_opts = sorted(df_f["tipo_veiculo"].unique().tolist())
sel_tipo = st.sidebar.multiselect("Tipo de veículo (texto)", tipo_opts, default=tipo_opts)
df_f = df_f[df_f["tipo_veiculo"].isin(sel_tipo)]

# responsáveis
if "responsaveis" in df_f.columns:
    resp_opts = sorted([r for r in df_f["responsaveis"].dropna().unique().tolist() if str(r).strip() != ""])
    if resp_opts:
        sel_resp = st.sidebar.multiselect("Responsáveis", resp_opts, default=resp_opts)
        if sel_resp:
            df_f = df_f[df_f["responsaveis"].astype(str).isin(sel_resp)]

# busca textual
q = st.sidebar.text_input("Buscar no texto (name/desc)")
if q.strip():
    qn = q.strip().lower()
    df_f = df_f[df_f["texto_norm"].str.contains(re.escape(qn), na=False)]

# -----------------------------
# Abas
# -----------------------------
tab_pipeline, tab_kpi, tab_texto, tab_cards = st.tabs(["Pipeline", "Indicadores", "Texto", "Cards"])

with tab_pipeline:
    st.subheader("Visão da Pipeline (por Lista/Status)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Cards (filtrado)", f"{len(df_f):,}".replace(",", "."))
    c2.metric("Concluídos", f"{int(df_f['concluido'].sum()):,}".replace(",", "."))
    c3.metric("Não concluídos", f"{int((~df_f['concluido']).sum()):,}".replace(",", "."))
    pct = (df_f["concluido"].mean() * 100) if len(df_f) else 0
    c4.metric("% Concluídos", f"{pct:.1f}%".replace(".", ","))

    st.divider()

    st.write("**Cards por status (lista)**")
    st.bar_chart(df_f["status_lista"].value_counts())

    st.divider()

    st.write("**Matriz: Status x Categoria**")
    pivot = pd.crosstab(df_f["status_lista"], df_f["categoria"])
    st.dataframe(pivot, use_container_width=True)

with tab_kpi:
    st.subheader("Indicadores operacionais")

    colA, colB = st.columns(2)
    with colA:
        st.write("**Cards por categoria**")
        st.bar_chart(df_f["categoria"].value_counts())

    with colB:
        st.write("**Truck vs Veicular (inferido do texto)**")
        st.bar_chart(df_f["tipo_veiculo"].value_counts())

    st.divider()

    st.subheader("Evolução no tempo")
    tmp = df_f.dropna(subset=["dateLastActivity"]).copy()
    if len(tmp):
        serie_m = tmp.groupby(pd.Grouper(key="dateLastActivity", freq="M")).size().sort_index()
        st.line_chart(serie_m)
    else:
        st.info("Sem datas válidas em dateLastActivity no recorte atual.")

    st.divider()

    st.subheader("Ranking de responsáveis (quantidade de cards)")
    if "responsaveis" in df_f.columns and df_f["responsaveis"].astype(str).str.strip().ne("").any():
        st.bar_chart(df_f["responsaveis"].value_counts().head(15))
    else:
        st.info("Não há responsáveis preenchidos nos cards (ou estão vazios).")

with tab_texto:
    st.subheader("Insights do texto (termos mais frequentes)")
    texto = " ".join(df_f["texto_norm"].fillna("").tolist())
    tokens = re.findall(r"[a-zà-ú0-9]{3,}", texto, flags=re.IGNORECASE)

    stop = set([
        "para","com","não","nao","uma","que","por","sem","mais","muito","onde","foi","vai","já","ja",
        "dos","das","ele","ela","seu","sua","nos","nós","sim","aos","de","do","da","em","no","na",
        "um","e","ou","ao","à","as","os","o","a","boa","tarde","dia","noite","favor","preciso",
        "segue","ola","olá","atendimento","protocolo","informacoes","informações","veiculo","veículo",
        "condutor","associado","beneficiario","beneficiário"
    ])

    tokens = [t.lower() for t in tokens if t.lower() not in stop]
    top = Counter(tokens).most_common(40)
    top_df = pd.DataFrame(top, columns=["termo", "freq"])
    st.dataframe(top_df, use_container_width=True, height=420)

    st.divider()
    st.subheader("Exemplos (cards) do recorte atual")
    st.caption("Dica: use os filtros para isolar uma categoria e veja os textos reais.")
    show_cols = ["status_lista", "categoria", "tipo_veiculo", "responsaveis", "dateLastActivity", "name", "desc"]
    show_cols = [c for c in show_cols if c in df_f.columns]
    st.dataframe(df_f[show_cols].head(50), use_container_width=True, height=420)

with tab_cards:
    st.subheader("Tabela completa (normalizada) — recorte filtrado")
    st.dataframe(df_f, use_container_width=True, height=520)
    csv = df_f.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar CSV (recorte filtrado)", csv, file_name="trello_cards_filtrado.csv", mime="text/csv")
