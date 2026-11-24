"""
Gera os dados simulados de uma rede fictícia de lojas de artigos para casa no Rio de Janeiro
(7 lojas físicas + e-commerce, jan/2024 a out/2026), no formato que costuma sair de um ERP:
vendas por item, produtos, lojas, metas, campanhas e devoluções. Os arquivos brutos trazem
problemas comuns de propósito (pedidos duplicados pela integração, códigos de loja fora do
padrão, categorias escritas de jeitos diferentes, preço zero, datas impossíveis, custo vazio).
"""
from pathlib import Path
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BR = RAIZ / "dados/brutos"; BR.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20261124)

# ---------- lojas
lojas = pd.DataFrame([
    ("L01", "Centro", "Rio de Janeiro", "Física", 1.00),
    ("L02", "Tijuca", "Rio de Janeiro", "Física", 0.90),
    ("L03", "Barra da Tijuca", "Rio de Janeiro", "Física", 1.25),
    ("L04", "Niterói", "Niterói", "Física", 1.05),
    ("L05", "Nova Iguaçu", "Nova Iguaçu", "Física", 0.80),
    ("L06", "Campo Grande", "Rio de Janeiro", "Física", 0.75),
    ("L07", "Duque de Caxias", "Duque de Caxias", "Física", 0.70),
    ("ECOM", "E-commerce", "Rio de Janeiro", "Online", 1.10),
], columns=["loja", "nome", "cidade", "canal", "peso"])

# ---------- produtos
CATS = {  # categoria: (n_skus, preço mín, preço máx, margem de tabela, fornecedores)
    "Cama, mesa e banho": (45, 39, 420, 0.52, ["Têxtil Serrana", "Fios do Vale"]),
    "Cozinha":            (50, 19, 320, 0.46, ["Inox Paulista", "Casa Forte Utilidades"]),
    "Eletroportáteis":    (40, 119, 899, 0.30, ["EletroSul", "Volt Brasil", "Quentinha Eletro"]),
    "Decoração":          (40, 29, 360, 0.56, ["Arte & Lar", "Vime Nordeste"]),
    "Organização":        (35, 15, 160, 0.50, ["Plastik Rio", "Casa Forte Utilidades"]),
    "Utilidades":         (30, 9, 120, 0.45, ["Plastik Rio", "Inox Paulista"]),
}
NOMES = {
    "Cama, mesa e banho": ["Jogo de lençol", "Toalha de banho", "Edredom", "Toalha de mesa", "Travesseiro", "Cobre-leito"],
    "Cozinha": ["Panela inox", "Jogo de facas", "Frigideira", "Assadeira", "Jogo de copos", "Aparelho de jantar"],
    "Eletroportáteis": ["Fritadeira elétrica", "Liquidificador", "Cafeteira", "Batedeira", "Sanduicheira", "Aspirador portátil"],
    "Decoração": ["Vaso decorativo", "Quadro", "Almofada", "Espelho", "Luminária", "Cesto de vime"],
    "Organização": ["Caixa organizadora", "Cabide", "Organizador de gaveta", "Prateleira", "Cesto de roupa"],
    "Utilidades": ["Pano de prato", "Escorredor", "Pote hermético", "Lixeira", "Rodo", "Balde"],
}
linhas, n = [], 1
for cat, (k, pmin, pmax, mg, forns) in CATS.items():
    for i in range(k):
        preco = round(float(np.exp(rng.uniform(np.log(pmin), np.log(pmax)))), 0) - 0.10
        base = NOMES[cat][i % len(NOMES[cat])]
        forn = forns[i % len(forns)]
        if cat == "Eletroportáteis" and base == "Fritadeira elétrica":
            forn = "Quentinha Eletro"
        custo = round(preco * (1 - mg + rng.normal(0, 0.04)), 2)
        linhas.append((f"P{n:04d}", f"{base} {chr(65 + i // len(NOMES[cat]))}{i % 7 + 1}", cat, forn, preco, custo))
        n += 1
