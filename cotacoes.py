"""Linha de comando da base de cotações.

Exemplos:
    python cotacoes.py adicionar PETR4.SA VALE3.SA ITUB4.SA --inicio 2015-01-01
    python cotacoes.py atualizar
    python cotacoes.py listar
    python cotacoes.py preco PETR4.SA --em 2020-03-16
    python cotacoes.py historico PETR4.SA VALE3.SA --inicio 2024-01-01 --fim 2024-06-30
    python cotacoes.py exportar --arquivo cotacoes.xlsx
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

from base_cotacoes import atualizar, db, fonte


def main(argv=None):
    p = argparse.ArgumentParser(description="Base de dados de cotações de ativos")
    p.add_argument("--db", default=str(db.CAMINHO_PADRAO), help="arquivo SQLite (padrão: dados/cotacoes.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("adicionar", help="cadastra ativos e baixa o histórico")
    a.add_argument("tickers", nargs="+", help="ex.: PETR4.SA AAPL BTC-USD ^BVSP")
    a.add_argument("--inicio", help="AAAA-MM-DD (padrão: todo o histórico disponível)")
    a.add_argument("--intervalo", default="1d", help="1d (padrão), 1wk, 1h, 15m, 5m, 1m")

    u = sub.add_parser("atualizar", help="baixa as cotações novas de todos os ativos")
    u.add_argument("--intervalo", default="1d")

    r = sub.add_parser("remover", help="remove ativos e suas cotações")
    r.add_argument("tickers", nargs="+")

    sub.add_parser("listar", help="mostra os ativos e o período coberto")

    pr = sub.add_parser("preco", help="preço de um ativo em um momento")
    pr.add_argument("ticker")
    pr.add_argument("--em", default=None, help="AAAA-MM-DD ou 'AAAA-MM-DD HH:MM' (padrão: último)")
    pr.add_argument("--intervalo", default="1d")

    h = sub.add_parser("historico", help="mostra a tabela de preços")
    h.add_argument("tickers", nargs="+")
    h.add_argument("--inicio")
    h.add_argument("--fim")
    h.add_argument("--intervalo", default="1d")
    h.add_argument("--campo", default="fech_ajust", choices=db.COLUNAS)

    e = sub.add_parser("exportar", help="exporta para .csv ou .xlsx")
    e.add_argument("--arquivo", default="cotacoes.xlsx")
    e.add_argument("--tickers", nargs="*")
    e.add_argument("--inicio")
    e.add_argument("--fim")
    e.add_argument("--intervalo", default="1d")

    args = p.parse_args(argv)
    con = db.conectar(args.db)
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)

    if args.cmd == "adicionar":
        for t in [t.upper() for t in args.tickers]:
            nome, moeda = fonte.info(t)
            db.registrar_ativo(con, t, nome, moeda)
            n = atualizar.atualizar_ativo(con, t, args.intervalo, inicio=args.inicio)
            print(f"{t:<12} {nome or '':<40} {n:>6} registros")
            if n == 0:
                print(f"  aviso: nenhuma cotação encontrada para {t} (ticker correto? ações B3 usam o sufixo .SA)")

    elif args.cmd == "atualizar":
        atualizar.atualizar_todos(con, args.intervalo)

    elif args.cmd == "remover":
        for t in args.tickers:
            db.remover_ativo(con, t)
        print("removido(s):", ", ".join(args.tickers))

    elif args.cmd == "listar":
        df = db.listar_ativos(con)
        print(df.to_string(index=False) if not df.empty else "Base vazia. Use: python cotacoes.py adicionar PETR4.SA")

    elif args.cmd == "preco":
        res = db.preco_em(con, args.ticker, args.em or "9999-12-31", args.intervalo)
        if res is None:
            print(f"Sem cotação de {args.ticker.upper()} até {args.em}.")
            return 1
        print(f"{args.ticker.upper()} em {res['momento']}:")
        for c in db.COLUNAS:
            print(f"  {c:<11} {res[c]}")

    elif args.cmd == "historico":
        df = db.tabela_precos(con, args.tickers, args.inicio, args.fim, args.intervalo, args.campo)
        print(df.to_string() if not df.empty else "Sem dados para o filtro.")

    elif args.cmd == "exportar":
        tickers = args.tickers or [r[0] for r in con.execute("SELECT ticker FROM ativos")]
        longo = db.historico(con, tickers, args.inicio, args.fim, args.intervalo)
        if args.arquivo.lower().endswith(".csv"):
            longo.to_csv(args.arquivo, index=False)
        else:
            with pd.ExcelWriter(args.arquivo) as w:
                longo.pivot(index="momento", columns="ticker", values="fech_ajust").to_excel(w, sheet_name="fech_ajustado")
                longo.pivot(index="momento", columns="ticker", values="fechamento").to_excel(w, sheet_name="fechamento")
                longo.to_excel(w, sheet_name="completo", index=False)
        print(f"{len(longo)} linhas exportadas para {args.arquivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
