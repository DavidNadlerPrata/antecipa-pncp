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


def pontuacao(p, i):
    """Risco inerente oficial (0–100) a partir das posições ordinais 1–5."""
    return VALOR[p] * VALOR[i]


def nivel_da_pontuacao(s):
    return next(n for lim, n in FAIXAS if s < lim)


def nivel(p, i):
    return nivel_da_pontuacao(pontuacao(p, i))


ALTOS = ("Elevado", "Crítico")
