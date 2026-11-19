# -*- coding: utf-8 -*-
"""
ANTECIPA — Planilha de validação da tabela de pontos com os gestores de risco do STF.

Abas:
  Leia-me          finalidade, como usar, legenda de cores, exemplo de preenchimento
  Fatores          um fator por linha: regra, peso atual, PESO PROPOSTO (editável),
                   nº de contratos afetados, racional, perguntas, avaliação
  Resultado        efeito dos pesos propostos sobre a carteira do STF, ao vivo
  Contratos        motor do simulador: 293 contratos × fatores, com fórmulas
  Questões gerais  impacto, conversão, faixas do modelo, risco residual, rótulo,
                   fatores candidatos
  Escala 781       escalas oficiais da Res. STF 781/2022 e conversões do ANTECIPA

Os pesos atuais vêm de escala_781.PESOS e os sinais por contrato do
antecipa_dados.json (rodar processa.py antes). Com os pesos propostos iguais aos
atuais, a aba Resultado reproduz exatamente os números do painel — há um bloco de
conferência para isso. O .xlsx é gravado em ../ (fora do repositório).
"""
import json
from collections import Counter
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import escala_781 as E

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"
DESTINO = BASE.parent / "Validacao_tabela_de_pontos_ANTECIPA.xlsx"

dados = json.loads((PROC / "antecipa_dados.json").read_text(encoding="utf-8"))
ps = sorted(dados["processos"], key=lambda p: -p["valor"])
N = len(ps)
L0, L1 = 8, 8 + N - 1                    # primeira e última linha de dados (Contratos)

# ------------------------------------------------------------------ estilos
F = "Arial"
f_base = Font(name=F, size=10)
f_neg = Font(name=F, size=10, bold=True)
f_tit = Font(name=F, size=14, bold=True, color="1F4E79")
f_sub = Font(name=F, size=10, italic=True, color="595959")
f_cab = Font(name=F, size=10, bold=True, color="FFFFFF")
f_azul = Font(name=F, size=10, color="0000FF")
f_azul_neg = Font(name=F, size=10, color="0000FF", bold=True)
f_verde = Font(name=F, size=10, color="008000")
f_sec = Font(name=F, size=11, bold=True, color="1F4E79")
p_cab = PatternFill("solid", fgColor="1F4E79")
p_edit = PatternFill("solid", fgColor="FFF2CC")
p_cinza = PatternFill("solid", fgColor="F2F2F2")
fino = Side(style="thin", color="BFBFBF")
borda = Border(left=fino, right=fino, top=fino, bottom=fino)
quebra = Alignment(wrap_text=True, vertical="top")
centro = Alignment(horizontal="center", vertical="top", wrap_text=True)
NIV_COR = {"Baixo": "C6EFCE", "Moderado": "FFEB9C", "Elevado": "F8CBAD", "Crítico": "FF9999"}

wb = Workbook()