prod = pd.DataFrame(linhas, columns=["sku", "produto", "categoria", "fornecedor", "preco_tabela", "custo_unit"])

# ---------- campanhas autorizadas (política: até 15% de desconto fora de campanha)
camp = pd.DataFrame([
    ("Dia das Mães 2024", "Cozinha", "2024-05-01", "2024-05-12", 15),
    ("Black Friday 2024", "Todas", "2024-11-25", "2024-11-30", 25),
    ("Dia das Mães 2025", "Cozinha", "2025-04-28", "2025-05-11", 15),
    ("Semana do Eletro 2025", "Eletroportáteis", "2025-11-10", "2025-11-23", 20),
    ("Black Friday 2025", "Todas", "2025-11-24", "2025-11-30", 25),
    ("Dia das Mães 2026", "Cozinha", "2026-04-27", "2026-05-10", 15),
], columns=["campanha", "categoria", "inicio", "fim", "desconto_max_pct"])

# ---------- vendas
dias = pd.date_range("2024-01-01", "2026-10-31", freq="D")
SAZ = {1: .85, 2: .80, 3: .92, 4: .95, 5: 1.15, 6: 1.0, 7: .95, 8: .97, 9: .95, 10: 1.0, 11: 1.35, 12: 1.45}
cat_lista = list(CATS)
skus_cat = {c: prod[prod.categoria == c] for c in cat_lista}
reg, pedido = [], 100000
for d in dias:
    t = (d - dias[0]).days / 365
    cresc = 1 + 0.11 * t
    fds = 1.25 if d.dayofweek >= 5 else 1.0
    bf = 2.6 if (d.month == 11 and d.day >= 24) else 1.0
    # mix: eletroportáteis ganham espaço com o tempo
    w = np.array([1.0, 1.0, 0.55 + 0.25 * t, 0.8, 0.7, 0.8]); w = w / w.sum()
    for lj in lojas.itertuples():
        n_ped = rng.poisson(9.5 * lj.peso * cresc * SAZ[d.month] * fds * bf)
        for _ in range(n_ped):
            pedido += 1
            for _ in range(1 + rng.binomial(3, 0.22)):
                cat = cat_lista[rng.choice(6, p=w)]
                p = skus_cat[cat].sample(1, random_state=int(rng.integers(1e9))).iloc[0]
                qtd = 1 + rng.binomial(2, 0.12 if cat != "Utilidades" else 0.35)
                # desconto do vendedor
                u = rng.random()
                desc = 0 if u < .68 else (rng.choice([5, 8, 10]) if u < .95 else 15)
                ds = d.strftime("%Y-%m-%d")
                for c in camp.itertuples():
                    if c.inicio <= ds <= c.fim and c.categoria in ("Todas", cat):
                        desc = max(desc, c.desconto_max_pct if rng.random() < .8 else c.desconto_max_pct - 5)
                # falha: a regra da Semana do Eletro ficou ativa nos PDVs de Barra e Niterói depois do fim
                if cat == "Eletroportáteis" and lj.loja in ("L03", "L04") and ds > "2025-11-30" and rng.random() < .88:
                    desc = 20
                reg.append((pedido, ds, lj.loja, p.sku, qtd, p.preco_tabela, desc))
vendas = pd.DataFrame(reg, columns=["pedido_id", "data", "loja", "sku", "quantidade", "preco_unit", "desconto_pct"])
vendas["valor_liquido"] = (vendas.quantidade * vendas.preco_unit * (1 - vendas.desconto_pct / 100)).round(2)

# ---------- devoluções (2% normal; fritadeiras da Quentinha Eletro com defeito a partir de mar/2026)
frit = set(prod[(prod.fornecedor == "Quentinha Eletro") & prod.produto.str.startswith("Fritadeira")].sku)
pr = np.where(vendas.sku.isin(frit) & (vendas.data >= "2026-03-01"), 0.17, 0.02)
pr = np.where(vendas.loja == "ECOM", pr * 1.4, pr)
dev = vendas[rng.random(len(vendas)) < pr].copy()
def motivo(r):
    if r.sku in frit and r.data >= "2026-03-01":
        return "Defeito" if rng.random() < .85 else "Arrependimento"
    return rng.choice(["Arrependimento", "Defeito", "Avaria no transporte", "Produto errado"], p=[.55, .2, .15, .1])
