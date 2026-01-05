from pathlib import Path

Path("app.py").write_text(r'''
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import re

st.set_page_config(page_title="Dashboard de Atendimentos (2025)", layout="wide")

# ---------- Tema/estética clean ----------
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
.small-muted {color: rgba(120,120,120,.95); font-size: 0.9rem;}
.kpi-card {padding: 14px 14px 10px 14px; border-radius: 12px;
           border: 1px solid rgba(0,0,0,.08); background: rgba(0,0,0,.02);}
.kpi-label {font-size: .82rem; color: rgba(0,0,0,.65); margin-bottom: 6px;}
.kpi-value {font-size: 1.6rem; font-weight: 800; line-height: 1.1;}
.kpi-sub {font-size: .78rem; color: rgba(0,0,0,.55); margin-top: 4px;}
.hr {border-top: 1px solid rgba(0,0,0,.08); margin: 1rem 0;}
</style>
""", unsafe_allow_html=True)

st.title("Dashboard de Atendimentos — 2025")
st.markdown('<div class="small-muted">Fonte: Excel mensal por aba • Visão clean (Power BI style) • Base completa</div>', unsafe_allow_html=True)

# ---------- Helpers ----------
def br_money(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X",".")

def br_num(v, dec=1):
    if v is None or (isinstance(v, float) and np.isnan(v)): return "—"
    fmt = f"{{:,.{dec}f}}"
    return fmt.format(v).replace(",", "X").replace(".", ",").replace("X",".")

def kpi(label, value, sub=""):
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{value}</div>
      <div class="kpi-sub">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

def money_to_float(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.replace(r"[Rr]\$\s*", "", regex=True).str.strip()
    x = x.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(x, errors="coerce")

# Detecta a linha do cabeçalho (resolve Unnamed)
def detect_header_row(excel_file, sheet_name: str) -> int:
    raw = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    # procurar uma linha que contenha "CLIENTE" e "PROTOCOLO"
    for i in range(min(25, len(raw))):
        row = raw.iloc[i].astype(str).str.strip().str.upper()
        vals = set(row.values)
        if "CLIENTE" in vals and "PROTOCOLO" in vals:
            return i
    # fallback: linha com mais campos preenchidos
    counts = [raw.iloc[i].notna().sum() for i in range(min(25, len(raw)))]
    return int(np.argmax(counts)) if counts else 0

def read_sheet_clean(excel_file, sheet_name: str):
    hr = detect_header_row(excel_file, sheet_name)
    df = pd.read_excel(excel_file, sheet_name=sheet_name, header=hr)

    # remove colunas "Unnamed"
    df = df.loc[:, ~df.columns.astype(str).str.contains(r"^Unnamed", na=False)]

    # limpa nomes
    df.columns = [str(c).strip() for c in df.columns]

    return df, hr

def safe_col(df, name_candidates):
    # encontra coluna por match "case-insensitive"
    cols = list(df.columns)
    low = {c.lower(): c for c in cols}
    for cand in name_candidates:
        for c in cols:
            if cand.lower() == c.lower():
                return c
    # fallback por contém
    for cand in name_candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None

# ---------- Upload ----------
up = st.file_uploader("Envie a planilha (xlsx)", type=["xlsx"])
if not up:
    st.info("Envie o arquivo .xlsx para iniciar.")
    st.stop()

# Abas: manter só as mensais (remover '5' e limpar espaços)
xls = pd.ExcelFile(up)
raw_sheets = xls.sheet_names
sheets = []
for s in raw_sheets:
    s_clean = s.strip()
    # ignora abas claramente não-mensais (ex: "5")
    if re.fullmatch(r"\d+", s_clean):
        continue
    sheets.append(s_clean)

sheet = st.selectbox("Mês (aba)", sheets)

df, header_row = read_sheet_clean(up, sheet)
st.caption(f"Cabeçalho detectado na linha: {header_row+1} (contagem humana) • Colunas: {len(df.columns)}")

with st.expander("Prévia (primeiras linhas)", expanded=False):
    st.dataframe(df.head(30), use_container_width=True)

# ---------- Auto-mapeamento (baseado no seu arquivo real) ----------
col_data = safe_col(df, ["DATA ATENDIMENTO"])
col_valor = safe_col(df, ["VALOR"])
col_prest = safe_col(df, ["PRESTADOR"])
col_reg = safe_col(df, ["REGIONAL"])
col_placa = safe_col(df, ["PLACA"])
col_tipo = safe_col(df, ["TIPO DE VEICULO"])
col_prot = safe_col(df, ["PROTOCOLO"])

work = df.copy()

# normalizações (se existirem)
work["_data"] = pd.to_datetime(work[col_data], errors="coerce", dayfirst=True) if col_data else pd.NaT
work["_valor"] = money_to_float(work[col_valor]) if col_valor else np.nan
work["_prestador"] = work[col_prest].astype(str).str.strip() if col_prest else ""
work["_regional"] = work[col_reg].astype(str).str.strip() if col_reg else ""
work["_placa"] = work[col_placa].astype(str).str.strip() if col_placa else ""
work["_tipo"] = work[col_tipo].astype(str).str.strip() if col_tipo else ""
work["_protocolo"] = work[col_prot].astype(str).str.strip() if col_prot else ""

# ---------- Filtros (corporativo) ----------
st.sidebar.header("Filtros")

if work["_data"].notna().any():
    dmin = work["_data"].min().date()
    dmax = work["_data"].max().date()
    di, dfim = st.sidebar.date_input("Período (dentro do mês)", (dmin, dmax))
    work = work[(work["_data"].dt.date >= di) & (work["_data"].dt.date <= dfim)].copy()

if col_prest:
    prests = sorted([p for p in work["_prestador"].dropna().unique() if p and p.lower()!="nan" and p.strip()!="*"])
    sel_p = st.sidebar.multiselect("Prestador", prests, default=prests[:25] if len(prests)>25 else prests)
    if sel_p:
        work = work[work["_prestador"].isin(sel_p)].copy()

if col_reg:
    regs = sorted([r for r in work["_regional"].dropna().unique() if r and r.lower()!="nan"])
    sel_r = st.sidebar.multiselect("Regional", regs, default=regs)
    if sel_r:
        work = work[work["_regional"].isin(sel_r)].copy()

q = st.sidebar.text_input("Buscar (placa/protocolo/beneficiário)")
if q.strip():
    qq = q.strip().lower()
    target_cols = []
    for cand in ["PLACA", "BENEFICIARIO", "PROTOCOLO", "MODELO", "MARCA", "SERVIÇO", "FATO"]:
        c = safe_col(work, [cand])
        if c: target_cols.append(c)
    # fallback: usa as técnicas
    target_cols += ["_placa","_protocolo"]

    mask = False
    for c in dict.fromkeys(target_cols):  # unique preservando ordem
        if c in work.columns:
            mask = mask | work[c].astype(str).str.lower().str.contains(re.escape(qq), na=False)
    work = work[mask].copy()

# ---------- Contexto ----------
ctx = [f"Mês/Aba: **{sheet}**", f"Registros: **{len(work):,}**".replace(",", ".")]
st.markdown(" • ".join(ctx))
st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# ---------- KPIs ----------
c1,c2,c3,c4,c5,c6 = st.columns(6)

with c1:
    kpi("Atendimentos", f"{len(work):,}".replace(",", "."), "Registros no recorte")
with c2:
    total = work["_valor"].sum(skipna=True) if work["_valor"].notna().any() else np.nan
    kpi("Valor total (R$)", br_money(total), "Soma (recorte)")
with c3:
    avg = work["_valor"].mean(skipna=True) if work["_valor"].notna().any() else np.nan
    kpi("Ticket médio (R$)", br_money(avg), "Média (recorte)")
with c4:
    qprest = (work["_prestador"].astype(str).str.strip().ne("").mean()*100) if len(work) else 0
    kpi("Qualidade (Prestador)", f"{qprest:.1f}%", "% preenchido")
with c5:
    qplaca = (work["_placa"].astype(str).str.strip().ne("").mean()*100) if len(work) else 0
    kpi("Qualidade (Placa)", f"{qplaca:.1f}%", "% preenchido")
with c6:
    qprot = (work["_protocolo"].astype(str).str.strip().ne("").mean()*100) if len(work) else 0
    kpi("Qualidade (Protocolo)", f"{qprot:.1f}%", "% preenchido")

# ---------- Abas ----------
tab1, tab2, tab3 = st.tabs(["Visão Geral", "Prestadores", "Base (todas as colunas)"])

with tab1:
    colA, colB = st.columns(2)

    with colA:
        st.subheader("Atendimentos por dia")
        if work["_data"].notna().any():
            tmp = work.dropna(subset=["_data"]).copy()
            tmp["dia"] = tmp["_data"].dt.date.astype(str)
            g = tmp.groupby("dia").size().reset_index(name="qtd")
            st.plotly_chart(px.line(g, x="dia", y="qtd", markers=True), use_container_width=True)
        else:
            st.info("Sem coluna de data válida para série diária.")

    with colB:
        st.subheader("Valor por dia")
        if work["_data"].notna().any() and work["_valor"].notna().any():
            tmp = work.dropna(subset=["_data"]).copy()
            tmp["dia"] = tmp["_data"].dt.date.astype(str)
            g = tmp.groupby("dia")["_valor"].sum().reset_index()
            st.plotly_chart(px.line(g, x="dia", y="_valor", markers=True), use_container_width=True)
        else:
            st.info("Sem data/valor válidos para série de custo.")

with tab2:
    st.subheader("Ranking de prestadores")
    tmp = work.copy()
    tmp = tmp[tmp["_prestador"].astype(str).str.strip().ne("") & (tmp["_prestador"].astype(str).str.strip()!="*")]

    if len(tmp):
        a,b = st.columns(2)
        with a:
            topq = tmp.groupby("_prestador").size().sort_values(ascending=False).head(20).reset_index(name="qtd")
            st.plotly_chart(px.bar(topq, x="qtd", y="_prestador", orientation="h"), use_container_width=True)
        with b:
            if tmp["_valor"].notna().any():
                topv = tmp.groupby("_prestador")["_valor"].sum().sort_values(ascending=False).head(20).reset_index()
                st.plotly_chart(px.bar(topv, x="_valor", y="_prestador", orientation="h"), use_container_width=True)
            else:
                st.info("Sem valor válido para ranking por custo.")
    else:
        st.info("Sem prestador preenchido no recorte atual.")

with tab3:
    st.subheader("Base completa (todas as colunas)")
    # principais primeiro (se existirem), depois TODAS as demais
    prefer = []
    for c in [col_data, col_reg, col_prest, col_valor, col_placa, col_prot, col_tipo]:
        if c and c in df.columns and c not in prefer:
            prefer.append(c)

    restantes = [c for c in df.columns if c not in prefer]
    cols_ordenadas = prefer + restantes

    st.dataframe(work[cols_ordenadas], use_container_width=True, height=650)
    st.caption(f"Total de colunas exibidas: {len(cols_ordenadas)}")

    st.download_button(
        "Baixar CSV do recorte (todas as colunas)",
        work[cols_ordenadas].to_csv(index=False, encoding="utf-8-sig"),
        "atendimentos_recorte_completo.csv",
        "text/csv"
    )
''', encoding="utf-8")

print("app.py atualizado para o seu Excel (cabeçalho automático + filtro por aba + base completa)")
