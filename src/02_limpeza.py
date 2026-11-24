"""
Limpa os arquivos brutos do ERP e carrega a base tratada em SQLite (dados/vendas.db).
Cada problema encontrado vai para saida/log_limpeza.csv com a quantidade de linhas e a ação tomada.
"""
from pathlib import Path
import sqlite3
import unicodedata
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BR, TR, SAI = RAIZ / "dados/brutos", RAIZ / "dados/tratados", RAIZ / "saida"
TR.mkdir(parents=True, exist_ok=True); SAI.mkdir(exist_ok=True)
log = []
def registra(problema, n, acao):
    log.append(dict(problema=problema, linhas=int(n), acao=acao)); print(f"{problema}: {n} -> {acao}")

v = pd.read_csv(BR / "vendas_itens.csv", sep=";", dtype={"pedido_id": int})
prod = pd.read_csv(BR / "produtos.csv")
lojas = pd.read_csv(BR / "lojas.csv")
dev = pd.read_csv(BR / "devolucoes.csv")
registra("Linhas no arquivo de vendas", len(v), "lidas")

# 1. vírgula decimal vinda do ERP
v["valor_liquido"] = v.valor_liquido.astype(str).str.replace(",", ".").astype(float)

# 2. pedidos reenviados pela integração do e-commerce (mesmo pedido, item e valores)
d = v.duplicated(keep="first")
registra("Itens duplicados (integração do e-commerce reenviou o pedido)", d.sum(), "removidos")
v = v[~d]

# 3. código de loja fora do padrão
fora = ~v.loja.isin(lojas.loja)
registra(f"Código de loja fora do padrão ({', '.join(sorted(v.loja[fora].unique()))})", fora.sum(), "corrigido para L04")
v.loc[v.loja == "L4", "loja"] = "L04"

# 4. datas impossíveis (depois do fim do período)
futura = v.data > "2026-10-31"
registra("Data no futuro (ano 2052, digitação de 2025)", futura.sum(), "corrigido para 2025")
v.loc[futura, "data"] = v.loc[futura, "data"].str.replace("2052", "2025")

# 5. quantidade negativa: estorno lançado como venda (a devolução já está na tabela de devoluções)
neg = v.quantidade <= 0
registra("Quantidade negativa (estorno lançado como venda)", neg.sum(), "removidos da tabela de vendas")
v = v[~neg]

# 6. preço zero: não é possível saber o valor real; fica fora das análises de receita e margem
zero = v.preco_unit <= 0
registra("Preço zero no item", zero.sum(), "marcado (fora das análises de receita)")
v["item_valido"] = (~zero).astype(int)

# 7. categorias escritas de jeitos diferentes
def chave(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if ch.isalnum())
OFICIAL = ["Cama, mesa e banho", "Cozinha", "Eletroportáteis", "Decoração", "Organização", "Utilidades"]
mapa = {chave(c): c for c in OFICIAL}
mapa[chave("cama mesa banho")] = "Cama, mesa e banho"
nova = prod.categoria.map(lambda c: mapa[chave(c)])
registra(f"Produtos com categoria fora do padrão ({prod.categoria.nunique()} grafias para 6 categorias)", (nova != prod.categoria).sum(), "padronizado")
prod["categoria"] = nova

# 8. custo não cadastrado: margem desses itens não é calculada
sem = prod.custo_unit.isna()
registra("Produtos sem custo cadastrado", sem.sum(), "marcado (fora do cálculo de margem)")
n_itens = v.sku.isin(prod.sku[sem]).sum()
registra("Itens vendidos desses produtos", n_itens, "receita mantida, margem não calculada")

registra("Linhas na base final de vendas", len(v), "carregadas no SQLite")

v.to_csv(TR / "vendas_itens.csv", index=False)
prod.to_csv(TR / "produtos.csv", index=False)
with sqlite3.connect(RAIZ / "dados/vendas.db") as con:
    v.to_sql("vendas", con, if_exists="replace", index=False)
    prod.to_sql("produtos", con, if_exists="replace", index=False)
    lojas.to_sql("lojas", con, if_exists="replace", index=False)
    dev.to_sql("devolucoes", con, if_exists="replace", index=False)
    pd.read_csv(BR / "metas_mensais.csv").to_sql("metas", con, if_exists="replace", index=False)
    pd.read_csv(BR / "campanhas.csv").to_sql("campanhas", con, if_exists="replace", index=False)
    con.executescript("""
        CREATE INDEX IF NOT EXISTS ix_v_sku ON vendas(sku);
        CREATE INDEX IF NOT EXISTS ix_v_data ON vendas(data);
        CREATE INDEX IF NOT EXISTS ix_d_sku ON devolucoes(sku);
    """)
pd.DataFrame(log).to_csv(SAI / "log_limpeza.csv", index=False)
