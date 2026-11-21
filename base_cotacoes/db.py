"""Camada de banco de dados: esquema SQLite, gravação e consultas de cotações."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

CAMINHO_PADRAO = Path(os.environ.get("COTACOES_DB") or Path(__file__).resolve().parent.parent / "dados" / "cotacoes.db")

ESQUEMA = """
CREATE TABLE IF NOT EXISTS ativos (
    ticker      TEXT PRIMARY KEY,
    nome        TEXT,
    moeda       TEXT,
    adicionado  TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cotacoes (
    ticker      TEXT NOT NULL REFERENCES ativos(ticker) ON DELETE CASCADE,
    intervalo   TEXT NOT NULL DEFAULT '1d',   -- 1d, 1h, 15m, 1m ...
    momento     TEXT NOT NULL,                -- ISO 8601: 'AAAA-MM-DD' ou 'AAAA-MM-DD HH:MM:SS'
    abertura    REAL,
    maxima      REAL,
    minima      REAL,
    fechamento  REAL,
    fech_ajust  REAL,                         -- fechamento ajustado por proventos/desdobramentos
    volume      INTEGER,
    PRIMARY KEY (ticker, intervalo, momento)
);

CREATE INDEX IF NOT EXISTS idx_cotacoes_momento ON cotacoes (momento);

-- Visão prática para abrir em qualquer visualizador de SQLite
CREATE VIEW IF NOT EXISTS v_cotacoes_diarias AS
SELECT c.momento AS data, c.ticker, a.nome, c.abertura, c.maxima, c.minima,
       c.fechamento, c.fech_ajust, c.volume
FROM cotacoes c LEFT JOIN ativos a USING (ticker)
WHERE c.intervalo = '1d'
ORDER BY c.momento, c.ticker;
"""

COLUNAS = ["abertura", "maxima", "minima", "fechamento", "fech_ajust", "volume"]


def conectar(caminho: str | Path = CAMINHO_PADRAO) -> sqlite3.Connection:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    return con


# ---------------------------------------------------------------- gravação
def registrar_ativo(con, ticker: str, nome: str | None = None, moeda: str | None = None) -> None:
    con.execute(
        """INSERT INTO ativos (ticker, nome, moeda) VALUES (?, ?, ?)
           ON CONFLICT(ticker) DO UPDATE SET
             nome  = COALESCE(excluded.nome,  ativos.nome),
             moeda = COALESCE(excluded.moeda, ativos.moeda)""",
        (ticker.upper(), nome, moeda),
    )
    con.commit()


def remover_ativo(con, ticker: str) -> None:
    con.execute("DELETE FROM ativos WHERE ticker = ?", (ticker.upper(),))
    con.commit()


def gravar_cotacoes(con, ticker: str, df: pd.DataFrame, intervalo: str = "1d") -> int:
    """Grava (ou atualiza) as linhas de `df`. Índice = momento; colunas = COLUNAS."""
    if df.empty:
        return 0
    diario = intervalo.endswith(("d", "wk", "mo"))
    fmt = "%Y-%m-%d" if diario else "%Y-%m-%d %H:%M:%S"
    linhas = []
    for momento, r in df.iterrows():
        valores = [None if pd.isna(r.get(c)) else r.get(c) for c in COLUNAS]
        if valores[-1] is not None:
            valores[-1] = int(valores[-1])
        linhas.append((ticker.upper(), intervalo, pd.Timestamp(momento).strftime(fmt), *valores))
    con.executemany(
        """INSERT OR REPLACE INTO cotacoes
           (ticker, intervalo, momento, abertura, maxima, minima, fechamento, fech_ajust, volume)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        linhas,
    )
    con.commit()
    return len(linhas)


# ---------------------------------------------------------------- consultas
def listar_ativos(con) -> pd.DataFrame:
    return pd.read_sql_query(
        """SELECT a.ticker, a.nome, a.moeda, c.intervalo,
                  MIN(c.momento) AS primeiro, MAX(c.momento) AS ultimo, COUNT(c.momento) AS registros
           FROM ativos a LEFT JOIN cotacoes c USING (ticker)
           GROUP BY a.ticker, c.intervalo ORDER BY a.ticker, c.intervalo""",
        con,
    )


def ultimo_momento(con, ticker: str, intervalo: str = "1d") -> str | None:
    row = con.execute(
        "SELECT MAX(momento) FROM cotacoes WHERE ticker = ? AND intervalo = ?",
        (ticker.upper(), intervalo),
    ).fetchone()
    return row[0]


def historico(con, tickers, inicio=None, fim=None, intervalo="1d") -> pd.DataFrame:
    """Cotações em formato longo (uma linha por ticker x momento)."""
    if isinstance(tickers, str):
        tickers = [tickers]
    tickers = [t.upper() for t in tickers]
    sql = f"""SELECT ticker, momento, {', '.join(COLUNAS)} FROM cotacoes
              WHERE intervalo = ? AND ticker IN ({','.join('?' * len(tickers))})"""
    params: list = [intervalo, *tickers]
    if inicio:
        sql += " AND momento >= ?"
        params.append(str(inicio))
    if fim:
        # inclui o dia inteiro quando `fim` é apenas uma data
        sql += " AND momento <= ?"
        params.append(str(fim) + ("" if " " in str(fim) else " 23:59:59"))
    sql += " ORDER BY momento, ticker"
    df = pd.read_sql_query(sql, con, params=params)
    df["momento"] = pd.to_datetime(df["momento"])
    return df


def tabela_precos(con, tickers, inicio=None, fim=None, intervalo="1d", campo="fech_ajust") -> pd.DataFrame:
    """Tabela larga: linhas = momentos, colunas = tickers (pronta para Markowitz/risco)."""
    df = historico(con, tickers, inicio, fim, intervalo)
    return df.pivot(index="momento", columns="ticker", values=campo)


def preco_em(con, ticker: str, momento, intervalo: str = "1d") -> dict | None:
    """Última cotação disponível no momento informado ou antes dele."""
    m = str(momento)
    if " " not in m and not intervalo.endswith(("d", "wk", "mo")):
        m += " 23:59:59"
    row = con.execute(
        f"""SELECT momento, {', '.join(COLUNAS)} FROM cotacoes
            WHERE ticker = ? AND intervalo = ? AND momento <= ?
            ORDER BY momento DESC LIMIT 1""",
        (ticker.upper(), intervalo, m),
    ).fetchone()
    if row is None:
        return None
    return dict(zip(["momento", *COLUNAS], row))
