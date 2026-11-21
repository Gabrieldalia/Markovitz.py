"""Download de cotações (Yahoo Finance via yfinance)."""
from __future__ import annotations

import pandas as pd

MAPA = {
    "Open": "abertura", "High": "maxima", "Low": "minima",
    "Close": "fechamento", "Adj Close": "fech_ajust", "Volume": "volume",
}


def baixar(ticker: str, inicio=None, fim=None, intervalo: str = "1d") -> pd.DataFrame:
    import yfinance as yf

    kwargs = dict(interval=intervalo, auto_adjust=False, progress=False, actions=False)
    if inicio is None and fim is None:
        kwargs["period"] = "max"
    else:
        kwargs["start"], kwargs["end"] = inicio, fim
    df = yf.download(ticker, **kwargs)
    if df is None or df.empty:
        return pd.DataFrame(columns=list(MAPA.values()))
    if isinstance(df.columns, pd.MultiIndex):  # yfinance >= 0.2.5x devolve (campo, ticker)
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=MAPA)
    for c in MAPA.values():
        if c not in df.columns:
            df[c] = None
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:  # intradiário: guarda no fuso da bolsa, sem tz
        idx = idx.tz_localize(None)
    df.index = idx
    return df[list(MAPA.values())].dropna(how="all")


def info(ticker: str) -> tuple[str | None, str | None]:
    """(nome, moeda) do ativo, se disponível."""
    try:
        import yfinance as yf
        i = yf.Ticker(ticker).info or {}
        return i.get("longName") or i.get("shortName"), i.get("currency")
    except Exception:
        return None, None
