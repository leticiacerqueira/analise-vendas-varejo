"""
Gera o painel interativo de vendas e margem (HTML único, sem dependências): painel/index.html.
Os dados vêm da base tratada em SQLite, agregados por mês, loja, categoria e fornecedor.
"""
from pathlib import Path
import json
import sqlite3
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
con = sqlite3.connect(RAIZ / "dados/vendas.db")
q = lambda s: pd.read_sql_query(s, con)

LIMITE = """(SELECT MAX(c.desconto_max_pct) FROM campanhas c
             WHERE v.data BETWEEN c.inicio AND c.fim AND c.categoria IN ('Todas', p.categoria))"""
agg = q(f"""
SELECT substr(v.data,1,7) mes, v.loja, p.categoria cat,
       SUM(v.valor_liquido) receita,
       SUM(CASE WHEN p.custo_unit IS NOT NULL THEN v.valor_liquido END) receita_c,
       SUM(CASE WHEN p.custo_unit IS NOT NULL THEN v.valor_liquido - v.quantidade*p.custo_unit END) margem,
       SUM(v.quantidade*v.preco_unit) bruto,
       SUM(CASE WHEN v.desconto_pct > COALESCE({LIMITE},15) THEN v.quantidade*v.preco_unit*(v.desconto_pct-15)/100.0 ELSE 0 END) desc_exc
FROM vendas v JOIN produtos p USING (sku) WHERE v.item_valido=1 GROUP BY 1,2,3""").fillna(0)
ped = q("SELECT substr(data,1,7) mes, loja, COUNT(DISTINCT pedido_id) pedidos FROM vendas WHERE item_valido=1 GROUP BY 1,2")
un = q("""SELECT substr(v.data,1,7) mes, v.loja, p.fornecedor forn, SUM(v.quantidade) un
          FROM vendas v JOIN produtos p USING (sku) WHERE v.item_valido=1 GROUP BY 1,2,3""")
dev = q("""SELECT substr(d.data_devolucao,1,7) mes, d.loja, p.fornecedor forn, SUM(d.quantidade) un,
                  SUM(CASE WHEN d.motivo='Defeito' THEN d.quantidade ELSE 0 END) defeito, SUM(d.valor_estornado) estorno
           FROM devolucoes d JOIN produtos p USING (sku) GROUP BY 1,2,3""")
lojas = q("SELECT loja, nome FROM lojas")
meses = sorted(agg.mes.unique()); L = list(lojas.loja); C = sorted(agg.cat.unique())
F = sorted(set(un.forn))
r2 = lambda x: round(float(x), 2)
dados = {
    "meses": meses, "lojas": [[a, b] for a, b in zip(lojas.loja, lojas.nome)], "cats": C, "forns": F,
    # [mes, loja, cat, receita, receita_c, margem, bruto, desc_exc]
    "agg": [[meses.index(r.mes), L.index(r.loja), C.index(r.cat), r2(r.receita), r2(r.receita_c), r2(r.margem), r2(r.bruto), r2(r.desc_exc)]
            for r in agg.itertuples()],
    "ped": [[meses.index(r.mes), L.index(r.loja), int(r.pedidos)] for r in ped.itertuples()],
    # [mes, loja, forn, un_vendidas, un_devolvidas, un_defeito, estorno]
    "forn": [],
}
m = un.merge(dev, on=["mes", "loja", "forn"], how="outer", suffixes=("_v", "_d")).fillna(0)
m = m[m.mes.isin(meses)]
dados["forn"] = [[meses.index(r.mes), L.index(r.loja), F.index(r.forn), int(r.un_v), int(r.un_d), int(r.defeito), r2(r.estorno)]
                 for r in m.itertuples()]
js = json.dumps(dados, ensure_ascii=False, separators=(",", ":"))
tpl = (RAIZ / "src/painel_template.html").read_text(encoding="utf-8")
corpo = tpl.replace("/*__DADOS__*/null", js)
(RAIZ / "painel").mkdir(exist_ok=True)
pagina = ('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
          '<meta name="viewport" content="width=device-width, initial-scale=1">\n</head>\n<body>\n'
          + corpo + "\n</body>\n</html>\n")
(RAIZ / "painel/index.html").write_text(pagina, encoding="utf-8")
print(f"painel/index.html: {len(pagina)/1024:.0f} KB")