def larguras(ws, ws_larg):
    for i, w in enumerate(ws_larg, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def cab(ws, linha, textos, col0=1):
    for j, t in enumerate(textos):
        c = ws.cell(row=linha, column=col0 + j, value=t)
        c.font, c.fill, c.alignment, c.border = f_cab, p_cab, centro, borda


def escreve(ws, linha, col, valor, fonte=None, fmt=None, fill=None, alin=None):
    c = ws.cell(row=linha, column=col, value=valor)
    c.font = fonte or f_base
    c.alignment = alin or quebra
    c.border = borda
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    return c


# ======================================================= definição dos fatores
# (id, leitura, nome, regra, fonte, efeito, racional, perguntas)
FAT = [
    ("B0", "Base", "Ponto de partida",
     "Todo contrato começa com 1,0 ponto (posição Muito baixa).", "—", "Ponto de partida",
     "Sem nenhum sinal de risco, a probabilidade é a mínima da escala (“Rara”).",
     "Algum tipo de objeto (p. ex. obras, serviços com mão de obra dedicada) deveria partir de um nível "
     "acima de “Muito baixa”?"),
    ("F1", "Ex-ante", "Capital social baixo em relação ao contrato",
     "Capital social inferior a 2% do valor global do contrato.", "Receita Federal (CNPJ aberto) + PNCP",
     "Aumenta",
     "Capital muito inferior ao compromisso assumido sugere menor capacidade de suportar a execução.",
     "1) O descompasso entre capital e valor do contrato é, na experiência da área, sinal de risco de "
     "inexecução? 2) A Lei 14.133/2021 (art. 69, § 4º) permite exigir capital mínimo de até 10% do valor "
     "estimado: 10% seria limiar melhor que 2%? 3) O peso deveria ser maior em serviços com mão de obra "
     "dedicada?"),
    ("F2", "Ex-ante", "Capital social elevado em relação ao contrato",
     "Capital social superior a 30% do valor global do contrato.", "Receita Federal (CNPJ aberto) + PNCP",
     "Reduz",
     "Folga patrimonial reduz o risco de inexecução.",
     "Capital elevado deve reduzir a probabilidade ou apenas deixar de somar pontos? Hoje o fator aparece "
     "em quase toda a carteira: o limiar de 30% é adequado?"),
    ("F3", "Ex-ante", "Capital social não informado",
     "Campo vazio ou igual a zero na base aberta da Receita.", "Receita Federal (CNPJ aberto)", "Aumenta",
     "A ausência do dado impede a verificação; é comum em consórcios.",
     "A falta do dado deve pesar? Consórcios deveriam ter tratamento próprio (p. ex. considerar o capital "
     "das empresas consorciadas)?"),
    ("F4", "Ex-ante", "Empresa recente",
     "CNPJ com menos de 3 anos na data da assinatura.", "Receita Federal (CNPJ aberto)", "Aumenta",
     "Pouco histórico de execução e maior mortalidade das empresas jovens.",
     "1) Empresa recente é sinal de risco na experiência da área? Qual idade seria referência (2, 3, 5 "
     "anos)? 2) Como evitar penalizar microempresas e EPP, que a LC 123/2006 manda favorecer?"),
    ("F5", "Ex-ante", "Empresa consolidada",
     "CNPJ com mais de 10 anos na data da assinatura.", "Receita Federal (CNPJ aberto)", "Reduz",
     "Tempo de mercado indica sobrevivência e experiência acumulada.",
     "Tempo de mercado deve reduzir a probabilidade? A partir de quantos anos?"),
    ("F6", "Ex-ante", "Crescimento contratual atípico",
     "Nº de contratos no último ano ≥ 3 vezes a mediana dos anos anteriores (PNCP, todos os órgãos). "
     "Avaliado só para os 15 maiores fornecedores.", "PNCP (busca nacional)", "Aumenta",
     "Expansão abrupta da carteira pública pode indicar sobrecarga operacional.",
     "A área observa inexecução em fornecedores que cresceram rápido? Vale coletar a série nacional "
     "para todos os fornecedores?"),
    ("F7", "Ex-ante", "Situação cadastral irregular",
     "Situação na Receita diferente de “Ativa” (suspensa, inapta, baixada).", "Receita Federal (CNPJ aberto)",
     "Aumenta",
     "CNPJ irregular é sinal grave de irregularidade do fornecedor.",
     "Na prática, isso já impede a contratação na fase de habilitação? Se sim, o fator só sinalizaria falha "
     "de controle — deveria levar o contrato direto a Crítico?"),
    ("F8", "Ex-ante", "Vigência longa",
     "Vigência prevista superior a 12 meses.", "PNCP", "Aumenta",
     "Mais tempo de execução, mais exposição a eventos adversos.",
     "A duração deve pesar na probabilidade ou só no impacto? Serviços continuados, prorrogáveis por "
     "natureza, deveriam ter tratamento à parte? (Hoje o fator aparece em quase toda a carteira.)"),
    ("F9", "Ex-ante", "Sanção vigente na assinatura",
     "Sanção no CEIS ou no CNEP em vigor e já publicada na data da assinatura.",
     "Portal da Transparência (CEIS/CNEP)", "Aumenta",
     "Era consultável antes de contratar; indica risco grave ou falha de controle.",
     "1) A Lei 14.133/2021 (art. 91, § 4º) obriga a consulta antes de contratar: uma sanção vigente deveria "
     "levar direto a Crítico? 2) Sanções de abrangência restrita (impedimento aplicado por outro ente) e "
     "nacional (inidoneidade) devem ter pesos diferentes? (Hoje não aparece em nenhum contrato do STF.)"),
    ("O1", "Observado", "Aditivos acumulados",
     "Dois ou mais termos aditivos firmados.", "PNCP (termos do contrato)", "Aumenta",
     "Alterações recorrentes indicam problemas de planejamento ou de execução.",
     "Quantos aditivos indicam problema? Aditivos de mera prorrogação em serviço continuado deveriam "
     "ficar fora da contagem?"),
    ("O2", "Observado", "Acréscimo de valor",
     "Valor acumulado mais de 10% acima do valor inicial.", "PNCP (termos do contrato)", "Aumenta",
     "Acréscimos relevantes indicam subdimensionamento ou mudança de escopo.",
     "Que percentual a área considera sinal de alerta? (A lei admite acréscimos de até 25%, ou 50% em "
     "reformas.)"),
    ("O3", "Observado", "Rescisão",
     "Termo de rescisão ou de extinção registrado no PNCP.", "PNCP (termos do contrato)", "Aumenta",
     "O contrato foi encerrado antes do previsto.",
     "É possível distinguir rescisão por inadimplemento de rescisão amigável ou por conveniência da "
     "Administração? Só a primeira deveria pesar?"),
]
PESO = {"B0": E.BASE_PONTOS, **E.PESOS}
IDS = [f[0] for f in FAT]
# coluna de cada fator na aba Contratos (F = base, G…O = F1…F9, P…R = O1…O3)
COL = {fid: get_column_letter(6 + i) for i, fid in enumerate(IDS)}
LIN_FAT = {fid: 5 + i for i, fid in enumerate(IDS)}       # linha na aba Fatores
assert set(PESO) == set(IDS), "escala_781.PESOS e a lista de fatores divergem"

# ======================================================================== Leia-me
ws = wb.active
ws.title = "Leia-me"
larguras(ws, [3, 26, 22, 14, 14, 40, 20, 14])
ws["B1"] = "ANTECIPA — Validação da tabela de pontos (Res. STF 781/2022)"
ws["B1"].font = f_tit
ws["B2"] = (f"Planilha para discussão com os gestores de risco do STF · dados de "
            f"{dados['resumo']['coletado_em']} (PNCP), sanções de {dados['resumo'].get('sancoes_consulta') or '—'} "
            f"· gerada em {date.today().strftime('%d/%m/%Y')}")
ws["B2"].font = f_sub
txt = [
    ("Para que serve",
     "A Res. 781/2022 define as escalas de probabilidade e impacto (níveis 1·2·5·8·10, risco de 0 a 100), "
     "mas não diz como transformar dados de um contrato em um nível. O ANTECIPA faz essa conversão com uma "
     "tabela de pontos própria: cada sinal observado soma ou subtrai pontos, e o total indica o nível de "
     "probabilidade. Esta planilha serve para validar essa tabela com quem conhece a realidade das "
     "contratações do STF."),
    ("Por que importa",
     "Com os pesos atuais, a leitura ex-ante (antes da assinatura) classifica pouquíssimos contratos como "
     "Elevado ou Crítico — e erra os que classifica. Esse resultado depende dos pesos. Validá-los com a área "
     "é parte do resultado da pesquisa, não um detalhe."),
    ("Como usar",
     "1) Na aba Fatores, leia a regra, o racional e as perguntas de cada linha. 2) Registre a avaliação "
     "(Manter / Ajustar / Excluir), comentários, quem validou e a data. 3) Se a área sugerir outro peso, "
     "digite-o na coluna “Peso proposto”. 4) Veja na aba Resultado, na hora, como a carteira do STF muda com "
     "os pesos propostos. 5) Use a aba Questões gerais para os temas que não são de um fator só."),
    ("O que o simulador faz",
     "Recalcula os 293 contratos do STF com os pesos propostos e compara com os atuais: quantos ficam em cada "
     "nível e quantos dos alertas (Elevado + Crítico) tiveram desfecho adverso. Ele varia os PESOS. Mudanças "
     "de LIMIAR (p. ex. 2% → 10% do capital) exigem reprocessar os dados: anote-as nos comentários."),
]
r = 4
for titulo, corpo in txt:
    ws.cell(row=r, column=2, value=titulo).font = f_sec
    c = ws.cell(row=r + 1, column=2, value=corpo)
    c.font, c.alignment = f_base, quebra
    ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=8)
    ws.row_dimensions[r + 1].height = 62
    r += 3

