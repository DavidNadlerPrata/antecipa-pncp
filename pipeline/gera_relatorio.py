# -*- coding: utf-8 -*-
"""Gera o relatório ANTECIPA (Word), documento endereçado à pesquisadora e à
orientadora. Requer python-docx (pip install python-docx) e as figuras geradas
por diagrama_calibracao.py e compara_explicacoes.py.

O .docx é gravado na RAIZ da pasta unb (um nível acima de antecipa-real), de
propósito FORA do repositório git: por ser documento nominal com avaliação
crítica, não é publicado (o conteúdo técnico impessoal está em RESULTADOS.md).
"""
from pathlib import Path

import docx
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE = Path(__file__).resolve().parent.parent          # .../unb/antecipa-real
PROC = BASE / "dados" / "processados"
DESTINO = BASE.parent / "Relatorio_ANTECIPA_dados_reais.docx"  # .../unb/ (fora do repo)

AZUL = RGBColor(0x1C, 0x5C, 0xAB)
CINZA = RGBColor(0x52, 0x51, 0x4E)
PRETO = RGBColor(0x0B, 0x0B, 0x0B)
FIGURA = str(PROC / "diagrama_calibracao.png")
FIGURA2 = str(PROC / "comparacao_explicacoes.png")

doc = Document()
st = doc.styles["Normal"]
st.font.name = "Calibri"
st.font.size = Pt(10.5)
for nome, tam, cor in [("Heading 1", 15, AZUL), ("Heading 2", 12, PRETO)]:
    h = doc.styles[nome]
    h.font.name = "Calibri"
    h.font.size = Pt(tam)
    h.font.bold = True
    h.font.color.rgb = cor

def p(texto="", bold=False, italic=False, cor=None, tam=None, center=False, just=True):
    par = doc.add_paragraph()
    if center:
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif just:
        par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    run = par.add_run(texto)
    run.bold = bold
    run.italic = italic
    if cor: run.font.color.rgb = cor
    if tam: run.font.size = Pt(tam)
    return par

def rich(par, texto, bold=False, italic=False):
    run = par.add_run(texto)
    run.bold = bold
    run.italic = italic
    return run

def bullet(partes):
    par = doc.add_paragraph(style="List Bullet")
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if isinstance(partes, str):
        partes = [(partes, False)]
    for texto, bold in partes:
        r = par.add_run(texto)
        r.bold = bold
    return par

def hyperlink(par, texto, url):
    rel = par.part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK,
                             is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rel)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    c = OxmlElement("w:color"); c.set(qn("w:val"), "1c5cab"); rpr.append(c)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rpr.append(u)
    r.append(rpr)
    t = OxmlElement("w:t"); t.text = texto; r.append(t)
    h.append(r)
    par._p.append(h)

