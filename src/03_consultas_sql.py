"""Roda os blocos de sql/analises.sql no SQLite e salva cada resultado em saida/sql/<nome>.csv."""
from pathlib import Path
import re
import sqlite3
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "saida/sql"; OUT.mkdir(parents=True, exist_ok=True)
texto = (RAIZ / "sql/analises.sql").read_text(encoding="utf-8")
blocos = re.split(r"^-- nome: (\S+)\s*$", texto, flags=re.M)[1:]
with sqlite3.connect(RAIZ / "dados/vendas.db") as con:
    for nome, sql in zip(blocos[::2], blocos[1::2]):
        df = pd.read_sql_query(sql, con)
        df.to_csv(OUT / f"{nome}.csv", index=False)
        print(f"{nome}: {len(df)} linhas")