ws.cell(row=r, column=2, value="Legenda de cores").font = f_sec
leg = [
    (p_edit, f_base, "Amarelo", "Células para preencher ou editar (peso proposto, avaliação, comentários)."),
    (None, f_azul, "Texto azul", "Valores atuais de referência — não editar."),
    (None, f_verde, "Texto verde", "Vínculo com outra aba (preenchido automaticamente)."),
    (None, f_base, "Texto preto", "Dados do PNCP, da Receita e do Portal da Transparência, ou fórmulas."),
]
for i, (fill, fonte, rot, desc) in enumerate(leg, 1):
    escreve(ws, r + i, 2, rot, fonte=fonte, fill=fill)
    escreve(ws, r + i, 3, desc)
    ws.merge_cells(start_row=r + i, start_column=3, end_row=r + i, end_column=8)
r += len(leg) + 2

ws.cell(row=r, column=2, value="Exemplo de preenchimento (ilustrativo — não é uma avaliação real)").font = f_sec
cab(ws, r + 1, ["Fator", "Peso atual", "Peso proposto", "Avaliação", "Comentários", "Validado por", "Data"],
    col0=2)
ex = ["F4 — Empresa recente", 0.8, 0.5, "Ajustar",
      "Empresas recentes são comuns entre ME/EPP; reduzir o peso para não penalizar o porte (LC 123/2006).",
      "Nome — unidade", date(2026, 11, 25)]
for j, v in enumerate(ex):
    c = escreve(ws, r + 2, 2 + j, v, fill=p_cinza)
    if j in (1, 2):
        c.number_format = "0.0"
    if j == 6:
        c.number_format = "dd/mm/yyyy"
ws.row_dimensions[r + 2].height = 40
r += 4

ws.cell(row=r, column=2, value="Fontes").font = f_sec
fontes = ("Escalas oficiais: anexos da Resolução STF nº 781/2022 (probabilidade, impacto, nível de risco e "
          "eficácia dos controles). Contratos e termos: API de Consulta do PNCP. Capital, idade e situação: "
          "dados abertos do CNPJ (Receita Federal). Sanções: API do Portal da Transparência (CEIS e CNEP). "
          "Metodologia completa: RESULTADOS.md do projeto ANTECIPA.")
c = ws.cell(row=r + 1, column=2, value=fontes)
c.font, c.alignment = f_base, quebra
ws.merge_cells(start_row=r + 1, start_column=2, end_row=r + 1, end_column=8)
ws.row_dimensions[r + 1].height = 50

# ======================================================================== Fatores
wf = wb.create_sheet("Fatores")
larguras(wf, [6, 11, 26, 34, 22, 9, 11, 12, 11, 34, 52, 13, 38, 18, 12])
wf["A1"] = "Tabela de pontos do escore heurístico — fatores, pesos e perguntas"
wf["A1"].font = f_tit
wf["A2"] = ("Edite somente as células amarelas. “Peso proposto” começa igual ao atual; altere-o para "
            "simular (veja a aba Resultado). Leituras: Ex-ante = conhecido na assinatura; Observado = "
            "ocorrido depois (só entra no nível observado).")
wf["A2"].font = f_sub
wf.merge_cells("A2:O2")
cab(wf, 4, ["ID", "Leitura", "Fator", "Regra aplicada no ANTECIPA", "Fonte do dado", "Peso atual",
            "Peso proposto", "Contratos do STF em que aparece", "Efeito no risco", "Por que foi proposto",
            "Perguntas para os gestores", "Avaliação", "Comentários e ajustes sugeridos", "Validado por",
            "Data"])
