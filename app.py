"""Visualizador da base de cotações.  Rode com:  streamlit run app.py"""
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from base_cotacoes import atualizar, db, fonte

st.set_page_config(page_title="Base de Cotações", layout="wide")
con = db.conectar()

st.sidebar.header("Ativos")
with st.sidebar.form("novo"):
    novos = st.text_input("Adicionar tickers (separados por espaço)", placeholder="PETR4.SA VALE3.SA AAPL")
    ini_novo = st.date_input("Baixar a partir de", value=date(2010, 1, 1))
    if st.form_submit_button("Adicionar") and novos.strip():
        for t in novos.upper().split():
            nome, moeda = fonte.info(t)
            db.registrar_ativo(con, t, nome, moeda)
            n = atualizar.atualizar_ativo(con, t, inicio=ini_novo)
            st.write(f"{t}: {n} registros")
if st.sidebar.button("Atualizar todos"):
    with st.spinner("Baixando cotações..."):
        logs = []
        atualizar.atualizar_todos(con, log=logs.append)
    st.sidebar.code("\n".join(logs))

ativos = db.listar_ativos(con)
if ativos.empty:
    st.title("Base de Cotações")
    st.info("A base está vazia. Adicione ativos na barra lateral (ações da B3 usam o sufixo .SA).")
    st.stop()

intervalos = sorted(ativos["intervalo"].dropna().unique()) or ["1d"]
intervalo = st.sidebar.selectbox("Intervalo", intervalos, index=intervalos.index("1d") if "1d" in intervalos else 0)
disp = ativos[ativos["intervalo"] == intervalo]
tickers = st.sidebar.multiselect("Ativos exibidos", disp["ticker"].tolist(), default=disp["ticker"].tolist()[:5])
campo = st.sidebar.selectbox("Campo", db.COLUNAS, index=db.COLUNAS.index("fech_ajust"))

st.title("Base de Cotações")
st.dataframe(ativos, hide_index=True, width="stretch")
if not tickers:
    st.stop()

pmin = pd.to_datetime(disp[disp.ticker.isin(tickers)]["primeiro"]).min().date()
pmax = pd.to_datetime(disp[disp.ticker.isin(tickers)]["ultimo"]).max().date()
c1, c2, c3 = st.columns(3)
inicio = c1.date_input("Início", value=pmin, min_value=pmin, max_value=pmax)
fim = c2.date_input("Fim", value=pmax, min_value=pmin, max_value=pmax)
base100 = c3.checkbox("Normalizar (base 100)")

tabela = db.tabela_precos(con, tickers, inicio, fim, intervalo, campo)
serie = tabela / tabela.bfill().iloc[0] * 100 if base100 else tabela

fig = go.Figure()
for t in serie.columns:
    fig.add_scatter(x=serie.index, y=serie[t], name=t, mode="lines")
fig.update_layout(hovermode="x unified", height=480, margin=dict(l=10, r=10, t=30, b=10))
st.plotly_chart(fig, width="stretch")

st.subheader("Preço em um momento")
m1, m2 = st.columns(2)
dia = m1.date_input("Data", value=fim, key="dia")
hora = m2.time_input("Hora (intradiário)", value=None) if intervalo != "1d" else None
momento = f"{dia} {hora}" if hora else str(dia)
linhas = []
for t in tickers:
    r = db.preco_em(con, t, momento, intervalo)
    if r:
        linhas.append({"ticker": t, **r})
st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")

st.subheader("Tabela de preços")
st.dataframe(tabela.sort_index(ascending=False), width="stretch")
st.download_button("Baixar CSV", tabela.to_csv().encode("utf-8"), "cotacoes.csv", "text/csv")
