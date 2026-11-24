"""
Exporta o modelo estrela para o Power BI (saida/powerbi/): fatos de vendas e devoluções,
dimensões de produto, loja e meta. Custo, margem e desconto acima da política já vêm calculados
por item, para as medidas DAX ficarem simples. O projeto do Power BI fica em powerbi/.
"""
from pathlib import Path
import sqlite3
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
OUT = RAIZ / "saida/powerbi"; OUT.mkdir(parents=True, exist_ok=True)
con = sqlite3.connect(RAIZ / "dados/vendas.db")
q = lambda s: pd.read_sql_query(s, con)
fv = q("""
SELECT v.pedido_id, v.data, v.loja, v.sku, v.quantidade, v.preco_unit, v.desconto_pct, v.valor_liquido, v.item_valido,
       ROUND(v.quantidade * p.custo_unit, 2) AS custo,
       ROUND(v.valor_liquido - v.quantidade * p.custo_unit, 2) AS margem,
       CASE WHEN p.custo_unit IS NULL THEN 0 ELSE 1 END AS tem_custo,
       ROUND(CASE WHEN v.desconto_pct > COALESCE((SELECT MAX(c.desconto_max_pct) FROM campanhas c
              WHERE v.data BETWEEN c.inicio AND c.fim AND c.categoria IN ('Todas', p.categoria)), 15)
            THEN v.quantidade * v.preco_unit * (v.desconto_pct - 15) / 100.0 ELSE 0 END, 2) AS desconto_excedente
FROM vendas v JOIN produtos p USING (sku)""")
fv.to_csv(OUT / "fato_vendas.csv", index=False)
q("SELECT devolucao_id, pedido_id, sku, loja, data_devolucao AS data, quantidade, valor_estornado, motivo FROM devolucoes") \
    .to_csv(OUT / "fato_devolucoes.csv", index=False)
q("SELECT * FROM produtos").to_csv(OUT / "dim_produto.csv", index=False)
q("SELECT * FROM lojas").to_csv(OUT / "dim_loja.csv", index=False)
q("SELECT loja, mes, meta_receita, mes || '-01' AS data FROM metas").to_csv(OUT / "dim_meta.csv", index=False)
for f in sorted(OUT.glob("*.csv")):
    print(f"{f.name}: {sum(1 for _ in open(f, encoding='utf-8')) - 1} linhas, {f.stat().st_size/1e6:.1f} MB")
