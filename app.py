import json
import re
from collections import Counter
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dashboard Trello (Cards + Texto)", layout="wide")
st.title("Dashboard Trello — Tratamento de Conteúdo dos Cards")

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
# Extrair cards e actions
# -----------------------------
cards = data.get("cards", [])
actions = data.get("actions", [])

if not isinstance(cards, list) or not cards:
    st.error("Não encontrei data['cards'] no JSON. Confirme que é export do Trello (board).")
    st.stop()

cards_df = pd.json_normalize(cards, sep=".")

# Comentários: actions.type == commentCard  -> data.text + data.card.id
comments = []
if isinstance(actions, list) and actions:
    for a in actions:
        if isinstance(a, dict) and a.get("type") == "commentCard":
            d = a.get("data", {}) or {}
            card = d.get("card", {}) or {}
            comments.append({
                "card_id": card.get("id"),
                "comment_text": d.get("text"),
                "comment_date": a.get("date"),
            })

comments_df = pd.DataFrame(comments)

# Agrupar comentários por card_id
if not comments_df.empty:
    comments_df["comment_text"] = comments_df["comment_text"].fillna("").astype(str)
    agg = comments_df.groupby("card_id")["comment_text"].apply(lambda x: " \n".join([t for t in x if t.strip()]))
    comments_map = agg.to_dict()
else:
    comments_map = {}

# -----------------------------
# Funções de limpeza e classificação
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

# Regras simples e eficazes (baseline)
TRUCK_KW = ["caminhao", "caminhão", "axor", "atego", "mb", "mercedes", "scania", "volvo", "carreta", "bitrem", "truck"]
VEIC_KW  = ["carro", "passeio", "hb20", "onix", "gol", "palio", "civic", "corolla", "moto", "motocicleta"]

CATEGORIAS = {
    "Acidente": ["acidente", "colis", "batida", "capot", "tombou", "saiu da pista"],
    "Pane elétrica": ["pane eletrica", "pane elétrica", "bateria", "alternador", "não dá partida", "nao da partida", "curto", "fiação", "fiação"],
    "Pane mecânica": ["pane mecanica", "pane mecânica", "motor", "cambio", "câmbio", "embreagem", "superaquec", "quebrou", "vazamento"],
    "Guincho/Remoção": ["guincho", "reboque", "remoção", "remocao", "plataforma", "prancha"],
    "Pneu": ["pneu", "estouro", "furou", "estepe", "calibr"],
    "Chave/Trava": ["chave", "trava", "trancou", "chaveiro"],
}

def classificar_tipo_veiculo(texto_norm: str) -> str:
    t = texto_norm
    truck = any(k in t for k in TRUCK_KW)
    veic  = any(k in t for k in VEIC_KW)
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
# Montar dataset final (texto_total)
# -----------------------------
# Campos comuns do Trello
id_col = "id" if "id" in cards_df.columns else None
name_col = "name" if "name" in cards_df.columns else None
desc_col = "desc" if "desc" in cards_df.columns else None
closed_col = "closed" if "closed" in cards_df.columns else None
last_col = "dateLastActivity" if "dateLastActivity" in cards_df.columns else None
closed_date_col = "dateClosed" if "dateClosed" in cards_df.columns else None

df = cards_df.copy()

if id_col is None:
    st.error("Não encontrei coluna 'id' nos cards.")
    st.stop()

df["title"] = df[name_col].fillna("").astype(str) if name_col else ""
df["desc_clean"] = df[desc_col].apply(clean_text) if desc_col else ""
df["comments_clean"] = df[id_col].map(lambda cid: clean_text(comments_map.get(cid, "")))

df["texto_total"] = (df["title"].fillna("") + "\n" + df["desc_clean"].fillna("") + "\n" + df["comments_clean"].fillna("")).str.strip()
df["texto_norm"] = df["texto_total"].apply(norm_for_rule_]()_]()
