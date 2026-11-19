# -*- coding: utf-8 -*-
"""
Escalas oficiais da Resolução STF nº 781/2022 (Política de Gestão de Riscos) —
fonte única para todo o pipeline. Transcritas dos anexos oficiais da norma
(escala de probabilidade, escala de impacto, escala de nível de risco e escala de
eficácia dos controles).

  probabilidade e impacto: cinco níveis com VALORES 1, 2, 5, 8, 10
  risco inerente = probabilidade × impacto  (0 a 100)
  faixas: Baixo 0–9,9 · Moderado 10–39,9 · Elevado 40–79,9 · Crítico 80–100
  risco residual = risco inerente × risco de controle (1,0 · 0,8 · 0,6 · 0,4 · 0,2)

Os descritores da norma são qualitativos ("Rara", "Improvável"...): ela NÃO
define como converter dados observáveis em níveis. A conversão usada no ANTECIPA
(tabela de pontos em processa.py) é operacionalização própria, sujeita a validação
pelos gestores de risco do STF.

Como dados públicos não informam a eficácia dos controles internos, o ANTECIPA
calcula apenas o RISCO INERENTE (equivale a supor controle não avaliado).

Internamente os níveis são representados pela POSIÇÃO ordinal 1–5; VALOR traduz
posição -> valor oficial.
"""

VALOR = {1: 1, 2: 2, 3: 5, 4: 8, 5: 10}

PROBABILIDADE = {   # posição: (rótulo, descritor oficial)
    1: ("Muito baixa", "Rara"),
    2: ("Baixa", "Improvável"),
    3: ("Média", "Possível"),
    4: ("Alta", "Provável"),
    5: ("Muito alta", "Praticamente certa"),
}
IMPACTO = {
    1: ("Muito baixo", "Insignificante"),
    2: ("Baixo", "Pequeno"),
    3: ("Médio", "Moderado"),
    4: ("Alto", "Significativo"),
    5: ("Muito alto", "Catastrófico"),
}
FAIXAS = [(10, "Baixo"), (40, "Moderado"), (80, "Elevado"), (float("inf"), "Crítico")]
RISCO_CONTROLE = {"Inexistente": 1.0, "Insuficiente": 0.8, "Mediano": 0.6,
                  "Satisfatório": 0.4, "Forte": 0.2}


def posicao_probabilidade(pontos):
    """Converte a soma de pontos do escore heurístico na posição ordinal 1–5,
    arredondando 0,5 PARA CIMA — regra convencional, idêntica à função
    ARRED/ROUND do Excel usada na planilha de validação.

    Não usar round() do Python: ele arredonda 0,5 para o par mais próximo
    (2,5 -> 2, 3,5 -> 4), o que contrariava a regra documentada e, até 19/11/2026,
    alterava a posição de 29 leituras na carteira do STF. O round(x, 6) elimina
    ruído de ponto flutuante (1,2 + 0,3 = 1,4999999…).
    """
    import math
    return max(1, min(5, math.floor(round(float(pontos), 6) + 0.5)))


def pontuacao(p, i):
    """Risco inerente oficial (0–100) a partir das posições ordinais 1–5."""
    return VALOR[p] * VALOR[i]


def nivel_da_pontuacao(s):
    return next(n for lim, n in FAIXAS if s < lim)


def nivel(p, i):
    return nivel_da_pontuacao(pontuacao(p, i))


ALTOS = ("Elevado", "Crítico")


# ---------------------------------------------------------------------------
# Tabela de pontos do escore heurístico — OPERACIONALIZAÇÃO PRÓPRIA, EM VALIDAÇÃO
# com os gestores de risco do STF (planilha gerada por gera_planilha_validacao.py).
# Fonte única: processa.py e os baselines dos scripts de treino leem daqui.
# Para adotar pesos validados, altere apenas este dicionário e reprocesse.
# Os limiares (2 %, 30 %, 3 anos…) ficam no código que aplica cada regra.
# ---------------------------------------------------------------------------
BASE_PONTOS = 1.0   # todo contrato parte de 1,0 ponto (posição "Muito baixa")
PESOS = {
    # ex-ante — conhecidos na assinatura
    "F1": 1.2,    # capital social < 2 % do valor do contrato
    "F2": -0.5,   # capital social > 30 % do valor do contrato
    "F3": 0.3,    # capital social não informado na base aberta (ex.: consórcios)
    "F4": 0.8,    # CNPJ com menos de 3 anos na data da assinatura
    "F5": -0.4,   # CNPJ com mais de 10 anos na data da assinatura
    "F6": 1.0,    # crescimento contratual atípico (≥ 3× a mediana no PNCP) — só top-15
    "F7": 1.5,    # situação cadastral na Receita diferente de "Ativa"
    "F8": 0.4,    # vigência prevista superior a 12 meses
    "F9": 2.0,    # sanção CEIS/CNEP vigente e já publicada na assinatura
    # (F10 — "fornecedor sem perfil coletado", +0,3 — retirado em 19/11/2026: era
    #  artefato de coleta; F1–F5 e F7 passaram a usar o cadastro de todos)
    # observado — posteriores à assinatura
    "O1": 0.8,    # 2 ou mais termos aditivos
    "O2": 0.8,    # valor acumulado > 10 % acima do inicial
    "O3": 1.5,    # termo de rescisão/extinção registrado
}