def tabela(headers, rows, larguras_cm):
    t = doc.add_table(rows=1 + len(rows), cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, htxt in enumerate(headers):
        cel = t.cell(0, j)
        cel.text = ""
        r = cel.paragraphs[0].add_run(htxt)
        r.bold = True
        r.font.size = Pt(9)
    for i, row in enumerate(rows, 1):
        for j, txt in enumerate(row):
            cel = t.cell(i, j)
            cel.text = ""
            r = cel.paragraphs[0].add_run(str(txt))
            r.font.size = Pt(9)
    for j, larg in enumerate(larguras_cm):
        for cel in t.columns[j].cells:
            cel.width = Cm(larg)
    doc.add_paragraph()
    return t

# ---------------------------------------------------------------- capa
p("RELATÓRIO TÉCNICO", bold=True, cor=CINZA, tam=11, center=True)
p("ANTECIPA — Da PoC simulada aos dados reais do PNCP e ao modelo preditivo",
  bold=True, cor=AZUL, tam=17, center=True)
p("Evolução do Produto Técnico-Tecnológico do projeto “Do Controle Reativo à Antecipação: "
  "IA para Gestão Preditiva de Riscos em Compras Públicas no STF”", italic=True, tam=11, center=True)
p("Para: Cristina Harumi Matsunaga e Profa. Dra. Marina Figueiredo Moreira (FACE/UnB)",
  cor=CINZA, tam=10, center=True)
p("Elaborado por David Nadler Prata, com apoio de IA (Claude) · versão de 18 de novembro de 2026 "
  "(1ª versão: 22 de julho de 2026)", cor=CINZA, tam=10, center=True)

# ------------------------------------------------------- nota desta versão
doc.add_heading("Nota sobre esta versão", level=1)
p("Os anexos oficiais da Resolução STF nº 781/2022 e a chave da API do Portal da Transparência, enviados "
  "pela pesquisadora, permitiram três correções e um avanço em relação à versão de julho:")
bullet([("Escala oficial da Res. 781/2022. ", True),
        ("Os anexos mostram que probabilidade e impacto têm níveis 1, 2, 5, 8 e 10, que o risco inerente "
         "vai de 0 a 100 e que as faixas são Baixo (0–9,9), Moderado (10–39,9), Elevado (40–79,9) e "
         "Crítico (80–100). A versão anterior usava uma escala 1–5 linear com faixas próprias, que "
         "divergia da norma. A escala oficial foi centralizada num único módulo do pipeline e passou a "
         "valer para o painel, para o baseline das avaliações e para este relatório.", False)])
bullet([("Carteira do STF deduplicada. ", True),
        ("Os 365 registros publicados no PNCP correspondem a 293 contratos únicos — o painel somava "
         "cópias de republicações. Os números da carteira foram recalculados.", False)])
bullet([("Sanções CEIS/CNEP integradas. ", True),
        ("Os 232 fornecedores do STF foram consultados pela API oficial; a sanção vigente na data da "
         "assinatura passou a compor o escore ex-ante (seção 4.6).", False)])
p("As correções mudam a forma do achado da seção 4.4: onde antes se lia “a matriz ex-ante não "
  "discrimina (lift 1,01×)”, lê-se agora que, na escala oficial, a matriz ex-ante não emite nenhum "
  "alerta Elevado ou Crítico. Os resultados formais do modelo supervisionado (seções 4.1 a 4.3) não "
  "mudam, pois usavam o dataset multi-órgão, já deduplicado.")

# ------------------------------------------------------- sumário executivo
doc.add_heading("Sumário executivo", level=1)
p("A Prova de Conceito do ANTECIPA, originalmente construída com dados simulados, foi evoluída em três "
  "saltos: (1) os três módulos do dashboard passaram a operar com dados reais e públicos (PNCP, "
  "compras.gov.br e dados abertos do CNPJ/Receita Federal); (2) foi coletado um dataset multi-órgão com "
  "25.488 contratos únicos de 11 órgãos do Judiciário federal, rotulado pelo desfecho real de cada "
  "contrato (aditivos, prorrogações e rescisões registrados nos termos do PNCP); e (3) foram treinados e "
  "avaliados modelos supervisionados em duas versões — a segunda com rótulo de horizonte fixo de 12 meses "
  "e probabilidades calibradas, hoje publicada no dashboard.")
p("Resultado central: o Gradient Boosting v2 atinge PR-AUC de 0,139 (6,6 vezes o acaso) e ROC-AUC de "
  "0,806 em validação temporal. No mesmo teste em que a automatização das regras da matriz de risco "
  "(baseline heurístico, na escala oficial da norma) foi avaliada, o modelo tem o dobro da precisão e "
  "captura cerca de onze vezes mais desfechos adversos. Isso sustenta "
  "empiricamente a alegação central da dissertação — o sistema é preditivo, não um mero automatizador de "
  "regras — e responde diretamente às fragilidades 2.1, 2.2 e 2.7 da análise crítica. Todo o pipeline é "
  "reprodutível em ~5 minutos no Google Colab, sem credenciais, a partir do repositório público no GitHub.")
p("Achado complementar, e possivelmente o mais contundente para a defesa (seção 4.4): na escala oficial "
  "da Res. 781/2022, alimentada apenas com dados anteriores à assinatura, a matriz de riscos não "
  "classifica nenhum dos 293 contratos do STF como Elevado ou Crítico. Relaxado o critério para "
  "“Moderado ou acima”, sua precisão fica abaixo da taxa base. Ordenados os contratos, os 50 primeiros do "
  "modelo supervisionado contêm três vezes mais desfechos adversos que os 50 primeiros da régua normativa. "
  "A automatização das regras, isoladamente, não entrega capacidade preditiva; é o aprendizado a partir "
  "dos desfechos reais que a produz.")

# ------------------------------------------------------- 1. o que foi construído
doc.add_heading("1. O que foi construído", level=1)
bullet([("Dashboard com dados reais", True),
        (" (ANTECIPA_dashboard_real.html): os três módulos do PTT — Spend Analysis, Raio-X do Fornecedor "
         "e Alertas de Risco — alimentados por APIs oficiais, preservando a identidade visual e os "
         "mecanismos de governança (human-in-the-loop) da PoC original. Arquivo autocontido: abre em "
         "qualquer navegador, sem servidor.", False)])
bullet([("Pipeline de coleta idempotente", True),
        (" em Python (somente biblioteca padrão): contratos e termos do STF e de 10 tribunais (STJ, TST, "
         "TSE, STM, CNJ, TRF2–TRF6), cadastros de 9.598 fornecedores na Receita Federal, sanções CEIS/CNEP "
         "dos 232 fornecedores do STF no Portal da Transparência, preços de referência nacionais por item de "
         "catálogo — com cache em disco, retry/backoff e passe de reparo para janelas bloqueadas por "
         "rate-limit. A chave pessoal da API do Portal fica fora do repositório.", False)])
bullet([("Dois datasets rotulados pelo desfecho real", True),
        (": v1 (25.488 contratos, rótulo sem horizonte) e v2 (16.783 contratos elegíveis, rótulo de "
         "evento adverso em até 12 meses da assinatura — correção da censura à direita).", False)])
bullet([("Modelos supervisionados com validação temporal", True),
        (" (Regressão Logística e Gradient Boosting), comparados a um baseline heurístico transparente "
         "que automatiza as escalas da Res. 781/2022; experimentos adicionais confrontando treino só-STF "
         "contra multi-órgão (com bootstrap) e duas técnicas de explicação (SHAP sobre o modelo em uso "
         "contra modelo substituto linear).", False)])
bullet([("Explicabilidade auditada por evidência", True),
        (": as explicações do painel usam SHAP sobre o próprio Gradient Boosting, escolha adotada após "
         "medir que o modelo substituto anteriormente empregado coincidia com o modelo real quanto ao "
         "fator principal em apenas 12,3% dos contratos (seção 4.5).", False)])
bullet([("Publicação e reprodutibilidade", True),
        (": repositório público no GitHub com código e caches de dados, dois notebooks para Google Colab "
         "(um monta o Google Drive; outro clona o repositório e roda sem credenciais) e script de "
         "sincronização Drive→GitHub.", False)])

# ------------------------------------------------------- 2. dados
doc.add_heading("2. Dados coletados (todos reais e públicos)", level=1)
tabela(
    ["Fonte", "Conteúdo", "Volume"],
    [
        ["API de Consulta do PNCP", "Contratos do STF e de 10 tribunais federais desde 2023 (objeto, valores, vigência, fornecedor)", "31.907 registros; 25.488 contratos únicos"],
        ["API do PNCP — termos", "Aditivos, apostilamentos e rescisões de cada contrato, com data e valores", "Milhares de termos; base do rótulo"],
        ["API de busca do PNCP", "Presença nacional (todos os órgãos) dos maiores fornecedores do STF", "Top-15 da carteira STF"],
        ["Dados abertos do CNPJ (Receita Federal, via minhareceita.org)", "Capital social, porte, idade, CNAE, situação cadastral, natureza jurídica", "9.598 de 9.600 fornecedores únicos"],
        ["Portal da Transparência — CEIS e CNEP (API oficial)", "Sanções de empresas: inidoneidade, impedimento, suspensão, Lei Anticorrupção", "232 fornecedores do STF; 19 com registro"],
        ["Pesquisa de preços do compras.gov.br + catálogo de PDMs", "Distribuição nacional de preços homologados por item (Módulo 1)", "7 itens com amostra nacional"],
    ],
    [4.5, 8.0, 4.0])
p("Recorte temporal: vigência plena da Lei 14.133/2021 (2023 em diante), conforme decisão metodológica "
  "do projeto. No STF: 293 contratos únicos (365 registros no PNCP, por causa de republicações), R$ 996 "
  "milhões em valor global, 179 termos aditivos e 16 rescisões/extinções — 62 contratos (21,2%) com "
  "algum desfecho adverso observável.")

# ------------------------------------------------------- 3. metodologia
doc.add_heading("3. Rotulagem pelo desfecho real e modelagem", level=1)
doc.add_heading("3.1 Rótulo (resposta à fragilidade 2.1 — circularidade)", level=2)
p("Em vez de rotular pelos escores da própria matriz de risco (o que faria o modelo apenas reproduzir as "
  "regras), cada contrato é rotulado pelo que de fato aconteceu depois da assinatura, extraído dos termos "
  "publicados no PNCP: rescisão/extinção registrada, acréscimo de valor superior a 25% ou prorrogação "
  "superior a 365 dias.")
p("Na v2, o rótulo ganhou horizonte fixo: evento adverso em até 12 meses da assinatura (datado pelo "
  "termo), e só entram no dataset contratos com 12 meses completos de observação. Essa correção eliminou "
  "um artefato importante: na v1, a prevalência “caía” de 5,2% no treino para 1,6% no teste não por "
  "melhora real, mas porque contratos recentes ainda não tiveram tempo de acumular termos (censura à "
  "direita). Com o horizonte fixo, a prevalência fica estável por coorte de assinatura: 1,5% (2023), "
  "1,7% (2024) e 2,1% (2025).")
doc.add_heading("3.2 Features (somente informação disponível na assinatura)", level=2)
p("Valor global, duração prevista, categoria do processo, órgão, capital social, idade do CNPJ, porte, "
  "opção pelo Simples, situação cadastral, natureza de consórcio, razão capital/valor e recorrência do "
  "fornecedor. Nenhuma variável posterior à assinatura entra como feature — o desfecho é usado apenas "
  "como rótulo.")
doc.add_heading("3.3 Protocolo de avaliação (resposta à fragilidade 2.7)", level=2)
p("Validação temporal (treino 2023–2024, teste 2025; contratos de 2026 excluídos da avaliação na v1 por "
  "rótulo imaturo), métricas para classe rara — precision, recall e F1 da classe positiva, PR-AUC e "
  "ROC-AUC; nunca acurácia. Limiar de decisão escolhido no treino (máximo F1 em validação cruzada), "
  "jamais no teste. Baseline heurístico avaliado nas mesmas condições, com alerta definido como Elevado "
  "ou Crítico na escala oficial da Res. 781/2022 (risco inerente igual ou superior a 40).")

doc.add_heading("3.4 As três leituras de risco e como cada uma é calculada", level=2)
p("Escala oficial da Res. 781/2022. ", bold=True)
p("Conforme os anexos da norma, probabilidade e impacto têm cinco níveis, com valores 1, 2, 5, 8 e 10 "
  "(Muito baixa/o, Baixa/o, Média/o, Alta/o, Muito alta/o), acompanhados de descritores qualitativos — "
  "da probabilidade “Rara” à “Praticamente certa”, do impacto “Insignificante” ao “Catastrófico”. O risco "
  "inerente é o produto dos dois valores, de 0 a 100, classificado em Baixo (0–9,9), Moderado (10–39,9), "
  "Elevado (40–79,9) e Crítico (80–100). A norma define ainda o risco residual, igual ao inerente "
  "multiplicado por um fator de eficácia dos controles (de 1,0, controle inexistente, a 0,2, controle "
  "forte). Como dados públicos não informam a eficácia dos controles internos, o painel calcula apenas o "
  "risco inerente.")
p("O painel apresenta cada contrato sob três leituras distintas, que respondem a perguntas diferentes e "
  "não devem ser confundidas. Duas delas são ex-ante (usam apenas o que se sabia no dia da assinatura) e "
  "uma é retrospectiva. A distinção é essencial para interpretar corretamente os resultados da seção 4.")

p("(a) Nível ex-ante — Res. 781/2022. ", bold=True)
p("Escore heurístico transparente que parte de 1,0 ponto de probabilidade e soma apenas fatores "
  "conhecidos na assinatura:")
bullet("capital social inferior a 2% do volume contratado nacional: +1,2; superior a 30%: −0,5; "
       "não informado na base aberta (comum em consórcios): +0,3")
bullet("CNPJ com menos de 3 anos: +0,8; com mais de 10 anos: −0,4")
bullet("crescimento contratual atípico (3 ou mais vezes a mediana histórica no PNCP): +1,0")
bullet("situação cadastral na Receita diferente de “Ativa”: +1,5")
bullet("vigência prevista superior a 12 meses (serviço continuado): +0,4")
bullet("sanção no CEIS ou no CNEP em vigor e já publicada na data da assinatura — portanto consultável "
       "antes de contratar: +2,0")
p("O total é arredondado e limitado a 1–5, posição que indica o nível de probabilidade da norma: Muito "
  "baixa (1), Baixa (2), Média (5), Alta (8) ou Muito alta (10).")

p("(b) Probabilidade prevista na assinatura — modelo supervisionado. ", bold=True)
p("Gradient Boosting com calibração isotônica (5 folds), de modo que a porcentagem exibida corresponde a "
  "frequência observada, e não a um escore arbitrário:")
bullet("treino: 16.783 contratos de 11 órgãos do Judiciário federal (2022–2025), todos com 12 meses "
       "completos de observação")
bullet("rótulo: desfecho adverso em até 12 meses da assinatura — rescisão/extinção, acréscimo de valor "
       "superior a 25% ou prorrogação superior a 365 dias")
bullet("variáveis: apenas as disponíveis na assinatura — valor global, duração, categoria, órgão, capital "
       "social, idade e porte do fornecedor, situação cadastral, razão capital/valor e recorrência no PNCP")
bullet("na matriz de riscos, a probabilidade contínua é convertida para os níveis da norma por faixas "
       "fixas — Muito baixa (1): abaixo de 2%; Baixa (2): de 2 a 5%; Média (5): de 5 a 10%; Alta (8): de "
       "10 a 20%; Muito alta (10): 20% ou mais —, ancoradas na taxa base e não em quantis, para "
       "permanecerem comparáveis entre períodos e órgãos. A correspondência com os descritores "
       "qualitativos é provisória: 20% já é mais de onze vezes a taxa base, mas está longe de "
       "“praticamente certa”")
p("A explicação por contrato utiliza valores SHAP (TreeExplainer) calculados sobre o próprio Gradient "
  "Boosting — o modelo que gera a probabilidade —, em escala de log-odds. As contribuições de variáveis "
  "categóricas são somadas por variável original, de modo que não sejam exibidas atribuições a níveis "
  "que o contrato não assume. A seção 4.5 documenta a evidência que motivou essa escolha.")

p("(c) Nível observado — Res. 781/2022. ", bold=True)
p("O mesmo escore da leitura (a), acrescido do que já ocorreu com o contrato após a assinatura:")
bullet("dois ou mais termos aditivos firmados: +0,8")
bullet("valor acumulado mais de 10% acima do inicial: +0,8")
bullet("termo de rescisão/extinção registrado: +1,5")
p("Trata-se, portanto, de leitura retrospectiva: parte do que ela mede já é o próprio problema "
  "materializado, e não uma previsão. É a razão pela qual um contrato pode figurar como “Crítico” nesta "
  "leitura e apresentar probabilidade modesta nas leituras ex-ante.")

p("Elementos comuns e ressalva. ", bold=True)
p("Nas três leituras, o impacto é o quintil do valor global do contrato dentro da carteira do STF, "
  "mapeado nos cinco níveis da norma (Muito baixo, valor 1, a Muito alto, valor 10), e o nível de risco "
  "resulta do produto probabilidade × impacto nas faixas oficiais. Compartilhar o mesmo eixo de impacto "
  "torna as leituras diretamente comparáveis. Registre-se, contudo, que a norma traz apenas descritores "
  "qualitativos, sem regras de conversão de dados em níveis: a tabela de pontos acima é operacionalização "
  "própria, em validação com os gestores de risco do STF (seção 7). E o escore ex-ante é uma reconstrução "
  "realizada no presente: utiliza os dados cadastrais atuais da Receita Federal, que podem ter se alterado "
  "desde a data de assinatura; a versão rigorosa exigiria séries históricas de dados cadastrais, não "
  "disponíveis na base aberta.")

# ------------------------------------------------------- 4. resultados
doc.add_heading("4. Resultados", level=1)
doc.add_heading("4.1 Modelo principal (teste temporal 2025)", level=2)
tabela(
    ["Modelo", "Precision", "Recall", "F1", "PR-AUC", "ROC-AUC"],
    [
        ["Gradient Boosting v2 (12 meses)", "0,109", "0,494", "0,179", "0,139 (lift 6,6×)", "0,806"],
        ["Regressão Logística v2", "0,052", "0,647", "0,096", "0,065", "0,755"],
        ["Gradient Boosting v1", "0,064", "0,393", "0,111", "0,071 (lift 4,4×)", "0,798"],
        ["Baseline heurístico (Res. 781, escala oficial)", "0,032", "0,036", "0,034", "0,031 (lift ~1,9×)", "0,701"],
    ],
    [5.2, 2.2, 2.0, 1.8, 3.2, 2.1])
p("Leitura: o modelo aprende sinal real que as regras não capturam. O baseline foi avaliado no mesmo "
  "teste e com o mesmo rótulo do Gradient Boosting v1; contra ele, o modelo tem o dobro da precisão (0,064 "
  "contra 0,032) e encontra cerca de onze vezes mais desfechos adversos (recall de 0,393 contra 0,036) — "
  "na escala oficial, a régua normativa emite 154 alertas e acerta 5 dos 140 casos. A v2 domina a v1 em "
  "todas as métricas "
  "relevantes (a comparação correta entre versões é pelo lift sobre o acaso, pois testes e rótulos "
  "diferem). Em visão operacional de fila de diligência: entre os 100 contratos de 2025 com maior escore "
  "v2, 16 tiveram desfecho adverso real em 12 meses — 7,6 vezes a taxa base — capturando 19% de todos os "
  "adversos do ano.")
doc.add_heading("4.2 Experimento: treinar só com STF × multi-órgão (fragilidade 2.2)", level=2)
p("Ambos avaliados no mesmo teste (contratos do STF assinados em 2025: 106 contratos, 13 adversos). O "
  "modelo só-STF (148 contratos de treino) obteve PR-AUC 0,384; o multi-órgão (12.483 contratos), 0,319. "
  "O bootstrap (4.000 reamostras) mostra que a diferença não é conclusiva: Δ = +0,069 com IC95% "
  "[−0,221; +0,350]. Interpretação equilibrada: o padrão local do STF carrega sinal específico relevante "
  "(sua carteira tem prevalência de desfecho adverso muito superior à dos demais órgãos), mas o modelo "
  "multi-órgão entrega desempenho comparável com 84 vezes mais dados e muito mais estabilidade. "
  "Recomendação com nuance empírica própria: treinar no padrão nacional e calibrar/afinar por órgão.")
doc.add_heading("4.3 Calibração (o que o dashboard exibe)", level=2)
p("O treino com pesos de classe (class_weight='balanced') instrui o modelo a tratar as classes como se "
  "fossem equilibradas, quando na realidade apenas 1,8% dos contratos têm desfecho adverso. Isso melhora "
  "o aprendizado em classe rara, mas distorce a saída: o número produzido é um escore inflado, não uma "
  "probabilidade. Para corrigir, aplica-se calibração isotônica — uma regressão monotônica não "
  "decrescente que aprende, a partir dos próprios dados, o mapeamento entre escore e frequência "
  "efetivamente observada, sem impor formato de curva. O ajuste é feito por validação cruzada em 5 "
  "partições, de modo que a calibração não utilize as mesmas observações do treino.")
p("A tabela e a figura abaixo, medidas no conjunto de teste temporal (contratos assinados em 2025, nunca "
  "vistos no treino), demonstram o efeito:")
tabela(
    ["Métrica", "Sem calibração", "Calibrado (isotônica)", "Referência"],
    [
        ["Brier score (menor é melhor)", "0,1280", "0,0196", "—"],
        ["ECE — erro de calibração esperado", "0,2240", "0,0063", "0 (ideal)"],
        ["Probabilidade média prevista", "24,5%", "2,0%", "2,1% (frequência real)"],
        ["ROC-AUC (discriminação)", "0,8064", "0,8019", "—"],
    ],
    [5.6, 3.2, 3.9, 3.8])
p("Três leituras desta tabela merecem destaque. Primeiro, o modelo não calibrado prevê em média 24,5% "
  "quando a frequência real é 2,1% — superestimativa de aproximadamente doze vezes, que produziria "
  "alarmes falsos sistemáticos se exibida ao servidor. Segundo, após a calibração a média passa a 2,0%, "
  "praticamente idêntica à frequência observada, e o erro de calibração (ECE) cai de 0,224 para 0,006 — "
  "redução de trinta e seis vezes. Terceiro, e decisivo para a validade do procedimento, o ROC-AUC "
  "permanece essencialmente inalterado (0,8064 contra 0,8019): como a transformação é monotônica, a "
  "ordenação dos contratos é preservada. A calibração não melhora nem piora a capacidade de discriminar; "
  "ela apenas torna a escala interpretável — que é precisamente o que se pretende ao exibir uma "
  "porcentagem a quem decide.")
try:
    doc.add_picture(str(FIGURA), width=Cm(16.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p("Figura 1 — Diagrama de confiabilidade no teste temporal de 2025. Em (a), escala completa: a curva "
      "sem calibração (vermelha) afasta-se drasticamente da diagonal, chegando a prever 80% onde a "
      "frequência real é 10%. Em (b), zoom na faixa efetivamente ocupada pelo modelo calibrado (azul), "
      "que acompanha a diagonal de perto. Em (c), a distribuição das probabilidades evidencia o "
      "deslocamento: o modelo bruto espalha contratos por toda a escala, enquanto o calibrado os "
      "concentra próximo à prevalência real.", italic=True, cor=CINZA, tam=9)
except Exception as e:  # figura ainda não gerada
    p(f"[Figura do diagrama de confiabilidade não incorporada: {e}]", italic=True, cor=CINZA, tam=9)
p("As explicações por contrato usam valores SHAP calculados sobre o próprio Gradient Boosting, "
  "apresentados explicitamente como insumo para a motivação humana, e não como a motivação em si "
  "(fragilidade 2.8). A seção seguinte documenta a evidência que levou a substituir a abordagem "
  "anteriormente adotada.")

doc.add_heading("4.4 Aplicação à carteira do STF: na escala oficial, a matriz ex-ante não emite alerta",
                level=2)
p("Aplicando os critérios de alerta aos 293 contratos únicos do STF publicados no PNCP (taxa base de "
  "desfecho adverso: 21,2%), obtém-se o resultado abaixo. O escore ex-ante é o mesmo escore heurístico "
  "da Res. 781/2022, na escala oficial da norma, porém calculado apenas com os fatores conhecidos no dia "
  "da assinatura — a leitura que o sistema teria exibido ao gestor antes de contratar.")
tabela(
    ["Critério de alerta", "Alertas", "Acertos", "Precisão", "Recall", "Lift"],
    [
        ["Ex-ante (Res. 781) — Elevado/Crítico", "0", "0", "—", "0,0%", "—"],
        ["Ex-ante (Res. 781) — Moderado ou acima", "158", "32", "20,2%", "51,6%", "0,96×"],
        ["Ex-ante top-50 (ordenado pelo escore)", "50", "9", "18,0%", "14,5%", "0,85×"],
        ["ML top-50 (probabilidade)", "50", "27", "54,0%", "43,5%", "2,55×"],
        ["Ex-ante top-100", "100", "19", "19,0%", "30,6%", "0,90×"],
        ["ML top-100", "100", "49", "49,0%", "79,0%", "2,32×"],
        ["ML ≥ 20%", "82", "45", "54,9%", "72,6%", "2,59×"],
        ["ML ≥ 10%", "128", "51", "39,8%", "82,3%", "1,88×"],
        ["(referência, circular) Observado — Elevado/Crítico", "20", "17", "85,0%", "27,4%", "4,02×"],
    ],
    [6.4, 1.7, 1.7, 1.7, 1.6, 1.6])
p("O achado central: na escala oficial, a leitura ex-ante não classifica nenhum contrato como Elevado ou "
  "Crítico. Com os fatores disponíveis antes da assinatura, a probabilidade ex-ante de todos os 293 "
  "contratos fica em Muito baixa (1) ou Baixa (2); mesmo com impacto máximo (10), o risco inerente chega "
  "no máximo a 20 — Moderado. Na matriz de riscos ex-ante do painel, todos os contratos ocupam apenas as "
  "duas primeiras colunas de probabilidade. Relaxando o critério para “Moderado ou acima”, a precisão "
  "(20,2%) fica abaixo da própria taxa base. E, ordenados os contratos pelo escore contínuo, os 50 "
  "primeiros da régua normativa contêm 9 desfechos adversos, contra 27 entre os 50 primeiros do modelo — "
  "três vezes mais, no mesmo custo operacional.")
p("Ressalvas indispensáveis para a leitura correta desta tabela:", bold=True)
bullet([("Viés in-sample nos números do ML. ", True),
        ("Os contratos do STF integraram o treino do modelo calibrado (2022–2025, 11 órgãos), de modo "
         "que os valores acima são otimistas. A medição fora da amostra é a da seção 4.1: precisão de "
         "10,9% e recall de 49,4% no teste temporal de 2025 — nominalmente menor, mas sobre prevalência "
         "de 2,1%, o que corresponde a lift de aproximadamente 5×.", False)])
bullet([("Rótulo mais frouxo. ", True),
        ("Esta tabela usa o rótulo do dashboard (“teve desfecho adverso a qualquer momento”), não o de "
         "horizonte de 12 meses da avaliação formal. Rótulo mais comum eleva a precisão nominal e "
         "dificulta a discriminação fina — por isso a coluna comparável entre contextos é o lift, não a "
         "precisão absoluta.", False)])
bullet([("Por que a heurística falha justamente no STF. ", True),
        ("A carteira do Tribunal é homogeneamente de alto risco pelos critérios da norma: quase tudo é "
         "serviço continuado, longo e de valor elevado. As variáveis que a heurística usa para "
         "discriminar (quantil de valor, vigência superior a 12 meses) estão saturadas — se todos "
         "pontuam, ninguém se destaca.", False)])
bullet([("O “zero alertas” depende da tabela de pontos. ", True),
        ("O resultado combina a escala oficial com a operacionalização própria da seção 3.4, que "
         "concentra a probabilidade ex-ante em 1 e 2 porque os fatores disponíveis antes da assinatura são "
         "poucos e de peso moderado. Se a validação com os gestores do STF elevar os pesos, o número de "
         "alertas mudará — o que torna essa validação parte do resultado, e não mero detalhe.", False)])
bullet([("A leitura observada é circular. ", True),
        ("Sua precisão de 85% decorre de usar o próprio desfecho que pretende sinalizar; aparece na tabela "
         "apenas como referência.", False)])
p("Este é, na avaliação técnica deste relatório, o resultado mais forte do trabalho para a defesa: "
  "operacionalizar a matriz da Res. 781/2022 com dados anteriores à assinatura não produz capacidade "
  "preditiva na carteira do STF — e é precisamente essa lacuna que o modelo supervisionado preenche. "
  "Reforça-se, porém, a contrapartida operacional: 80 a 130 alertas numa carteira de 293 contratos "
  "excedem a capacidade de diligência de qualquer equipe, o que sustenta o uso do modelo como fila de "
  "priorização (top-N por probabilidade) em vez de alerta binário.")
p("Probabilidade pura × matriz: réguas para perguntas diferentes. ", bold=True)
p("A matriz de riscos do modelo (probabilidade convertida nos níveis da norma e multiplicada pelo "
  "impacto) e o ranqueamento pela probabilidade pura não são versões melhor e pior do mesmo instrumento — "
  "otimizam objetivos distintos. Avaliadas por precisão sobre “deu errado”, no mesmo conjunto:")
tabela(
    ["Critério", "Alertas", "Acertos", "Precisão", "Recall", "Lift"],
    [
        ["Matriz ML — Elevado/Crítico", "91", "29", "31,9%", "46,8%", "1,51×"],
        ["Matriz ML — só Crítico", "40", "18", "45,0%", "29,0%", "2,13×"],
        ["ML ≥ 20% (probabilidade pura, volume ~igual)", "82", "45", "54,9%", "72,6%", "2,59×"],
        ["ML top-50 (probabilidade pura)", "50", "27", "54,0%", "43,5%", "2,55×"],
    ],
    [6.4, 1.7, 1.7, 1.7, 1.6, 1.6])
p("Em volume semelhante de alertas (91 e 82), a probabilidade pura é mais precisa que a matriz (54,9% "
  "contra 31,9%): "
  "multiplicar pelo impacto dilui o sinal preditivo, porque o eixo de impacto — o quantil do valor do "
  "contrato — mede a consequência de um problema, não a sua probabilidade. Isso não é defeito da matriz: "
  "ela otimiza perda esperada, não taxa de acerto. Um contrato com 10% de chance de problema em R$ 500 "
  "milhões merece mais atenção que um com 25% em R$ 50 mil, e é exatamente essa priorização que a "
  "ponderação por impacto captura, ao custo de errar mais em quantidade.")
p("A implicação metodológica é usar a régua conforme a pergunta. Para “quais contratos vão dar "
  "problema?”, ordena-se pela probabilidade pura. Para “onde alocar a diligência considerando o estrago "
  "potencial?”, usa-se a matriz. Avaliar a matriz por precisão sobre o desfecho é, em rigor, medi-la por "
  "um objetivo que não é o dela — daí a coexistência das três leituras no painel, cada uma respondendo a "
  "uma pergunta distinta.")

doc.add_heading("4.5 Escolha da técnica de explicação: SHAP × modelo substituto", level=2)
p("A primeira versão do painel exibia, como explicação de cada contrato, as contribuições aditivas de uma "
  "regressão logística treinada sobre os mesmos dados. A escolha era pragmática — a regressão logística é "
  "aditiva por construção, o que produz explicação exata e auditável sem bibliotecas adicionais —, mas "
  "envolvia uma fragilidade conceitual: a logística é um modelo substituto, que explica a si mesmo e não "
  "o Gradient Boosting do qual provém a probabilidade exibida.")
p("Para decidir com evidência, e não por preferência teórica, as duas formas de explicação foram "
  "calculadas para os mesmos contratos do STF e no mesmo espaço de variáveis (ambos os modelos ajustados "
  "sobre a matriz pré-processada idêntica). Os resultados são desfavoráveis ao modelo substituto:")
tabela(
    ["Indicador de concordância entre as duas explicações", "Valor"],
    [
        ["Correlação de Spearman média entre as atribuições", "0,222"],
        ["Contratos em que o fator principal coincide", "12,3%"],
        ["Sobreposição média entre os três principais fatores", "56,3%"],
        ["Contratos analisados", "293"],
    ],
    [10.5, 4.5])
p("Em outras palavras, em aproximadamente nove de cada dez contratos o fator apresentado como principal "
  "não era o principal do modelo que produziu a porcentagem. A inspeção das atribuições revelou a causa "
  "estrutural: em variáveis codificadas por indicadores binários (one-hot), a contribuição da regressão "
  "logística é o coeficiente multiplicado por um — isto é, uma constante idêntica para todos os contratos "
  "do mesmo órgão. O indicador “órgão: STF” aparecia assim como fator principal em praticamente todos os "
  "casos, com magnitude fixa, dominando a explicação sem discriminar coisa alguma entre contratos. A "
  "importância global confirma a inversão: a variável de maior peso no Gradient Boosting (duração do "
  "contrato, com contribuição média absoluta de 1,521) tinha peso quase dez vezes menor na regressão "
  "logística (0,156), enquanto “órgão: STF” liderava nesta última (3,024) contra 0,810 no modelo real.")
try:
    doc.add_picture(str(FIGURA2), width=Cm(16.5))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p("Figura 2 — A mesma predição explicada de duas formas, para três contratos do STF. À esquerda, SHAP "
      "sobre o Gradient Boosting; à direita, contribuições da regressão logística. Note-se que “órgão: "
      "STF” figura como fator principal da logística nos três casos, com magnitude idêntica (+3,02), "
      "inclusive no contrato de menor risco — onde o SHAP indica que o fator dominante é o número de "
      "contratos do fornecedor, reduzindo o risco. A explicação substituta chegava a contradizer a "
      "direção do raciocínio do modelo.", italic=True, cor=CINZA, tam=9)
except Exception as e:
    p(f"[Figura da comparação de explicações não incorporada: {e}]", italic=True, cor=CINZA, tam=9)
p("Diante desse resultado, as explicações do painel foram migradas para valores SHAP (TreeExplainer) "
  "calculados sobre o próprio Gradient Boosting, atendendo ao que o projeto de qualificação já previa. "
  "Duas providências acompanharam a migração. Primeiro, as contribuições dos níveis de cada variável "
  "categórica passaram a ser somadas por variável original: sem isso, o SHAP atribuía valor a níveis que "
  "o contrato não assume (por exemplo, “órgão: TSE” em contrato do STF, medindo a contribuição de não ser "
  "do TSE), o que é tecnicamente correto mas incompreensível para o usuário. Segundo, mede-se e reporta-se "
  "a fidelidade da explicação ao modelo publicado.")
p("Ressalva de fidelidade. ", bold=True)
p("O SHAP explica o Gradient Boosting ajustado sobre toda a base de treino, ao passo que a probabilidade "
  "exibida provém do mesmo algoritmo calibrado em cinco partições. A concordância de ordenação entre os "
  "dois é de 0,878 (Spearman) — muito superior aos 0,222 do modelo substituto, porém inferior à unidade. "
  "Parte dessa diferença é artefato de empates, e não discordância efetiva: a calibração isotônica é "
  "função em degraus e reduz os 293 contratos do STF a apenas 111 valores distintos de probabilidade, o "
  "que penaliza o coeficiente de Spearman sem que haja divergência real de ordenação.")
p("O indicador é recalculado a cada publicação do modelo e registrado no arquivo de predições para fins "
  "de auditoria. Além disso, o próprio painel exibe a ressalva no bloco “Como as três leituras são "
  "calculadas”, de modo que quem consulta o dashboard conhece o limite da explicação sem depender desta "
  "documentação — coerente com a orientação de que a explicabilidade deve estar disponível a quem decide, "
  "e não apenas ao corpo técnico.")
p("Eliminar por completo o resíduo seria possível calibrando com conjunto reservado (parâmetro "
  "cv=\"prefit\"): haveria então um único modelo, e o SHAP explicaria exatamente o escore que alimenta a "
  "calibração. O custo seria retirar observações do ajuste do modelo, num conjunto que dispõe de apenas "
  "296 casos positivos. A configuração adotada privilegia a qualidade da calibração (ECE de 0,006, "
  "seção 4.3) e assume um resíduo de fidelidade que é medido e divulgado, em vez de ignorado. Trata-se "
  "de escolha entre duas propriedades desejáveis, com o critério explicitado.")
p("Registre-se, por fim, que a alternativa oposta permanece defensável e merece discussão na dissertação: "
  "publicar a própria regressão logística como modelo, abrindo mão de aproximadamente metade do poder "
  "preditivo (PR-AUC de 0,065 contra 0,139) em troca de um sistema em que a explicação é o modelo, sem "
  "substituto nem aproximação. Em contexto de Direito Administrativo, no qual o princípio da motivação "
  "pode pesar mais que pontos de acurácia, essa troca é argumentável. O que não se sustenta é a "
  "combinação anteriormente adotada — modelo de árvores explicado por modelo linear distinto.")

doc.add_heading("4.6 Sanções CEIS/CNEP dos fornecedores do STF", level=2)
p("Com a chave da API do Portal da Transparência, os 232 fornecedores pessoa jurídica da carteira do STF "
  "foram consultados no CEIS (Cadastro de Empresas Inidôneas e Suspensas) e no CNEP (Cadastro Nacional de "
  "Empresas Punidas), em 18 de novembro de 2026. Dezenove fornecedores (8,2%) têm registro — todos no "
  "CEIS, nenhum no CNEP. Um único fornecedor concentra quase trinta sanções, entre elas uma declaração de "
  "inidoneidade pelo TCU e duas sanções aplicadas pelo próprio STF.")
bullet([("O fator ex-ante de sanção não disparou em nenhum contrato. ", True),
        ("Nenhum fornecedor tinha sanção em vigor e já publicada na data da assinatura: todas as 66 "
         "combinações contrato–sanção referem-se a sanções iniciadas depois. É o resultado esperado, pois "
         "a Lei 14.133/2021 (art. 91, § 4º) obriga a consultar CEIS e CNEP antes de formalizar o "
         "contrato — o controle prévio funcionou na carteira examinada.", False)])
bullet([("Vinte e três contratos têm fornecedor sancionado posteriormente ", True),
        ("(oito dessas combinações por sanção do próprio STF). O painel exibe essa informação no "
         "detalhamento de cada contrato, separada do escore ex-ante, já que não era conhecida na "
         "assinatura.", False)])
bullet([("Verificação exploratória com resultado nulo. ", True),
        ("Testou-se se a sanção posterior, sinal independente do rótulo, validaria o modelo. Não validou: "
         "esses 23 contratos tiveram desfecho adverso de 13,0%, contra 21,9% dos demais (teste exato de "
         "Fisher, p = 0,43), e probabilidade mediana prevista de 9,9%, contra 7,5% (Mann-Whitney "
         "unilateral, p = 0,12). Com apenas 23 casos o teste tem pouco poder, e as sanções refletem "
         "condutas perante outros órgãos, enquanto o rótulo mede aditivos e prorrogações do próprio "
         "contrato. Registra-se o resultado nulo, sem forçar interpretação.", False)])
p("A chave da API é pessoal e não integra o repositório público: o script de coleta a lê de uma variável "
  "de ambiente ou de um arquivo fora da pasta do projeto e, na ausência dela, usa o cache já coletado.",
  italic=True, cor=CINZA, tam=9.5)

# ------------------------------------------------------- 5. achados
doc.add_heading("5. Achados de engenharia de dados (material para a dissertação)", level=1)
bullet([("O STF não preenche o código CATMAT/CATSER", True),
        (" nos itens que publica no PNCP: 0 de 916 itens tinham o campo. A comparação nacional de preços "
         "do Módulo 1 exigiu reconstruir a ponte descrição → PDM → códigos de item via catálogo do "
         "compras.gov.br. Confirma na prática o item 2.4 da análise crítica: a maior parte do esforço é "
         "engenharia e limpeza de dados.", False)])
bullet([("As listas paginadas do PNCP contêm duplicatas", True),
        (" (republicações/retificações): o TST retorna 13.765 registros para 9.407 contratos únicos, e o "
         "próprio STF, 365 registros para 293 contratos. Deduplicação por numeroControlePncp é obrigatória "
         "em qualquer uso analítico do PNCP — inclusive no painel, que até a versão de julho somava as "
         "cópias.", False)])
bullet([("CNPJs raiz agregam unidades", True),
        (": TST e TSE, pelo CNPJ raiz, trazem as unidades regionais da Justiça do Trabalho e Eleitoral — "
         "útil para volume, mas exige atenção ao interpretar “órgão”.", False)])
bullet([("Serviços continuados são publicados como item único de valor global", True),
        (" (quantidade 1), o que inviabiliza comparação unitária de preços de serviços sem normalização "
         "adicional (postos, m² etc.).", False)])
bullet([("Consórcios aparecem com capital social zero", True),
        (" na base aberta da Receita — é dado não informado, não “empresa sem lastro”; o escore trata o "
         "caso separadamente para não gerar falso alerta.", False)])
bullet([("A API do PNCP aplica rate-limit", True),
        (" (HTTP 429) em coletas longas; o pipeline usa retry com backoff e um passe de reparo. Pequenas "
         "lacunas residuais estão documentadas no repositório.", False)])
bullet([("A API do Portal da Transparência exige chave pessoal", True),
        (" e limita as requisições (cerca de 90 por minuto em horário diurno); datas vêm no formato "
         "dd/mm/aaaa e o fim de uma sanção pode ser indeterminado. Para distinguir o que era consultável "
         "antes de contratar, usa-se a data de publicação da sanção, não apenas a de início.", False)])

# ------------------------------------------------------- 6. análise crítica
doc.add_heading("6. Correspondência com a análise crítica", level=1)
tabela(
    ["Recomendação", "Status"],
    [
        ["1. Rotular pelo desfecho real, não pela matriz", "Implementada (v1 e v2; horizonte de 12 meses na v2)"],
        ["2. Treinar multi-órgão e aplicar ao STF", "Implementada + experimento próprio com bootstrap (seção 4.2)"],
        ["3. APIs oficiais em vez de raspagem", "Implementada, incluindo CEIS/CNEP via API do Portal da Transparência (seção 4.6); SICAF e CNDT pendentes de acesso institucional"],
        ["4. Dimensionar limpeza/normalização CATMAT", "Confirmada na prática; ponte descrição→PDM construída para 7 itens"],
        ["5. Normativo: alerta dispara diligência, nunca inabilitação", "Institucional — reforçada nos textos do dashboard e relatórios"],
        ["6. Monitorar concordância humano-máquina", "Pendente (exige uso real com servidores)"],
        ["7. Precision/recall/F1 + calibração em vez de acurácia", "Implementada (validação temporal, PR-AUC, calibração isotônica)"],
        ["8. SHAP como insumo da motivação, não a motivação", "Implementada: SHAP sobre o modelo publicado (seção 4.5), apresentado como insumo"],
        ["9. Explicitar arquitetura batch vs. tempo real", "Explicitada: pipeline batch regenerável; dashboard autocontido"],
        ["10. Dono institucional e sustentação", "Pendente (decisão institucional)"],
    ],
    [8.2, 8.3])

# ------------------------------------------------------- 7. nota 781
doc.add_heading("7. Nota importante: operacionalização da Res. 781/2022", level=1)
p("Os anexos da Resolução — escalas de probabilidade, de impacto, de nível de risco e de eficácia dos "
  "controles, além dos modelos de lista de eventos, diagrama bow-tie e plano de tratamento — foram "
  "incorporados nesta versão, e a escala oficial substituiu a régua linear usada antes. Os anexos "
  "confirmam, porém, que a norma traz apenas descritores qualitativos e não define como converter dados "
  "observáveis em níveis. A tabela de pesos usada no escore heurístico (por exemplo, capital/volume "
  "abaixo de 2% → +1,2; empresa com menos de 3 anos → +0,8; sanção vigente na assinatura → +2,0) "
  "permanece, portanto, uma operacionalização proposta neste trabalho — plausível, porém arbitrária.")
p("A validação desse quadro com os gestores de risco do STF, já em curso, é decisiva por dois motivos. "
  "Primeiro, legitima o escore perante a instituição. Segundo, condiciona diretamente o achado da seção "
  "4.4: o “zero alertas ex-ante” depende dos pesos. Sugere-se documentar na dissertação, para cada fator, "
  "o descritor da norma que ele pretende sustentar, o proxy de dados usado, o peso e a justificativa "
  "validada. O mesmo vale para a correspondência entre as faixas de probabilidade do modelo e os "
  "descritores qualitativos (“Rara” … “Praticamente certa”). Importante: o resultado central (modelo "
  "supervisionado) não depende dessa tabela — o rótulo vem do desfecho real, justamente para escapar da "
  "circularidade.")

# ------------------------------------------------------- 8. limitações
doc.add_heading("8. Limitações honestas", level=1)
bullet("O rótulo captura desfechos administráveis (aditivos, prorrogações, rescisões) — não fraude ou "
       "conluio, raros e não observáveis nestas bases.")
bullet("O horizonte de 12 meses não captura desfechos tardios (ex.: aditivos do 2º ano em serviços "
       "continuados); análise de sensibilidade com 18/24 meses é extensão natural.")
bullet("A feature de recorrência do fornecedor é contada no dataset completo (leve vazamento temporal; "
       "em produção, contar apenas contratos anteriores à assinatura).")
bullet("A precisão absoluta dos alertas é baixa (classe rara) — o uso correto é ranqueamento com fila "
       "por capacidade de diligência, e a decisão é sempre humana.")
bullet("Comparações de preço por PDM agregam especificações heterogêneas: desvios disparam diligência, "
       "nunca conclusão de sobrepreço.")
bullet("As explicações SHAP descrevem o Gradient Boosting ajustado sobre toda a base, enquanto a "
       "probabilidade exibida provém do mesmo algoritmo calibrado em cinco partições — concordância de "
       "ordenação de 0,878 (Spearman), parcialmente reduzida por empates da calibração (seção 4.5).")
bullet("O painel calcula apenas o risco inerente: o risco residual da norma depende da avaliação da "
       "eficácia dos controles internos de cada unidade, que não é dado público.")
bullet("As sanções CEIS/CNEP foram consultadas apenas para os fornecedores do STF e entram no escore "
       "heurístico, não no modelo supervisionado; SICAF e CNDT seguem fora, por falta de API pública.")

# ------------------------------------------------------- 9. próximos passos
doc.add_heading("9. Próximos passos recomendados (em ordem de custo-benefício)", level=1)
bullet([("Concluir a validação da tabela de pontos com os gestores do STF", True),
        (" (seção 7), já em curso, e registrar o quadro de mapeamento na dissertação; em seguida, "
         "reprocessar o painel com os pesos validados e verificar como muda o achado da seção 4.4.", False)])
bullet([("Sanções de todos os fornecedores no modelo", True),
        (": com a chave já disponível, coletar CEIS/CNEP dos cerca de 9.600 fornecedores do dataset "
         "multi-órgão (algumas horas de coleta, pelo limite da API) e testar a sanção prévia como variável "
         "do modelo supervisionado, com nova avaliação temporal.", False)])
bullet([("Custo assimétrico explícito", True),
        (" (falso negativo em contrato crítico vs. falso positivo) como peso amostral — transforma o "
         "balanceamento em decisão de gestão documentável (item 2.7).", False)])
bullet([("Sensibilidade do horizonte", True),
        (" (18/24 meses) e fine-tuning por órgão sobre o modelo nacional (seção 4.2).", False)])
bullet([("Piloto com servidores", True),
        (": medir a taxa de concordância humano-máquina (recomendação nº 6) e ajustar o desenho "
         "comportamental dos botões de governança.", False)])

# ------------------------------------------------------- 10. recursos
doc.add_heading("10. Recursos e reprodutibilidade", level=1)
par = doc.add_paragraph(); rich(par, "Repositório público (código + dados + relatórios): ", bold=True)
hyperlink(par, "github.com/DavidNadlerPrata/antecipa-pncp",
          "https://github.com/DavidNadlerPrata/antecipa-pncp")
par = doc.add_paragraph(); rich(par, "Reprodução em ~5 min no Google Colab (sem credenciais): ", bold=True)
hyperlink(par, "abrir ANTECIPA_colab_github.ipynb no Colab",
          "https://colab.research.google.com/github/DavidNadlerPrata/antecipa-pncp/blob/main/ANTECIPA_colab_github.ipynb")
par = doc.add_paragraph(); rich(par, "Dashboard publicado (link direto): ", bold=True)
hyperlink(par, "davidnadlerprata.github.io/antecipa-pncp/antecipa-4a8g1jdey1/",
          "https://davidnadlerprata.github.io/antecipa-pncp/antecipa-4a8g1jdey1/")
p("Endereço não indexado por buscadores (meta noindex) e de URL não adivinhável — adequado para "
  "compartilhamento com a orientadora e a banca antes da defesa. Observe-se que a proteção é por "
  "obscuridade, não por autenticação: quem tiver o link acessa. O arquivo também está no Drive em "
  "unb/ANTECIPA_dashboard_real.html (autocontido, abre em qualquer navegador).",
  italic=True, cor=CINZA, tam=9.5)
p("No Módulo 3, o dashboard apresenta as três leituras lado a lado — nível ex-ante e nível observado "
  "(ambos pela Res. 781/2022) e probabilidade prevista pelo modelo —, com as três matrizes de risco "
  "correspondentes e o detalhamento por contrato, que separa visualmente os fatores conhecidos na "
  "assinatura dos posteriores a ela.")
par = doc.add_paragraph(); rich(par, "Relatórios detalhados no repositório: ", bold=True)
rich(par, "README.md (visão geral e achados), dados/processados/relatorio_modelo.md (v1), "
          "relatorio_modelo_v2.md (v2) e comparacao_stf_vs_multi.md (experimento com bootstrap).")
p("Todos os dados utilizados são públicos (PNCP, compras.gov.br, dados abertos do CNPJ). Nenhuma "
  "informação interna do STF foi acessada; nada aqui constitui parecer jurídico. O repositório pode ser "
  "tornado privado ou transferido para a conta da pesquisadora a qualquer momento.",
  italic=True, cor=CINZA, tam=9.5)

doc.save(str(DESTINO))
print(f"gerado: {DESTINO} ({DESTINO.stat().st_size/1024:.0f} KB)")
