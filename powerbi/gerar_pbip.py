"""
Gera o projeto do Power BI (formato PBIP: modelo em TMDL + relatório) em powerbi/Painel Vendas/.
Os dados vêm direto dos CSVs públicos do repositório no GitHub (saida/powerbi/), então o arquivo
abre em qualquer computador sem ajustar caminho de pasta.
Abrir no Power BI Desktop: Arquivo > Abrir > "Painel Vendas.pbip" e depois Atualizar.
"""
from pathlib import Path
import json, re, shutil, uuid

AQUI = Path(__file__).resolve().parent
NOME = "Painel Vendas"
RAIZ = AQUI / NOME
URL = "https://raw.githubusercontent.com/leticiacerqueira/analise-vendas-varejo/main/saida/powerbi/"
ESCURO, LARANJA, MARROM, BEGE, FUNDO = "#2B1D14", "#C2560F", "#7A4A2A", "#C9A98F", "#F7F2EC"

def gid(*k):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "painel-vendas/" + "/".join(k)))

def q(n):  # nome TMDL: aspas simples quando tem espaço ou símbolo
    return n if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n) else "'" + n.replace("'", "''") + "'"


# ------------------------------------------------------------------ tabelas
T, D, I, S = "double", "dateTime", "int64", "string"
TABELAS = {
    "fato_vendas": [("pedido_id", I), ("data", D), ("loja", S), ("sku", S), ("quantidade", I), ("preco_unit", T), ("desconto_pct", T),
                    ("valor_liquido", T), ("item_valido", I), ("custo", T), ("margem", T), ("tem_custo", I), ("desconto_excedente", T)],
    "fato_devolucoes": [("devolucao_id", S), ("pedido_id", I), ("sku", S), ("loja", S), ("data", D), ("quantidade", I),
                        ("valor_estornado", T), ("motivo", S)],
    "dim_produto": [("sku", S), ("produto", S), ("categoria", S), ("fornecedor", S), ("preco_tabela", T), ("custo_unit", T)],
    "dim_loja": [("loja", S), ("nome", S), ("cidade", S), ("canal", S)],
    "dim_meta": [("loja", S), ("mes", S), ("meta_receita", T), ("data", D)],
}
MTIPO = {T: "type number", D: "type date", I: "Int64.Type", S: "type text"}

MEDIDAS = {
    "fato_vendas": [
        ("Receita", "CALCULATE ( SUM ( fato_vendas[valor_liquido] ), fato_vendas[item_valido] = 1 )", "\\R\\$ #,0"),
        ("Receita com Custo", "CALCULATE ( [Receita], fato_vendas[tem_custo] = 1 )", "\\R\\$ #,0"),
        ("Margem Bruta", "CALCULATE ( SUM ( fato_vendas[margem] ), fato_vendas[item_valido] = 1, fato_vendas[tem_custo] = 1 )", "\\R\\$ #,0"),
        ("Margem %", "DIVIDE ( [Margem Bruta], [Receita com Custo] )", "0.0%"),
        ("Margem % Ano Anterior", "CALCULATE ( [Margem %], SAMEPERIODLASTYEAR ( dCalendario[Data] ) )", "0.0%"),
        ("Variação da Margem (p.p.)", "IF ( NOT ISBLANK ( [Margem % Ano Anterior] ), ( [Margem %] - [Margem % Ano Anterior] ) * 100 )", "+0.0;-0.0"),
        ("Receita Ano Anterior", "CALCULATE ( [Receita], SAMEPERIODLASTYEAR ( dCalendario[Data] ) )", "\\R\\$ #,0"),
        ("Variação da Receita %", "DIVIDE ( [Receita] - [Receita Ano Anterior], [Receita Ano Anterior] )", "+0.0%;-0.0%"),
        ("Pedidos", "CALCULATE ( DISTINCTCOUNT ( fato_vendas[pedido_id] ), fato_vendas[item_valido] = 1 )", "#,0"),
        ("Ticket Médio", "DIVIDE ( [Receita], [Pedidos] )", "\\R\\$ #,0"),
        ("Desconto Acima da Política", "SUM ( fato_vendas[desconto_excedente] )", "\\R\\$ #,0"),
        ("Unidades Vendidas", "CALCULATE ( SUM ( fato_vendas[quantidade] ), fato_vendas[item_valido] = 1 )", "#,0"),
        ("Meta", "SUM ( dim_meta[meta_receita] )", "\\R\\$ #,0"),
        ("% da Meta", "DIVIDE ( [Receita], [Meta] )", "0.0%"),
    ],
    "fato_devolucoes": [
        ("Unidades Devolvidas", "SUM ( fato_devolucoes[quantidade] )", "#,0"),
        ("Taxa de Devolução %", "DIVIDE ( [Unidades Devolvidas], [Unidades Vendidas] )", "0.0%"),
        ("Valor Estornado", "SUM ( fato_devolucoes[valor_estornado] )", "\\R\\$ #,0"),
        ("Devoluções por Defeito", """CALCULATE ( [Unidades Devolvidas], fato_devolucoes[motivo] = "Defeito" )""", "#,0"),
    ],
}