for fid, leit, nome, regra, fonte, efeito, rac, perg in FAT:
    r = LIN_FAT[fid]
    escreve(wf, r, 1, fid, fonte=f_neg, alin=centro)
    escreve(wf, r, 2, leit, alin=centro)
    escreve(wf, r, 3, nome, fonte=f_neg)
    escreve(wf, r, 4, regra)
    escreve(wf, r, 5, fonte)
    escreve(wf, r, 6, PESO[fid], fonte=f_azul_neg, fmt="+0.0;-0.0;0.0", alin=centro)
    escreve(wf, r, 7, PESO[fid], fonte=f_neg, fmt="+0.0;-0.0;0.0", fill=p_edit, alin=centro)
    col = COL[fid]
    cont = (f"=COUNTA(Contratos!A{L0}:A{L1})" if fid == "B0"
            else f"=SUM(Contratos!{col}{L0}:{col}{L1})")
    escreve(wf, r, 8, cont, alin=centro, fmt="0")
    escreve(wf, r, 9, efeito, alin=centro)
    escreve(wf, r, 10, rac)
    escreve(wf, r, 11, perg)
    for cc in (12, 13, 14):
        escreve(wf, r, cc, None, fill=p_edit)
    escreve(wf, r, 15, None, fill=p_edit, fmt="dd/mm/yyyy")
    wf.row_dimensions[r].height = 92
wf.freeze_panes = "D5"
ult = LIN_FAT["O3"]
dv = DataValidation(type="list", formula1='"Manter,Ajustar,Excluir"', allow_blank=True)
dv.error, dv.errorTitle = "Escolha Manter, Ajustar ou Excluir.", "Avaliação"
wf.add_data_validation(dv)
dv.add(f"L5:L{ult}")
dvp = DataValidation(type="decimal", operator="between", formula1="-10", formula2="10", allow_blank=False)
dvp.error, dvp.errorTitle = "Use um número entre -10 e 10 (ex.: 0,8).", "Peso proposto"
wf.add_data_validation(dvp)
dvp.add(f"G5:G{ult}")
wf["G4"].comment = Comment("Edite aqui. Para EXCLUIR um fator do cálculo, use peso 0.", "ANTECIPA")
wf["H4"].comment = Comment("Quantos dos 293 contratos do STF apresentam o sinal. Um fator que quase "
                           "nunca aparece pouco influi no resultado, qualquer que seja o peso.", "ANTECIPA")

# ====================================================================== Contratos
wc = wb.create_sheet("Contratos")
larguras(wc, [12, 30, 40, 15, 9] + [6] * 13 + [9] + [8, 7, 10] * 4 + [10, 11])
wc["A1"] = "Motor do simulador — carteira do STF (não é preciso editar esta aba)"
wc["A1"].font = f_tit
wc["A2"] = ("1 = o sinal está presente no contrato. Os pontos somam base + fatores × pesos; o total é "
            "arredondado (0,5 para cima) e limitado a 1–5, que vira 1·2·5·8·10; risco = probabilidade × "
            "impacto (0–100). Linhas 4 e 5 trazem os pesos da aba Fatores.")
wc["A2"].font = f_sub
wc.merge_cells("A2:AE2")
escreve(wc, 4, 5, "Pesos atuais →", fonte=f_neg)
escreve(wc, 5, 5, "Pesos propostos →", fonte=f_neg)
for fid in IDS:
    j = 6 + IDS.index(fid)
    escreve(wc, 4, j, f"=Fatores!F{LIN_FAT[fid]}", fonte=f_verde, fmt="0.0", alin=centro)
    escreve(wc, 5, j, f"=Fatores!G{LIN_FAT[fid]}", fonte=f_verde, fmt="0.0", alin=centro)
# faixas de cabeçalho
for txt_, c1, c2 in (("Contrato", 1, 5), ("Sinais (1 = presente)", 6, 18), ("Desfecho", 19, 19),
                     ("Ex-ante — pesos atuais", 20, 22), ("Ex-ante — pesos propostos", 23, 25),
                     ("Observado — pesos atuais", 26, 28), ("Observado — pesos propostos", 29, 31)):
    wc.merge_cells(start_row=6, start_column=c1, end_row=6, end_column=c2)
    c = wc.cell(row=6, column=c1, value=txt_)
    c.font, c.fill, c.alignment = f_cab, p_cab, centro
cab(wc, 7, ["Processo", "Fornecedor", "Objeto", "Valor global (R$)", "Impacto (1–5)"] + IDS +
    ["Adverso"] + ["Pontos", "Risco", "Nível"] * 4 + ["Muda ex-ante?", "Muda observado?"])
wc.merge_cells(start_row=6, start_column=32, end_row=6, end_column=33)
c = wc.cell(row=6, column=32, value="Mudança de nível")
c.font, c.fill, c.alignment = f_cab, p_cab, centro


def bloco(pts_expr):
    """fórmulas de risco e nível a partir da célula de pontos (posição 0,5 para cima)"""
    return (f"=CHOOSE(MIN(5,MAX(1,INT(ROUND({pts_expr},6)+0.5))),1,2,5,8,10)"
            f"*CHOOSE($E{{r}},1,2,5,8,10)")