dev["motivo"] = [motivo(r) for r in dev.itertuples()]
dev["data_devolucao"] = (pd.to_datetime(dev.data) + pd.to_timedelta(rng.integers(2, 25, len(dev)), "D")).dt.strftime("%Y-%m-%d")
dev = dev[dev.data_devolucao <= "2026-10-31"]
dev = dev.assign(devolucao_id=[f"D{i:06d}" for i in range(1, len(dev) + 1)])[
    ["devolucao_id", "pedido_id", "sku", "loja", "data_devolucao", "quantidade", "valor_liquido", "motivo"]
].rename(columns={"valor_liquido": "valor_estornado"})

# ---------- metas mensais por loja (plano feito no início de cada ano, com 8% de crescimento)
vendas["mes"] = vendas.data.str[:7]
real = vendas.groupby(["loja", "mes"]).valor_liquido.sum().reset_index()
metas = real.copy()
metas["meta_receita"] = (metas.valor_liquido * rng.normal(1.04, 0.03, len(metas)) / 100).round() * 100
metas = metas[["loja", "mes", "meta_receita"]]
vendas = vendas.drop(columns="mes")

# ---------- sujeira de propósito
sujo = vendas.copy()
ecom = sujo[sujo.loja == "ECOM"]
dup = ecom[ecom.pedido_id.isin(rng.choice(ecom.pedido_id.unique(), 300, replace=False))]
sujo = pd.concat([sujo, dup])                                                        # integração reenviou pedidos
i = rng.choice(sujo.index[sujo.loja == "L04"], 140, replace=False); sujo.loc[i, "loja"] = "L4"   # código fora do padrão
i = rng.choice(sujo.index, 41, replace=False); sujo.loc[i, ["preco_unit", "valor_liquido"]] = 0.0  # preço zero
i = rng.choice(sujo.index, 9, replace=False); sujo.loc[i, "data"] = sujo.loc[i, "data"].str.replace("2025", "2052")  # ano digitado errado
i = rng.choice(sujo.index, 23, replace=False); sujo.loc[i, "quantidade"] *= -1      # estorno lançado como venda
sujo["valor_liquido"] = sujo.valor_liquido.map(lambda v: f"{v:.2f}".replace(".", ","))  # vírgula decimal do ERP
sujo = sujo.sample(frac=1, random_state=7).reset_index(drop=True)

prod_sujo = prod.copy()
var = {"Cama, mesa e banho": ["CAMA MESA E BANHO ", "cama mesa banho"], "Eletroportáteis": ["Eletroportateis", "ELETROPORTÁTEIS"],
       "Decoração": ["Decoracao"]}
for cat, vs in var.items():
    idx = prod_sujo.index[prod_sujo.categoria == cat]
    for k, j in enumerate(rng.choice(idx, 3 * len(vs), replace=False)):
        prod_sujo.loc[j, "categoria"] = vs[k % len(vs)]
prod_sujo.loc[rng.choice(prod_sujo.index, 6, replace=False), "custo_unit"] = np.nan  # custo não cadastrado

sujo.to_csv(BR / "vendas_itens.csv", index=False, sep=";")
prod_sujo.to_csv(BR / "produtos.csv", index=False)
lojas.drop(columns="peso").to_csv(BR / "lojas.csv", index=False)
camp.to_csv(BR / "campanhas.csv", index=False)
dev.to_csv(BR / "devolucoes.csv", index=False)
metas.to_csv(BR / "metas_mensais.csv", index=False)
for f in sorted(BR.glob("*.csv")):
    print(f"{f.name}: {sum(1 for _ in open(f, encoding='utf-8')) - 1} linhas, {f.stat().st_size/1e6:.1f} MB")
