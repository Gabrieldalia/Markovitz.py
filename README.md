# Markovitz.py

Scripts de otimização de carteira (`otimização`), métricas de risco (`Risk`) e uma
**base de dados local de cotações** (`base_cotacoes/`).

## Base de cotações

As cotações ficam em um arquivo SQLite (`dados/cotacoes.db`). Os dados vêm do Yahoo Finance.
Ações da B3 usam o sufixo `.SA` (ex.: `PETR4.SA`) e o Ibovespa é `^BVSP`.

```bash
pip install -r requirements.txt

python cotacoes.py adicionar PETR4.SA VALE3.SA ITUB4.SA BOVA11.SA --inicio 2015-01-01
python cotacoes.py atualizar                      # baixa só o que falta (rode todo dia)
python cotacoes.py listar                         # ativos e período coberto
python cotacoes.py preco PETR4.SA --em 2020-03-16 # preço naquele dia (ou no último pregão antes dele)
python cotacoes.py historico PETR4.SA VALE3.SA --inicio 2024-01-01
python cotacoes.py exportar --arquivo cotacoes.xlsx

streamlit run app.py                              # visualizador: gráfico, preço numa data, tabela
```

Também dá para guardar dados intradiários, por exemplo com `--intervalo 1h` (o Yahoo
guarda cerca de 730 dias) ou `--intervalo 5m` (cerca de 60 dias). A consulta é a
mesma: `preco PETR4.SA --em "2026-11-20 14:00" --intervalo 1h`.

### Como abrir a base

- Pelo visualizador: `streamlit run app.py`
- No [DB Browser for SQLite](https://sqlitebrowser.org/): abra `dados/cotacoes.db` e use a
  visão `v_cotacoes_diarias`
- No Excel: `python cotacoes.py exportar`
- No Python, para usar na otimização ou no risco:

```python
from base_cotacoes import db
con = db.conectar()
precos = db.tabela_precos(con, ["BBAS3.SA", "ITUB4.SA", "EQTL3.SA"], inicio="2018-01-05")
log_retornos = np.log(precos / precos.shift(1))
```

### Estrutura

| tabela      | conteúdo |
|-------------|----------|
| `ativos`    | ticker, nome, moeda |
| `cotacoes`  | ticker, intervalo, momento, abertura, maxima, minima, fechamento, fech_ajust, volume |
| `v_cotacoes_diarias` | visão com as cotações diárias e o nome do ativo |