niv = 'IF({v}>=80,"Crítico",IF({v}>=40,"Elevado",IF({v}>=10,"Moderado","Baixo")))'
EX0, EX1 = COL["B0"], COL["F9"]                 # F … O
OB0, OB1 = COL["O1"], COL["O3"]                 # P … R
for i, p in enumerate(ps):
    r = L0 + i
    ids = {f[3] for f in p["fatores"] if len(f) > 3}
    escreve(wc, r, 1, p["id"].strip())
    escreve(wc, r, 2, (p.get("forn_nome") or "")[:60])
    escreve(wc, r, 3, (p.get("obj") or "")[:90])
    escreve(wc, r, 4, p["valor"], fmt='"R$" #,##0')
    escreve(wc, r, 5, p["imp"], alin=centro)
    for fid in IDS:
        escreve(wc, r, 6 + IDS.index(fid), 1 if (fid == "B0" or fid in ids) else 0, alin=centro)
    escreve(wc, r, 19, int(p["desfecho"]["desfecho_adverso"]), alin=centro)
    # ex-ante atual (T U V) e proposto (W X Y)
    for col_pts, linha_peso in (("T", 4), ("W", 5)):
        cp = wc[f"{col_pts}{r}"]
        cp.value = f"=SUMPRODUCT(${EX0}${linha_peso}:${EX1}${linha_peso},{EX0}{r}:{EX1}{r})"
    # observado = ex-ante + fatores posteriores
    wc[f"Z{r}"] = f"=T{r}+SUMPRODUCT(${OB0}$4:${OB1}$4,{OB0}{r}:{OB1}{r})"
    wc[f"AC{r}"] = f"=W{r}+SUMPRODUCT(${OB0}$5:${OB1}$5,{OB0}{r}:{OB1}{r})"
    for pts, rsk, nv in (("T", "U", "V"), ("W", "X", "Y"), ("Z", "AA", "AB"), ("AC", "AD", "AE")):
        wc[f"{rsk}{r}"] = bloco(f"{pts}{r}").format(r=r)
        wc[f"{nv}{r}"] = "=" + niv.format(v=f"{rsk}{r}")
        for cl, fmt in ((pts, "0.0"), (rsk, "0"), (nv, None)):
            c = wc[f"{cl}{r}"]
            c.font, c.border, c.alignment = f_base, borda, centro
            if fmt:
                c.number_format = fmt
    # auxiliares: 1 = o nível muda com os pesos propostos
    escreve(wc, r, 32, f'=IF(V{r}=Y{r},0,1)', alin=centro, fmt="0")
    escreve(wc, r, 33, f'=IF(AB{r}=AE{r},0,1)', alin=centro, fmt="0")
wc.freeze_panes = f"D{L0}"
for cl in ("V", "Y", "AB", "AE"):
    for nome_, cor in NIV_COR.items():
        wc.conditional_formatting.add(f"{cl}{L0}:{cl}{L1}", CellIsRule(
            operator="equal", formula=[f'"{nome_}"'], fill=PatternFill("solid", fgColor=cor)))

# ====================================================================== Resultado
wr = wb.create_sheet("Resultado", 2)
larguras(wr, [44, 18, 18, 18, 18, 4, 16, 16, 12])
wr["A1"] = "Resultado da simulação — carteira do STF"
wr["A1"].font = f_tit
wr["A2"] = ("Atualiza sozinho quando você muda um “Peso proposto” na aba Fatores. A leitura observada usa o "
            "próprio desfecho e é circular: serve de referência, não de previsão.")
wr["A2"].font = f_sub
wr.merge_cells("A2:I2")
cab(wr, 4, ["Nível", "Ex-ante — pesos atuais", "Ex-ante — pesos propostos",
            "Observado — pesos atuais", "Observado — pesos propostos"])
NIVCOL = {"B": "V", "C": "Y", "D": "AB", "E": "AE"}
for k, nivel in enumerate(["Baixo", "Moderado", "Elevado", "Crítico"]):
    r = 5 + k
    escreve(wr, r, 1, nivel, fonte=f_neg, fill=PatternFill("solid", fgColor=NIV_COR[nivel]))
    for cl, cc in NIVCOL.items():
        escreve(wr, r, ord(cl) - 64, f'=COUNTIF(Contratos!{cc}${L0}:{cc}${L1},$A{r})', alin=centro, fmt="0")
escreve(wr, 9, 1, "Total de contratos", fonte=f_neg)
for cl in NIVCOL:
    escreve(wr, 9, ord(cl) - 64, f"=SUM({cl}5:{cl}8)", fonte=f_neg, alin=centro, fmt="0")

rot = [(11, "Alertas (Elevado + Crítico)"), (12, "Acertos: alertas com desfecho adverso"),
       (13, "Precisão dos alertas"), (14, "Recall: adversos que viraram alerta"),
       (15, "Taxa base de desfecho adverso"), (16, "Lift (precisão ÷ taxa base)")]
for r, t in rot:
    escreve(wr, r, 1, t, fonte=f_neg)
ADV = f"Contratos!$S${L0}:$S${L1}"
for cl, cc in NIVCOL.items():
    j = ord(cl) - 64
    rng = f"Contratos!{cc}${L0}:{cc}${L1}"
    escreve(wr, 11, j, f"={cl}7+{cl}8", alin=centro, fmt="0")
    escreve(wr, 12, j, f'=COUNTIFS({rng},"Elevado",{ADV},1)+COUNTIFS({rng},"Crítico",{ADV},1)',
            alin=centro, fmt="0")
    escreve(wr, 13, j, f'=IF({cl}11=0,"sem alertas",{cl}12/{cl}11)', alin=centro, fmt="0.0%")
    escreve(wr, 14, j, f"={cl}12/SUM({ADV})", alin=centro, fmt="0.0%")
    escreve(wr, 15, j, f"=AVERAGE({ADV})", alin=centro, fmt="0.0%")
    escreve(wr, 16, j, f'=IF({cl}11=0,"—",{cl}13/{cl}15)', alin=centro, fmt='0.00"×"')