def tab_m(nome, cols):
    tipos = ", ".join(f'{{"{c}", {MTIPO[t]}}}' for c, t in cols)
    return f'''let
    Fonte = Csv.Document(Web.Contents("{URL}{nome}.csv"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Cabecalhos = Table.PromoteHeaders(Fonte, [PromoteAllScalars = true]),
    Tipos = Table.TransformColumnTypes(Cabecalhos, {{{tipos}}}, "en-US")
in
    Tipos'''

def bloco(texto, nivel):
    pad = "\t" * nivel
    return "\n".join(pad + l if l.strip() else "" for l in texto.splitlines())

def tmdl_tabela(nome, cols, medidas, m, extra_cols=""):
    out = [f"table {q(nome)}", f"\tlineageTag: {gid(nome)}", ""]
    for c, t in cols:
        out += [f"\tcolumn {q(c)}", f"\t\tdataType: {t}"]
        if t == D: out.append("\t\tformatString: dd/mm/yyyy")
        if t in (T, I): out.append("\t\tsummarizeBy: none" if c in ("item_valido", "tem_custo", "pedido_id", "desconto_pct", "preco_unit", "preco_tabela", "custo_unit") else "\t\tsummarizeBy: sum")
        else: out.append("\t\tsummarizeBy: none")
        out += [f"\t\tlineageTag: {gid(nome, c)}", f"\t\tsourceColumn: {c}", ""]
    out.append(extra_cols)
    for n, expr, fmt in medidas:
        if "\n" in expr:
            out.append(f"\tmeasure {q(n)} =")
            out.append(bloco(expr, 3))
        else:
            out.append(f"\tmeasure {q(n)} = {expr}")
        if fmt: out.append(f"\t\tformatString: {fmt}")
        out += [f"\t\tlineageTag: {gid(nome, 'm', n)}", ""]
    out += [f"\tpartition {q(nome)} = m", "\t\tmode: import", "\t\tsource =", bloco(m, 4), ""]
    return "\n".join(out) + "\n"


CAL_COLS = [("Data", D), ("Ano", I), ("Mes Num", I), ("Mes", S), ("Ano-Mes", S)]
CAL_M = '''let
    Datas = List.Dates(#date(2024, 1, 1), Duration.Days(#date(2026, 10, 31) - #date(2024, 1, 1)) + 1, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(Datas, Splitter.SplitByNothing(), {"Data"}),
    Ano = Table.AddColumn(Tabela, "Ano", each Date.Year([Data]), Int64.Type),
    MesNum = Table.AddColumn(Ano, "Mes Num", each Date.Month([Data]), Int64.Type),
    Mes = Table.AddColumn(MesNum, "Mes", each {"jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"}{Date.Month([Data]) - 1} & "/" & Text.End(Text.From(Date.Year([Data])), 2), type text),
    AnoMes = Table.AddColumn(Mes, "Ano-Mes", each Date.ToText([Data], "yyyy-MM"), type text),
    Tipos = Table.TransformColumnTypes(AnoMes, {{"Data", type date}})
in
    Tipos'''

