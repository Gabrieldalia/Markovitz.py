"""Rotina de atualização incremental da base."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from . import db, fonte

# limites do Yahoo para dados intradiários (dias de histórico)
LIMITE_INTRADAY = {"1m": 7, "2m": 59, "5m": 59, "15m": 59, "30m": 59, "60m": 729, "90m": 59, "1h": 729}


def atualizar_ativo(con, ticker: str, intervalo: str = "1d", inicio=None, baixar=fonte.baixar) -> int:
    ultimo = db.ultimo_momento(con, ticker, intervalo)
    if ultimo:
        # rebaixa a partir do último registro (corrige o candle do dia, que pode ter mudado)
        inicio = pd.Timestamp(ultimo).date()
    elif inicio is None and intervalo in LIMITE_INTRADAY:
        inicio = date.today() - timedelta(days=LIMITE_INTRADAY[intervalo])
    fim = date.today() + timedelta(days=1) if inicio else None
    df = baixar(ticker, inicio, fim, intervalo)
    return db.gravar_cotacoes(con, ticker, df, intervalo)


def atualizar_todos(con, intervalo: str = "1d", baixar=fonte.baixar, log=print) -> None:
    tickers = [r[0] for r in con.execute("SELECT ticker FROM ativos ORDER BY ticker")]
    for t in tickers:
        try:
            n = atualizar_ativo(con, t, intervalo, baixar=baixar)
            log(f"{t:<12} {n:>6} registros gravados")
        except Exception as e:  # um ativo com erro não interrompe os demais
            log(f"{t:<12} ERRO: {e}")