escreve(wr, 18, 1, "Contratos que mudam de nível (propostos × atuais)", fonte=f_neg)
escreve(wr, 18, 3, f"=SUM(Contratos!AF{L0}:AF{L1})", alin=centro, fmt="0")
escreve(wr, 18, 5, f"=SUM(Contratos!AG{L0}:AG{L1})", alin=centro, fmt="0")
c = wr.cell(row=19, column=1, value=("Precisão abaixo da taxa base (lift < 1) significa que os alertas acertam "
                                      "menos que um sorteio ao acaso."))
c.font, c.alignment = f_sub, quebra
wr.merge_cells("A19:E19")

# conferência com o painel
conta_ex = Counter(p["nivel_ex"] for p in ps)
conta_ob = Counter(p["nivel"] for p in ps)
wr["A21"] = "Conferência: com os pesos atuais, a planilha deve reproduzir o painel"
wr["A21"].font = f_sec
cab(wr, 22, ["Nível", "Painel — ex-ante", "Planilha — ex-ante", "Painel — observado",
             "Planilha — observado", "", "Ex-ante confere?", "Observado confere?"])
for k, nivel in enumerate(["Baixo", "Moderado", "Elevado", "Crítico"]):
    r = 23 + k
    escreve(wr, r, 1, nivel, fonte=f_neg)
    escreve(wr, r, 2, conta_ex.get(nivel, 0), fonte=f_azul, alin=centro)
    escreve(wr, r, 3, f"=B{5 + k}", fonte=f_verde, alin=centro)
    escreve(wr, r, 4, conta_ob.get(nivel, 0), fonte=f_azul, alin=centro)
    escreve(wr, r, 5, f"=D{5 + k}", fonte=f_verde, alin=centro)
    escreve(wr, r, 7, f'=IF(B{r}=C{r},"OK","DIFERENTE")', alin=centro)
    escreve(wr, r, 8, f'=IF(D{r}=E{r},"OK","DIFERENTE")', alin=centro)
wr["B22"].comment = Comment(f"Contagens do painel ANTECIPA geradas em {date.today().strftime('%d/%m/%Y')} "
                            "(antecipa_dados.json).", "ANTECIPA")

# ================================================================ Questões gerais
wq = wb.create_sheet("Questões gerais")
larguras(wq, [5, 22, 40, 52, 42, 18, 12])
wq["A1"] = "Questões gerais — temas que não dependem de um fator só"
wq["A1"].font = f_tit
cab(wq, 3, ["#", "Tema", "Como é hoje no ANTECIPA", "Pergunta para os gestores", "Resposta / encaminhamento",
            "Responsável", "Data"])
QG = [
    ("Impacto — critério", "Impacto = quintil do valor global do contrato na carteira do STF (aba Escala 781).",
     "O valor do contrato representa bem o “comprometimento do objetivo” da escala de impacto? A criticidade "
     "do serviço (segurança, TI, manutenção predial, saúde) deveria entrar?"),
    ("Impacto — faixas", "Os limites são quintis da própria carteira (relativos), não valores fixos em R$.",
     "A área prefere faixas fixas em R$, estáveis no tempo? Com quais limites?"),
    ("Conversão de pontos em nível", "Soma de pontos, arredondada (0,5 para cima) e limitada a 1–5, que vira "
     "1·2·5·8·10.", "A conversão linear é adequada, ou seria melhor definir faixas de pontos para cada nível?"),
    ("Probabilidade do modelo", "Faixas fixas: <2% Muito baixa · 2–5% Baixa · 5–10% Média · 10–20% Alta · "
     "≥20% Muito alta (taxa base de 1,8%).", "Que probabilidades a área associaria a “Rara”, “Improvável”, "
     "“Possível”, “Provável” e “Praticamente certa” em contratos? ≥20% merece “Muito alta”?"),
    ("Risco residual", "Só o risco inerente é calculado: a eficácia dos controles (fator 1,0 a 0,2) não é "
     "dado público.", "Há avaliação de controles por tipo de contratação (fiscalização, garantia, gestão "
     "contratual) que permita calcular o risco residual?"),
    ("Evento de risco (o que é “dar problema”)", "Desfecho adverso = rescisão, acréscimo de valor > 25% ou "
     "prorrogação > 365 dias.", "Esses eventos representam “problema” para a área? Faltam eventos (glosas, "
     "penalidades aplicadas, atrasos)? Há dados internos que os registrem?"),
    ("Tipo de objeto", "Os mesmos pesos valem para compras, serviços continuados e obras.",
     "Deveria haver tabelas de pontos diferentes por tipo de objeto?"),
    ("Capacidade de diligência", "O modelo ordena os contratos por probabilidade; o painel não fixa um ponto "
     "de corte.", "Quantos contratos a área consegue examinar por mês? Esse número define o tamanho da fila de "
     "alertas."),
]
for i, (tema, hoje, perg) in enumerate(QG, 1):
    r = 3 + i
    escreve(wq, r, 1, i, alin=centro)
    escreve(wq, r, 2, tema, fonte=f_neg)
    escreve(wq, r, 3, hoje)
    escreve(wq, r, 4, perg)
    for cc in (5, 6):
        escreve(wq, r, cc, None, fill=p_edit)
    escreve(wq, r, 7, None, fill=p_edit, fmt="dd/mm/yyyy")
    wq.row_dimensions[r].height = 64
