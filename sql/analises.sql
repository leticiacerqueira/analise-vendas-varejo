-- Perguntas de negócio em SQL (SQLite). Cada bloco começa com "-- nome:" e vira um CSV em saida/sql/.
-- Base: só itens válidos (preço maior que zero). Margem bruta = valor líquido - custo, só para produtos com custo.

-- nome: 01_receita_margem_mensal
-- Receita, margem bruta e variação contra o mesmo mês do ano anterior (LAG de 12 meses)
WITH base AS (
  SELECT substr(v.data, 1, 7) AS mes,
         SUM(v.valor_liquido) AS receita,
         SUM(CASE WHEN p.custo_unit IS NOT NULL THEN v.valor_liquido - v.quantidade * p.custo_unit END) AS margem,
         SUM(CASE WHEN p.custo_unit IS NOT NULL THEN v.valor_liquido END) AS receita_com_custo,
         COUNT(DISTINCT v.pedido_id) AS pedidos
  FROM vendas v JOIN produtos p USING (sku)
  WHERE v.item_valido = 1
  GROUP BY 1
)
SELECT mes,
       ROUND(receita, 2) AS receita,
       ROUND(margem / receita_com_custo, 4) AS margem_pct,
       ROUND(receita / pedidos, 2) AS ticket_medio,
       ROUND(receita / LAG(receita, 12) OVER (ORDER BY mes) - 1, 4) AS var_receita_12m,
       ROUND(margem / receita_com_custo - LAG(margem / receita_com_custo, 12) OVER (ORDER BY mes), 4) AS var_margem_pp_12m
FROM base ORDER BY mes;

-- nome: 02_margem_por_loja
-- Margem por loja em 2025 x 2026 (jan-out nos dois anos, para comparar períodos iguais)
SELECT l.loja, l.nome,
       ROUND(SUM(CASE WHEN v.data BETWEEN '2025-01-01' AND '2025-10-31' THEN v.valor_liquido - v.quantidade * p.custo_unit END)
           / SUM(CASE WHEN v.data BETWEEN '2025-01-01' AND '2025-10-31' THEN v.valor_liquido END), 4) AS margem_2025,
       ROUND(SUM(CASE WHEN v.data >= '2026-01-01' THEN v.valor_liquido - v.quantidade * p.custo_unit END)
           / SUM(CASE WHEN v.data >= '2026-01-01' THEN v.valor_liquido END), 4) AS margem_2026,
       ROUND(SUM(CASE WHEN v.data >= '2026-01-01' THEN v.valor_liquido END), 2) AS receita_2026
FROM vendas v JOIN produtos p USING (sku) JOIN lojas l USING (loja)
WHERE v.item_valido = 1 AND p.custo_unit IS NOT NULL
GROUP BY l.loja, l.nome
ORDER BY margem_2026;

-- nome: 03_desconto_fora_politica
-- Desconto acima de 15% sem campanha autorizada na data e na categoria (LEFT JOIN com intervalo de datas)
WITH itens AS (
  SELECT v.*, p.categoria,
         (SELECT MAX(c.desconto_max_pct) FROM campanhas c
           WHERE v.data BETWEEN c.inicio AND c.fim AND c.categoria IN ('Todas', p.categoria)) AS limite_campanha
  FROM vendas v JOIN produtos p USING (sku)
  WHERE v.item_valido = 1
)
SELECT loja, categoria, substr(data, 1, 7) AS mes,
       COUNT(*) AS itens_fora,
       ROUND(SUM(quantidade * preco_unit * (desconto_pct - 15) / 100.0), 2) AS desconto_excedente
FROM itens
WHERE desconto_pct > COALESCE(limite_campanha, 15)
GROUP BY 1, 2, 3
ORDER BY desconto_excedente DESC;

-- nome: 04_desconto_excedente_por_loja
-- Resumo do bloco anterior por loja e ano: quanto de desconto passou do limite
WITH itens AS (
  SELECT v.*, p.categoria,
         (SELECT MAX(c.desconto_max_pct) FROM campanhas c
           WHERE v.data BETWEEN c.inicio AND c.fim AND c.categoria IN ('Todas', p.categoria)) AS limite_campanha
  FROM vendas v JOIN produtos p USING (sku)
  WHERE v.item_valido = 1
)
SELECT loja, substr(data, 1, 4) AS ano,
       SUM(desconto_pct > COALESCE(limite_campanha, 15)) AS itens_fora,
       ROUND(SUM(CASE WHEN desconto_pct > COALESCE(limite_campanha, 15)
                      THEN quantidade * preco_unit * (desconto_pct - 15) / 100.0 ELSE 0 END), 2) AS desconto_excedente,
       ROUND(1.0 * SUM(desconto_pct > COALESCE(limite_campanha, 15)) / COUNT(*), 4) AS pct_itens_fora
FROM itens GROUP BY 1, 2 ORDER BY ano, desconto_excedente DESC;