def gerar_modelo():
    sm = RAIZ / f"{NOME}.SemanticModel"
    d = sm / "definition"; (d / "tables").mkdir(parents=True)
    (sm / "definition.pbism").write_text(json.dumps({"version": "4.0", "settings": {}}, indent=2), encoding="utf-8")
    (d / "database.tmdl").write_text("database\n\tcompatibilityLevel: 1567\n", encoding="utf-8")
    nomes = list(TABELAS) + ["dCalendario"]
    model = ["model Model", "\tculture: pt-BR", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tsourceQueryCulture: pt-BR", "\tdataAccessOptions", "\t\tlegacyRedirects", "\t\treturnErrorValuesAsNull", ""]
    model += [f"ref table {q(n)}" for n in nomes] + ["", "ref cultureInfo pt-BR", ""]
    (d / "model.tmdl").write_text("\n".join(model), encoding="utf-8")
    (d / "cultures").mkdir()
    (d / "cultures" / "pt-BR.tmdl").write_text("cultureInfo pt-BR\n", encoding="utf-8")
    for n, cols in TABELAS.items():
        (d / "tables" / f"{n}.tmdl").write_text(tmdl_tabela(n, cols, MEDIDAS.get(n, []), tab_m(n, cols)), encoding="utf-8")
    cal = tmdl_tabela("dCalendario", CAL_COLS, [], CAL_M)
    cal = cal.replace("\tlineageTag: " + gid("dCalendario") + "\n", "\tlineageTag: " + gid("dCalendario") + "\n\tdataCategory: Time\n", 1)
    cal = cal.replace("\tcolumn Data\n", "\tcolumn Data\n\t\tisKey\n", 1)
    cal = cal.replace(f"\t\tsourceColumn: Mes\n", "\t\tsourceColumn: Mes\n\t\tsortByColumn: 'Ano-Mes'\n", 1)
    (d / "tables" / "dCalendario.tmdl").write_text(cal, encoding="utf-8")
    rel = [("fato_vendas", "data", "dCalendario", "Data"), ("fato_devolucoes", "data", "dCalendario", "Data"),
           ("dim_meta", "data", "dCalendario", "Data"), ("fato_vendas", "sku", "dim_produto", "sku"),
           ("fato_devolucoes", "sku", "dim_produto", "sku"), ("fato_vendas", "loja", "dim_loja", "loja"),
           ("fato_devolucoes", "loja", "dim_loja", "loja"), ("dim_meta", "loja", "dim_loja", "loja")]
    out = []
    for a, ca, b, cb in rel:
        out += [f"relationship {gid('rel', a, ca, b)}", f"\tfromColumn: {q(a)}.{q(ca)}", f"\ttoColumn: {q(b)}.{q(cb)}", ""]
    (d / "relationships.tmdl").write_text("\n".join(out), encoding="utf-8")

# ------------------------------------------------------------------ relatório (report.json)
def lit(v):
    return {"expr": {"Literal": {"Value": v}}}

def cor(c):
    return {"solid": {"color": lit(f"'{c}'")}}

def visual(nome, tipo, x, y, w, h, campos=None, objetos=None, vc_objetos=None, titulo=None, z=1000, ordenar=None, excluir=None):
    """campos: {projeção: [(tabela, campo, 'm'|'c')]}"""
    sv = {"visualType": tipo, "drillFilterOtherVisuals": True}
    if campos:
        apelidos, frm, sel, proj = {}, [], [], {}
        for papel, lst in campos.items():
            proj[papel] = []
            for t, c, k in lst:
                if t not in apelidos:
                    apelidos[t] = f"t{len(apelidos)}"
                    frm.append({"Name": apelidos[t], "Entity": t, "Type": 0})
                ref = f"{t}.{c}"
                expr = {"Expression": {"SourceRef": {"Source": apelidos[t]}}, "Property": c}
                if k == "a":   # coluna agregada (soma), exigida em eixos numéricos do gráfico de dispersão
                    ref = f"Sum({t}.{c})"
                    item = {"Aggregation": {"Expression": {"Column": expr}, "Function": 0}}
                else:
                    item = {"Measure": expr} if k == "m" else {"Column": expr}
                if ref not in [s["Name"] for s in sel]:
                    sel.append({**item, "Name": ref, **({"NativeReferenceName": c} if k == "m" else {})})
                proj[papel].append({"queryRef": ref, **({"active": True} if papel == "Category" else {})})
        sv["projections"] = proj
        sv["prototypeQuery"] = {"Version": 2, "From": frm, "Select": sel}
        if ordenar:   # (tabela, medida): ordena do maior para o menor
            t, c = ordenar
            sv["prototypeQuery"]["OrderBy"] = [{"Direction": 2, "Expression": {"Measure": {"Expression": {"SourceRef": {"Source": apelidos[t]}}, "Property": c}}}]
    objetos = dict(objetos or {})
    if tipo in ("lineChart", "clusteredColumnChart", "barChart", "clusteredBarChart", "scatterChart"):
        for eixo in ("categoryAxis", "valueAxis"):   # títulos dos eixos repetem o título do gráfico
            props = objetos.get(eixo, [{"properties": {}}])[0]["properties"]
            props["showAxisTitle"] = lit("false")
            objetos[eixo] = [{"properties": props}]
    if objetos: sv["objects"] = objetos
    vco = dict(vc_objetos or {})
    if titulo:
        vco["title"] = [{"properties": {"show": lit("true"), "text": lit(f"'{titulo}'"),
                                        "fontColor": cor(ESCURO), "fontSize": lit("11D"), "bold": lit("true")}}]
    if tipo in ("textbox", "basicShape"):
        vco["background"] = [{"properties": {"show": lit("false")}}]
        vco["border"] = [{"properties": {"show": lit("false")}}]
    else:
        vco.setdefault("background", [{"properties": {"show": lit("true"), "color": cor("#FFFFFF"), "transparency": lit("0D")}}])
        vco.setdefault("border", [{"properties": {"show": lit("true"), "color": cor("#E6DACE"), "radius": lit("6D")}}])
    if vco: sv["vcObjects"] = vco
    cfg = {"name": nome, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h}}], "singleVisual": sv}
    filtros = []
    if excluir:   # (tabela, coluna, [valores]) filtro do visual: NOT IN
        t, c, vals = excluir
        filtros.append({"name": f"{nome}_f", "type": "Categorical", "howCreated": 1,
                        "expression": {"Column": {"Expression": {"SourceRef": {"Entity": t}}, "Property": c}},
                        "filter": {"Version": 2, "From": [{"Name": "f", "Entity": t, "Type": 0}],
                                   "Where": [{"Condition": {"Not": {"Expression": {"In": {
                                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "f"}}, "Property": c}}],
                                       "Values": [[{"Literal": {"Value": f"'{v}'"}}] for v in vals]}}}}}]}})
    return {"x": x, "y": y, "z": z, "width": w, "height": h, "config": json.dumps(cfg, ensure_ascii=False),
            "filters": json.dumps(filtros, ensure_ascii=False)}