r0 = 4 + len(QG) + 1
wq.cell(row=r0, column=2, value="Fatores candidatos — a área considera incluir?").font = f_sec
cab(wq, r0 + 1, ["#", "Fator candidato", "Fonte", "Disponível em dados públicos?", "A área considera relevante?",
                 "Peso sugerido", "Comentários"])
CAND = [
    ("Modalidade: dispensa ou inexigibilidade (× pregão/concorrência)", "PNCP", "Sim"),
    ("Número de propostas ou licitantes (competição)", "PNCP (resultado da compra)", "Parcialmente"),
    ("Sanções anteriores aplicadas pelo próprio STF ao fornecedor", "Portal da Transparência", "Sim"),
    ("Histórico de aditivos do fornecedor em contratos anteriores com o STF", "PNCP", "Sim"),
    ("Desconto muito acima da média (risco de inexequibilidade)", "PNCP / compras.gov.br", "Parcialmente"),
    ("Ocorrências de fiscalização (notificações, glosas)", "Sistemas internos do STF", "Não"),
]
for i, (fc, fonte, disp) in enumerate(CAND, 1):
    r = r0 + 1 + i
    escreve(wq, r, 1, i, alin=centro)
    escreve(wq, r, 2, fc, fonte=f_neg)
    escreve(wq, r, 3, fonte)
    escreve(wq, r, 4, disp, alin=centro)
    escreve(wq, r, 5, None, fill=p_edit)
    escreve(wq, r, 6, None, fill=p_edit, fmt="0.0")
    escreve(wq, r, 7, None, fill=p_edit)
    wq.row_dimensions[r].height = 34
wq.freeze_panes = "C4"

# ===================================================================== Escala 781
we = wb.create_sheet("Escala 781")
larguras(we, [16, 10, 20, 70, 4, 12, 12, 12, 12, 12, 12])
we["A1"] = "Escalas oficiais da Res. STF 781/2022 e conversões usadas no ANTECIPA"
we["A1"].font = f_tit
we["A2"] = "Fonte: anexos da Resolução STF nº 781/2022 (Política de Gestão de Riscos do STF)."
we["A2"].font = f_sub
r = 4
we.cell(row=r, column=1, value="Escala de probabilidade").font = f_sec
cab(we, r + 1, ["Probabilidade", "Valor", "Descritor", "Descrição oficial"])
PROB = [("Muito baixa", 1, "Rara", "O evento poderá ocorrer, mas em situações excepcionais."),
        ("Baixa", 2, "Improvável", "De forma ocasional o evento poderá ocorrer, mas há poucas chances de acontecer."),
        ("Média", 5, "Possível", "O evento poderá ocorrer, pois há chances razoáveis de acontecer."),
        ("Alta", 8, "Provável", "O evento tende a ocorrer, pois há muitas chances de acontecer."),
        ("Muito alta", 10, "Praticamente certa",
         "O evento deve ocorrer. Somente não acontecerá em situações excepcionais.")]
for i, linha in enumerate(PROB):
    for j, v in enumerate(linha):
        escreve(we, r + 2 + i, 1 + j, v, fonte=f_azul if j == 1 else None, alin=centro if j == 1 else None)
r += 2 + len(PROB) + 1
we.cell(row=r, column=1, value="Escala de impacto").font = f_sec
cab(we, r + 1, ["Impacto", "Valor", "Descritor", "Descrição oficial"])
IMP = [("Muito baixo", 1, "Insignificante",
        "Compromete minimamente o alcance do objetivo/resultado, com mínima necessidade de recuperação."),
       ("Baixo", 2, "Pequeno",
        "Compromete em alguma medida o alcance do objetivo/resultado, com pequena necessidade de recuperação."),
       ("Médio", 5, "Moderado",
        "Compromete razoavelmente o alcance do objetivo/resultado, com razoável necessidade de recuperação."),
       ("Alto", 8, "Significativo",
        "Compromete grande parte do alcance do objetivo/resultado, mas com possibilidade de recuperação."),
       ("Muito alto", 10, "Catastrófico",
        "Compromete total ou quase totalmente o alcance do objetivo/resultado, com remota ou nenhuma "
        "possibilidade de recuperação.")]
for i, linha in enumerate(IMP):
    for j, v in enumerate(linha):
        escreve(we, r + 2 + i, 1 + j, v, fonte=f_azul if j == 1 else None, alin=centro if j == 1 else None)
r += 2 + len(IMP) + 1
we.cell(row=r, column=1, value="Nível de risco (probabilidade × impacto)").font = f_sec
cab(we, r + 1, ["Nível", "Pontuação", "", "Tratamento exigido pela norma"])
NR = [("Crítico", "80 a 100", "Comunicar ao Comitê de Gestão Estratégica; ações efetivas e tempestivas para "
       "evitar a materialização e avaliação dos controles."),
      ("Elevado", "40 a 79,9", "Comunicar ao responsável máximo pela unidade e à Secretaria de Gestão "
       "Estratégica; monitoramento constante e avaliação da efetividade dos controles."),
      ("Moderado", "10 a 39,9", "Atenção da gerência imediata para manter ou reduzir o risco, se a relação "
       "custo-benefício for favorável."),
      ("Baixo", "0 a 9,9", "Possíveis oportunidades; pode-se decidir assumir mais riscos após análise de "
       "custo-benefício.")]