-- nome: 05_devolucao_por_fornecedor
-- Taxa de devolução por fornecedor e trimestre, e quanto disso é defeito
WITH vend AS (
  SELECT p.fornecedor, substr(v.data, 1, 4) || '-T' || ((CAST(substr(v.data, 6, 2) AS INT) + 2) / 3) AS tri,
         SUM(v.quantidade) AS un_vendidas
  FROM vendas v JOIN produtos p USING (sku) WHERE v.item_valido = 1 GROUP BY 1, 2
), dev AS (
  SELECT p.fornecedor, substr(d.data_devolucao, 1, 4) || '-T' || ((CAST(substr(d.data_devolucao, 6, 2) AS INT) + 2) / 3) AS tri,
         SUM(d.quantidade) AS un_devolvidas,
         SUM(CASE WHEN d.motivo = 'Defeito' THEN d.quantidade ELSE 0 END) AS un_defeito,
         SUM(d.valor_estornado) AS valor_estornado
  FROM devolucoes d JOIN produtos p USING (sku) GROUP BY 1, 2
)
SELECT vend.fornecedor, vend.tri, un_vendidas,
       COALESCE(un_devolvidas, 0) AS un_devolvidas,
       ROUND(1.0 * COALESCE(un_devolvidas, 0) / un_vendidas, 4) AS taxa_devolucao,
       ROUND(1.0 * COALESCE(un_defeito, 0) / un_vendidas, 4) AS taxa_defeito,
       ROUND(COALESCE(valor_estornado, 0), 2) AS valor_estornado
FROM vend LEFT JOIN dev USING (fornecedor, tri)
ORDER BY vend.fornecedor, vend.tri;

-- nome: 06_curva_abc_margem
-- Curva ABC de produtos pela margem bruta de 2026 (soma acumulada com window function)
WITH m AS (
  SELECT p.sku, p.produto, p.categoria,
         SUM(v.valor_liquido - v.quantidade * p.custo_unit) AS margem
  FROM vendas v JOIN produtos p USING (sku)
  WHERE v.item_valido = 1 AND p.custo_unit IS NOT NULL AND v.data >= '2026-01-01'
  GROUP BY 1, 2, 3
), acum AS (
  SELECT *, SUM(margem) OVER (ORDER BY margem DESC ROWS UNBOUNDED PRECEDING) / SUM(margem) OVER () AS pct_acum,
         ROW_NUMBER() OVER (ORDER BY margem DESC) AS posicao, COUNT(*) OVER () AS total
  FROM m
)
SELECT posicao, sku, produto, categoria, ROUND(margem, 2) AS margem, ROUND(pct_acum, 4) AS pct_acumulado,
       CASE WHEN pct_acum <= 0.8 THEN 'A' WHEN pct_acum <= 0.95 THEN 'B' ELSE 'C' END AS classe
FROM acum ORDER BY posicao;

-- nome: 07_meta_por_loja_2026
-- Realizado x meta por loja em 2026 e ranking de atingimento
WITH r AS (
  SELECT loja, SUM(valor_liquido) AS realizado FROM vendas
  WHERE item_valido = 1 AND data >= '2026-01-01' GROUP BY loja
), m AS (
  SELECT loja, SUM(meta_receita) AS meta FROM metas WHERE mes >= '2026-01' GROUP BY loja
)
SELECT RANK() OVER (ORDER BY realizado / meta DESC) AS posicao, l.loja, l.nome,
       ROUND(realizado, 2) AS realizado, ROUND(meta, 2) AS meta, ROUND(realizado / meta, 4) AS atingimento
FROM r JOIN m USING (loja) JOIN lojas l USING (loja)
ORDER BY posicao;

-- nome: 08_ponte_margem_2025_2026
-- O que explica a queda de margem: mix de categorias x margem dentro de cada categoria (jan-out)
WITH c AS (
  SELECT p.categoria, substr(v.data, 1, 4) AS ano,
         SUM(v.valor_liquido) AS receita,
         SUM(v.valor_liquido - v.quantidade * p.custo_unit) AS margem
  FROM vendas v JOIN produtos p USING (sku)
  WHERE v.item_valido = 1 AND p.custo_unit IS NOT NULL AND substr(v.data, 6, 2) <= '10' AND v.data >= '2025-01-01'
  GROUP BY 1, 2
), t AS (SELECT ano, SUM(receita) AS tot FROM c GROUP BY ano)
SELECT c.categoria,
       ROUND(MAX(CASE WHEN c.ano = '2025' THEN receita / tot END), 4) AS part_2025,
       ROUND(MAX(CASE WHEN c.ano = '2026' THEN receita / tot END), 4) AS part_2026,
       ROUND(MAX(CASE WHEN c.ano = '2025' THEN margem / receita END), 4) AS margem_2025,
       ROUND(MAX(CASE WHEN c.ano = '2026' THEN margem / receita END), 4) AS margem_2026
FROM c JOIN t USING (ano) GROUP BY c.categoria ORDER BY part_2026 DESC;