def texto(nome, x, y, w, h, linhas, z=2000):
    paras = [{"textRuns": [{"value": t, "textStyle": {"fontWeight": "bold" if b else "normal", "fontSize": f"{s}pt", "color": c,
                                                      "fontFamily": "Segoe UI" + (" Semibold" if b else "")}}]} for t, s, c, b in linhas]
    return visual(nome, "textbox", x, y, w, h, objetos={"general": [{"properties": {"paragraphs": paras}}]}, z=z)

def forma(nome, x, y, w, h, c, z=0):
    return visual(nome, "basicShape", x, y, w, h, z=z, objetos={
        "shape": [{"properties": {"tileShape": lit("'rectangle'")}}],
        "fill": [{"properties": {"show": lit("true"), "fillColor": cor(c), "transparency": lit("0D")}}],
        "outline": [{"properties": {"show": lit("false")}}]})


def card(nome, x, y, w, rotulo, t, med):
    return visual(nome, "card", x, y, w, 92, {"Values": [(t, med, "m")]}, objetos={
        "labels": [{"properties": {"color": cor(ESCURO), "fontSize": lit("22D"), "labelDisplayUnits": lit("1D")}}],
        "categoryLabels": [{"properties": {"show": lit("false")}}]}, titulo=rotulo)

def moldura(pagina, titulo, sub):
    """barra lateral marrom + cabeçalho + filtros, igual em todas as páginas"""
    ps = ["Visão Geral", "Margem e Descontos", "Devoluções"]
    v = [forma(f"{pagina}_lado", 0, 0, 200, 720, ESCURO),
         texto(f"{pagina}_marca", 14, 18, 180, 96, [("Vendas e Margem", 14, "#FFFFFF", True), ("Rede de lojas · 2024–2026", 9, "#D9B48A", False)])]
    for i, p in enumerate(ps):
        ativo = p == titulo
        v.append(forma(f"{pagina}_bt{i}", 16, 130 + i * 48, 168, 36, LARANJA if ativo else "#4A2E1E", z=10 + i))
        v.append(texto(f"{pagina}_btt{i}", 22, 134 + i * 48, 156, 30, [(p, 10, "#FFFFFF", ativo)], z=3000 + i))
    v.append(texto(f"{pagina}_rodape", 14, 640, 176, 60, [("Dados simulados · Leticia Cerqueira", 8, "#D9B48A", False)]))
    v.append(texto(f"{pagina}_tit", 216, 6, 600, 66, [(titulo.upper(), 18, ESCURO, True), (sub, 9, "#6E5A4B", False)]))
    v.append(visual(f"{pagina}_fs", "slicer", 840, 4, 200, 70, {"Values": [("dim_loja", "nome", "c")]},
                    objetos={"data": [{"properties": {"mode": lit("'Dropdown'")}}], "header": [{"properties": {"show": lit("false")}}]}, titulo="Loja"))
    v.append(visual(f"{pagina}_fp", "slicer", 1050, 4, 216, 70, {"Values": [("dCalendario", "Data", "c")]},
                    objetos={"data": [{"properties": {"mode": lit("'Between'")}}], "header": [{"properties": {"show": lit("false")}}]}, titulo="Período"))
    return v

