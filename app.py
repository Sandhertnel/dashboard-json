from pathlib import Path

Path("app.py").write_text(r'''
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Dashboard de Atendimentos", layout="wide")

# CSS leve (clean, alinhamento, espaçamento)
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
h1, h2, h3 {letter-spacing: .2px;}
.small-muted {color: rgba(229,231,235,.75); font-size: 0.9rem;}
.kpi-card {padding: 14px 14px 10px 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,.08); background: rgba(255,255,255,.03);}
.kpi-label {font-size: .82rem; color: rgba(229,231,235,.7); margin-bottom: 6px;}
.kpi-value {font-size: 1.6rem; font-weight: 700; line-height: 1.1;}
.kpi-sub {font-size: .78rem; color: rgba(229,231,235,.55); margin-top: 4px;}
.hr {border-top: 1px solid rgba(255,255,255,.08); margin: 1rem 0;}
</style>
""", unsafe_allow_html=True)

st.title("Dashboard de Atendimentos")
st.markdown('<div class="small-muted">Entrada: Excel/CSV • Saída: KPIs, séries temporais, ranking e base filtrada</div>', unsafe_allow_html=True)

# ----------------------------
# Helpers
# ----------------------------
def money_to_float(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.replace("R$", "", regex=False).str.strip()
    x = x.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(x, errors="coerce")

def km_to_float(s: pd.Series) -> pd.Series:
    x = s.astype(str).str.lower().str.replace("km", "", regex=False).str.strip()
    x = x.str.replace(",", ".", regex=False)
    return pd.to_numeric(x, errors="coerce")

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

# ----------------------------
# Upload
# ----------------------------
up = st.file_uploader("Envie sua planilha (.xlsx ou .csv)", type=["xlsx","csv"])
if not up:
    st.info("Envie um arquivo para iniciar.")
    st.stop()

# Load
if up.name.lower().endswith(".csv"):
    df = pd.read_csv(up)
    aba = None
else:
    xls = pd.ExcelFile(up)
    aba = st.selectbox("Aba (Excel)", xls.sheet_names)
    df = pd.read_excel(up, sheet_name=aba)

df.columns = [str(c).strip() for c in df.columns]

with st.expander("Pré-visualização (primeiras linhas)", expanded=False):
    st.dataframe(df.head(30), use_container_width=True)

# ----------------------------
# Mapping (sidebar)
# ----------------------------
st.sidebar.header("Mapeamento")
cols = ["(não usar)"] + list(df.columns)

c_data  = st.sidebar.selectbox("Data", cols, index=0)
c_valor = st.sidebar.selectbox("Valor (R$)", cols, index=0)
c_km    = st.sidebar.selectbox("Distância (km)", cols, index=0)
c_prest = st.sidebar.selectbox("Prestador", cols, index=0)
c_tipo  = st.sidebar.selectbox("Tipo (Truck/Veicular)", cols, index=0)
c_reg   = st.sidebar.selectbox("Região/Cidade", cols, index=0)
c_placa = st.sidebar.selectbox("Placa", cols, index=0)

work = df.copy()
work["_data"] = pd.to_datetime(work[c_data], errors="coerce", dayfirst=True) if c_data!="(não usar)" else pd.NaT
work["_valor"] = money_to_float(work[c_valor]) if c_valor!="(não usar)" else np.nan
work["_km"] = km_to_float(work[c_km]) if c_km!="(não usar)" else np.nan
work["_prestador"] = work[c_prest].astype(str).str.strip() if c_prest!="(não usar)" else ""
work["_tipo"] = work[c_tipo].astype(str).str.strip() if c_tipo!="(não usar)" else "Indefinido"
work["_regiao"] = work[c_reg].astype(str).str.strip() if c_reg!="(não usar)" else ""
work["_placa"] = work[c_placa].astype(str).str.strip() if c_placa!="(não usar)" else ""

# ----------------------------
# Filters (sidebar)
# ----------------------------
st.sidebar.header("Filtros")

if work["_data"].notna().any():
    dmin = work["_data"].min().date()
    dmax = work["_data"].max().date()
    di, dfim = st.sidebar.date_input("Período", (dmin, dmax))
    work = work[(work["_data"].dt.date>=di) & (work["_data"].dt.date<=dfim)].copy()
else:
    di = dfim = None

if c_tipo!="(não usar)":
    tipos = sorted([t for t in work["_tipo"].dropna().unique() if t and t.lower()!="nan"])
    sel_t = st.sidebar.multiselect("Tipo", tipos, default=tipos)
    if sel_t: work = work[work["_tipo"].isin(sel_t)].copy()

if c_prest!="(não usar)":
    prests = sorted([p for p in work["_prestador"].dropna().unique() if p and p.lower()!="nan"])
    sel_p = st.sidebar.multiselect("Prestador", prests, default=prests[:30] if len(prests)>30 else prests)
    if sel_p: work = work[work["_prestador"].isin(sel_p)].copy()

if c_reg!="(não usar)":
    regs = sorted([r for r in work["_regiao"].dropna().unique() if r and r.lower()!="nan"])
    sel_r = st.sidebar.multiselect("Região", regs, default=regs)
    if sel_r: work = work[work["_regiao"].isin(sel_r)].copy()

# ----------------------------
# Header context
# ----------------------------
ctx = []
ctx.append(f"Registros: **{len(work):,}**".replace(",", "."))
if di and dfim:
    ctx.append(f"Período: **{di.strftime('%d/%m/%Y')} → {dfim.strftime('%d/%m/%Y')}**")
ctx.append(f"Fonte: **{up.name}**" + (f" • Aba: **{aba}**" if aba else ""))
st.markdown(" • ".join(ctx))

st.markdown('<div class="hr"></div>', unsafe_allow_html=True)

# ----------------------------
# KPIs (clean)
# ----------------------------
kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

with kpi1:
    kpi("Atendimentos", f"{len(work):,}".replace(",", "."), "Registros no recorte")
with kpi2:
    kpi("Valor total (R$)", "—" if work["_valor"].isna().all() else br_money(work["_valor"].sum(skipna=True)), "Soma do recorte")
with kpi3:
    kpi("Ticket médio (R$)", "—" if work["_valor"].isna().all() else br_money(work["_valor"].mean(skipna=True)), "Média do recorte")
with kpi4:
    kpi("KM total", "—" if work["_km"].isna().all() else br_num(work["_km"].sum(skipna=True), 1), "Soma do recorte")
with kpi5:
    kpi("KM médio", "—" if work["_km"].isna().all() else br_num(work["_km"].mean(skipna=True), 1), "Média do recorte")
with kpi6:
    quality = (work["_prestador"].astype(str).str.strip()!="").mean()*100 if len(work) else 0
    kpi("Qualidade (Prestador)", f"{quality:.1f}%", "% com prestador preenchido")

# ----------------------------
# Tabs
# ----------------------------
tab1, tab2, tab3, tab4 = st.tabs(["Visão Geral", "Prestadores", "Regiões", "Base"])

with tab1:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Atendimentos ao longo do tempo")
        if work["_data"].notna().any():
            tmp = work.dropna(subset=["_data"]).copy()
            tmp["mes"] = tmp["_data"].dt.to_period("M").astype(str)
            serie = tmp.groupby("mes").size().reset_index(name="qtd")
            st.plotly_chart(px.line(serie, x="mes", y="qtd", markers=True), use_container_width=True)
        else:
            st.info("Mapeie a coluna de data para habilitar a série temporal.")

    with c2:
        st.subheader("Valor ao longo do tempo")
        if work["_data"].notna().any() and work["_valor"].notna().any():
            tmp = work.dropna(subset=["_data"]).copy()
            tmp["mes"] = tmp["_data"].dt.to_period("M").astype(str)
            g = tmp.groupby("mes")["_valor"].sum().reset_index()
            st.plotly_chart(px.line(g, x="mes", y="_valor", markers=True), use_container_width=True)
        else:
            st.info("Mapeie data e valor para habilitar a série de custo.")

with tab2:
    st.subheader("Ranking de prestadores")
    tmp = work.copy()
    tmp["_prestador"] = tmp["_prestador"].astype(str).str.strip()
    tmp = tmp[tmp["_prestador"]!=""]

    if len(tmp):
        colA, colB = st.columns(2)

        with colA:
            topq = tmp.groupby("_prestador").size().sort_values(ascending=False).head(20).reset_index(name="qtd")
            st.plotly_chart(px.bar(topq, x="qtd", y="_prestador", orientation="h"), use_container_width=True)

        with colB:
            if tmp["_valor"].notna().any():
                topv = tmp.groupby("_prestador")["_valor"].sum().sort_values(ascending=False).head(20).reset_index()
                st.plotly_chart(px.bar(topv, x="_valor", y="_prestador", orientation="h"), use_container_width=True)
            else:
                st.info("Mapeie a coluna de valor para ranking por custo.")
    else:
        st.info("Sem prestador preenchido no recorte.")

with tab3:
    st.subheader("Regiões")
    if c_reg!="(não usar)" and work["_regiao"].astype(str).str.strip().ne("").any():
        g = work.groupby("_regiao").size().sort_values(ascending=False).head(25).reset_index(name="qtd")
        st.plotly_chart(px.bar(g, x="qtd", y="_regiao", orientation="h"), use_container_width=True)
    else:
        st.info("Mapeie a coluna de região/cidade para habilitar esta aba.")

with tab4:
    st.subheader("Base filtrada (clean)")
    # colunas principais primeiro
    prefer = ["_data","_tipo","_prestador","_valor","_km","_regiao","_placa"]
    prefer = [c for c in prefer if c in work.columns]
    cols = prefer + [c for c in work.columns if c not in prefer]

    st.dataframe(work[cols], use_container_width=True, height=520)

    st.download_button(
        "Baixar CSV do recorte",
        work[cols].to_csv(index=False, encoding="utf-8-sig"),
        "atendimentos_filtrados.csv",
        "text/csv"
    )
''', encoding="utf-8")

print("app.py (Power BI clean) criado")