for i, (nv, pt, tr) in enumerate(NR):
    escreve(we, r + 2 + i, 1, nv, fonte=f_neg, fill=PatternFill("solid", fgColor=NIV_COR[nv]))
    escreve(we, r + 2 + i, 2, pt, alin=centro)
    escreve(we, r + 2 + i, 3, None)
    escreve(we, r + 2 + i, 4, tr)
r += 2 + len(NR) + 1

we.cell(row=r, column=1, value="Matriz oficial (risco = probabilidade × impacto)").font = f_sec
mr = r + 1
escreve(we, mr, 6, "Impacto ↓ / Prob. →", fonte=f_neg, alin=centro)
VALS = [1, 2, 5, 8, 10]
for j, v in enumerate(VALS):
    escreve(we, mr, 7 + j, v, fonte=f_azul_neg, alin=centro)
for i, v in enumerate(reversed(VALS)):
    rr = mr + 1 + i
    escreve(we, rr, 6, v, fonte=f_azul_neg, alin=centro)
    for j in range(5):
        cl = get_column_letter(7 + j)
        escreve(we, rr, 7 + j, f"={cl}${mr}*$F{rr}", alin=centro, fmt="0")
mrng = f"G{mr + 1}:K{mr + 5}"
for lo, hi, cor in ((0, 9.99, "C6EFCE"), (10, 39.99, "FFEB9C"), (40, 79.99, "F8CBAD"), (80, 100, "FF9999")):
    we.conditional_formatting.add(mrng, CellIsRule(operator="between", formula=[str(lo), str(hi)],
                                                   fill=PatternFill("solid", fgColor=cor)))
r = mr + 7

we.cell(row=r, column=1, value="Eficácia dos controles (para o risco residual — não calculado no ANTECIPA)").font = f_sec
cab(we, r + 1, ["Nível de confiança", "Fator", "", "Descrição oficial"])
EC = [("Inexistente", 1.0, "Não há procedimentos de controle."),
      ("Insuficiente", 0.8, "Controles não formalizados e mal desenhados; operacionalização tende a ser escolha "
       "individual."),
      ("Mediano", 0.6, "Controles formalizados, mas não adequados ou suficientes."),
      ("Satisfatório", 0.4, "Controles implementados e sustentados por ferramentas adequadas, mas passíveis "
       "de aprimoramento."),
      ("Forte", 0.2, "Controles podem ser considerados “a melhor prática”, mitigando os aspectos relevantes "
       "do risco.")]
for i, (nc, fat, desc) in enumerate(EC):
    escreve(we, r + 2 + i, 1, nc, fonte=f_neg)
    escreve(we, r + 2 + i, 2, fat, fonte=f_azul, fmt="0.0", alin=centro)
    escreve(we, r + 2 + i, 3, None)
    escreve(we, r + 2 + i, 4, desc)
r += 2 + len(EC) + 1

we.cell(row=r, column=1, value="Como o ANTECIPA converte pontos em probabilidade").font = f_sec
cab(we, r + 1, ["Pontos somados", "Posição", "Nível", "Observação"])
CV = [("até 1,4", 1, "Muito baixa (1)", "Arredondamento convencional: 0,5 sobe (2,5 → 3)."),
      ("1,5 a 2,4", 2, "Baixa (2)", ""), ("2,5 a 3,4", 3, "Média (5)", ""), ("3,5 a 4,4", 4, "Alta (8)", ""),
      ("4,5 ou mais", 5, "Muito alta (10)", "")]
for i, linha in enumerate(CV):
    for j, v in enumerate(linha):
        escreve(we, r + 2 + i, 1 + j, v, alin=centro if j < 3 else None)
r += 2 + len(CV) + 1

we.cell(row=r, column=1, value="Impacto no ANTECIPA: quintis do valor global na carteira do STF").font = f_sec
cab(we, r + 1, ["Impacto", "Valor", "Contratos", "Faixa de valor global observada na carteira"])
por_imp = {}
for p in ps:
    por_imp.setdefault(p["imp"], []).append(p["valor"])
rot_imp = {1: "Muito baixo", 2: "Baixo", 3: "Médio", 4: "Alto", 5: "Muito alto"}
brl = lambda v: "R$ " + f"{v:,.0f}".replace(",", ".")
for i, k in enumerate(sorted(por_imp)):
    vs = por_imp[k]
    escreve(we, r + 2 + i, 1, rot_imp[k], fonte=f_neg)
    escreve(we, r + 2 + i, 2, E.VALOR[k], fonte=f_azul, alin=centro)
    escreve(we, r + 2 + i, 3, len(vs), alin=centro)
    escreve(we, r + 2 + i, 4, f"de {brl(min(vs))} a {brl(max(vs))}")

# ------------------------------------------------------------------ gravação
for w in wb.worksheets:
    w.sheet_view.showGridLines = False
wb.active = 0
wb.calculation.fullCalcOnLoad = True          # openpyxl não grava valores: recalcular ao abrir
wb.save(DESTINO)
print(f"planilha: {DESTINO} ({DESTINO.stat().st_size/1024:.0f} KB) · {N} contratos")
print("painel — ex-ante:", dict(conta_ex), "| observado:", dict(conta_ob))