def paginas():
    L, R = 214, 1266
    F = "fato_vendas"
    p1 = moldura("p1", "Visão Geral", "Receita cresce, margem cai: onde está o vazamento?")
    kp = [("Receita", F, "Receita"), ("Margem bruta", F, "Margem %"), ("Ticket médio", F, "Ticket Médio"),
          ("Desconto acima da política", F, "Desconto Acima da Política"), ("Taxa de devolução", "fato_devolucoes", "Taxa de Devolução %")]
    w = (R - L - 4 * 10) / 5
    p1 += [card(f"p1_k{i}", round(L + i * (w + 10)), 80, round(w), r, t, m) for i, (r, t, m) in enumerate(kp)]
    p1.append(visual("p1_rec", "clusteredColumnChart", L, 184, 640, 260,
                     {"Category": [("dCalendario", "Mes", "c")], "Y": [(F, "Receita", "m"), (F, "Meta", "m")]},
                     objetos={"dataPoint": [{"properties": {"fill": cor(BEGE)}, "selector": {"metadata": "fato_vendas.Receita"}},
                                            {"properties": {"fill": cor(MARROM)}, "selector": {"metadata": "fato_vendas.Meta"}}]},
                     titulo="Receita x meta por mês"))
    p1.append(visual("p1_lojas", "barChart", L + 650, 184, R - L - 650, 260,
                     {"Category": [("dim_loja", "nome", "c")], "Y": [(F, "Margem %", "m")]},
                     objetos={"dataPoint": [{"properties": {"fill": cor(LARANJA)}}], "labels": [{"properties": {"show": lit("true")}}]},
                     titulo="Margem bruta por loja", ordenar=(F, "Margem %")))
    p1.append(visual("p1_mg", "lineChart", L, 454, R - L, 256,
                     {"Category": [("dCalendario", "Mes", "c")], "Y": [(F, "Margem %", "m"), (F, "Margem % Ano Anterior", "m")]},
                     objetos={"dataPoint": [{"properties": {"fill": cor(LARANJA)}, "selector": {"metadata": "fato_vendas.Margem %"}},
                                            {"properties": {"fill": cor(BEGE)}, "selector": {"metadata": "fato_vendas.Margem % Ano Anterior"}}],
                              "lineStyles": [{"properties": {"lineStyle": lit("'dashed'")}, "selector": {"metadata": "fato_vendas.Margem % Ano Anterior"}}]},
                     titulo="Margem bruta por mês x mesmo mês do ano anterior"))

    p2 = moldura("p2", "Margem e Descontos", "Desconto além do teto de 15% (ou da campanha autorizada) e mix de categorias")
    kp2 = [("Margem bruta", F, "Margem %"), ("Variação (p.p. vs. ano anterior)", F, "Variação da Margem (p.p.)"),
           ("Desconto acima da política", F, "Desconto Acima da Política"), ("Receita vs. ano anterior", F, "Variação da Receita %")]
    w = (R - L - 3 * 10) / 4
    p2 += [card(f"p2_k{i}", round(L + i * (w + 10)), 80, round(w), r, t, m) for i, (r, t, m) in enumerate(kp2)]
    p2.append(visual("p2_desc", "clusteredColumnChart", L, 184, R - L, 250,
                     {"Category": [("dCalendario", "Mes", "c")], "Series": [("dim_loja", "nome", "c")], "Y": [(F, "Desconto Acima da Política", "m")]},
                     titulo="Desconto acima da política por mês e loja"))
    p2.append(visual("p2_tab", "tableEx", L, 444, 620, 266,
                     {"Values": [("dim_loja", "nome", "c"), (F, "Receita", "m"), (F, "Margem %", "m"), (F, "Variação da Margem (p.p.)", "m"),
                                 (F, "Desconto Acima da Política", "m"), (F, "% da Meta", "m")]},
                     titulo="Desempenho por loja"))
    p2.append(visual("p2_cat", "barChart", L + 630, 444, R - L - 630, 266,
                     {"Category": [("dim_produto", "categoria", "c")], "Y": [(F, "Margem %", "m")]},
                     objetos={"dataPoint": [{"properties": {"fill": cor(MARROM)}}], "labels": [{"properties": {"show": lit("true")}}]},
                     titulo="Margem bruta por categoria", ordenar=(F, "Margem %")))

    p3 = moldura("p3", "Devoluções", "Taxa de devolução por fornecedor e motivo")
    D_ = "fato_devolucoes"
    kp3 = [("Unidades devolvidas", D_, "Unidades Devolvidas"), ("Taxa de devolução", D_, "Taxa de Devolução %"),
           ("Devoluções por defeito", D_, "Devoluções por Defeito"), ("Valor estornado", D_, "Valor Estornado")]
    p3 += [card(f"p3_k{i}", round(L + i * (w + 10)), 80, round(w), r, t, m) for i, (r, t, m) in enumerate(kp3)]
    p3.append(visual("p3_linha", "lineChart", L, 184, R - L, 260,
                     {"Category": [("dCalendario", "Mes", "c")], "Series": [("dim_produto", "fornecedor", "c")], "Y": [(D_, "Taxa de Devolução %", "m")]},
                     titulo="Taxa de devolução por fornecedor e mês"))
    p3.append(visual("p3_forn", "tableEx", L, 454, 620, 256,
                     {"Values": [("dim_produto", "fornecedor", "c"), (F, "Unidades Vendidas", "m"), (D_, "Unidades Devolvidas", "m"),
                                 (D_, "Taxa de Devolução %", "m"), (D_, "Valor Estornado", "m")]},
                     titulo="Devoluções por fornecedor"))
    p3.append(visual("p3_mot", "barChart", L + 630, 454, R - L - 630, 256,
                     {"Category": [(D_, "motivo", "c")], "Y": [(D_, "Unidades Devolvidas", "m")]},
                     objetos={"dataPoint": [{"properties": {"fill": cor(LARANJA)}}], "labels": [{"properties": {"show": lit("true")}}]},
                     titulo="Unidades devolvidas por motivo", ordenar=(D_, "Unidades Devolvidas")))
    return [("ReportSection" + str(i + 1), n, v) for i, (n, v) in enumerate([("Visão Geral", p1), ("Margem e Descontos", p2), ("Devoluções", p3)])]

def gerar_relatorio():
    rp = RAIZ / f"{NOME}.Report"; rp.mkdir(parents=True)
    (rp / "definition.pbir").write_text(json.dumps({"version": "4.0", "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}}}, indent=2), encoding="utf-8")
    secoes = []
    for i, (sid, nome, vis) in enumerate(paginas()):
        cfg = {"objects": {"background": [{"properties": {"color": cor(FUNDO), "transparency": lit("0D")}}],
                           "outspace": [{"properties": {"color": cor(FUNDO)}}]}}
        secoes.append({"name": sid, "displayName": nome, "displayOption": 1, "width": 1280, "height": 720, "ordinal": i,
                       "config": json.dumps(cfg), "filters": "[]", "visualContainers": vis})
    # tema: o Power BI exige um tema base (e aceita um personalizado por cima) guardado em StaticResources
    tema = {"name": "Varejo", "dataColors": [LARANJA, MARROM, "#D9B48A", "#4A2E1E", "#E9A36B", "#8C6A55", "#B5651D", "#5C4033"],
            "background": "#FFFFFF", "foreground": ESCURO, "tableAccent": LARANJA, "good": "#1D7F47", "bad": "#C93A3A", "neutral": "#8A94A6",
            "textClasses": {"callout": {"fontSize": 22, "fontFace": "Segoe UI Semibold", "color": ESCURO},
                            "title": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": ESCURO},
                            "header": {"fontSize": 11, "fontFace": "Segoe UI Semibold", "color": ESCURO},
                            "label": {"fontSize": 9, "fontFace": "Segoe UI", "color": "#6E5A4B"}}}
    base = rp / "StaticResources" / "SharedResources" / "BaseThemes"; base.mkdir(parents=True)
    (base / "CY24SU10.json").write_text(json.dumps({**tema, "name": "CY24SU10"}, indent=2), encoding="utf-8")
    reg = rp / "StaticResources" / "RegisteredResources"; reg.mkdir(parents=True)
    (reg / "Varejo.json").write_text(json.dumps(tema, indent=2), encoding="utf-8")
    rep = {"config": json.dumps({"version": "5.61",
                                 "themeCollection": {"baseTheme": {"name": "CY24SU10", "version": "5.61", "type": 2},
                                                     "customTheme": {"name": "Varejo.json", "version": "5.61", "type": 1}},
                                 "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
                                 "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": 1}}),
           "layoutOptimization": 0,
           "resourcePackages": [
               {"resourcePackage": {"name": "SharedResources", "type": 2, "disabled": False,
                                    "items": [{"type": 202, "path": "BaseThemes/CY24SU10.json", "name": "CY24SU10"}]}},
               {"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                                    "items": [{"type": 201, "path": "Varejo.json", "name": "Varejo.json"}]}}],
           "sections": secoes, "filters": "[]"}
    (rp / "report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")

if __name__ == "__main__":
    if RAIZ.exists(): shutil.rmtree(RAIZ)
    RAIZ.mkdir()
    (RAIZ / f"{NOME}.pbip").write_text(json.dumps({"version": "1.0", "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
                                                  "settings": {"enableAutoRecovery": True}}, indent=2), encoding="utf-8")
    (RAIZ / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    gerar_modelo(); gerar_relatorio()
    for f in sorted(RAIZ.rglob("*")):
        if f.is_file(): print(f.relative_to(AQUI), f.stat().st_size)
