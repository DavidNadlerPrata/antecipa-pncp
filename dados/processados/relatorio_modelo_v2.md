# ANTECIPA — Modelo v2: rótulo com horizonte fixo de 12 meses

Única mudança em relação à v1: o rótulo passa a ser *evento adverso em até 12
meses da assinatura* (datado pelo termo), e só entram contratos com 12 meses
completos de observação. Mesmo protocolo, algoritmos e hiperparâmetros.

**Efeito da correção de censura na prevalência por coorte de assinatura**
(v1 caía de 5,2% no treino para 1,6% no teste — artefato de censura):
2023 = 1,5% · 2024 = 1,7% · 2025 = 2,1% — estável, como deve ser.

**Dados**: 16783 contratos elegíveis (8.705 excluídos por observação
insuficiente). Treino ≤2024: 12718 (1.7% adversos).
Teste 2025: 4065 (2.1% adversos).

## Métricas no teste (classe positiva = adverso em 12 meses)

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|
| Regressão Logística (v2) | 0.052 | 0.647 | 0.096 | 0.065 | 0.755 |
| Gradient Boosting (v2) | 0.109 | 0.494 | 0.179 | 0.139 | 0.806 |
| — v1 · Regressão Logística | 0.049 | 0.35 | 0.086 | 0.04 | 0.746 |
| — v1 · Gradient Boosting | 0.064 | 0.393 | 0.111 | 0.071 | 0.798 |
| — v1 · Baseline heurístico | 0.067 | 0.129 | 0.088 | 0.033 | 0.705 |

Prevalência no teste v2 (PR-AUC do acaso): 0.021 ·
v1: 0.016. **Atenção**: v1 e v2 têm testes e rótulos
diferentes — a comparação de PR-AUC deve ser feita em razão da prevalência
(lift sobre o acaso), não em valor absoluto.

## Visão operacional (fila de diligência)

| Modelo | Precision@100 | Recall@100 |
|---|---|---|
| Regressão Logística (v2) | 0.09 | 0.106 |
| Gradient Boosting (v2) | 0.16 | 0.188 |

(Dos 100 contratos de 2025 com maior escore — aproximadamente a capacidade
anual de uma equipe de controle — quantos de fato tiveram desfecho adverso
em 12 meses, e que fração de todos os adversos isso captura.)

## Limitações remanescentes

- O horizonte de 12 meses não captura desfechos tardios (aditivos do 2º ano em
  serviços continuados) — é um recorte deliberado para comparabilidade; um
  estudo de sensibilidade com horizonte de 18/24 meses fica como extensão.
- Probabilidades seguem sem calibração (class_weight distorce a escala);
  para exibir % ao usuário, aplicar recalibração (item 5 das recomendações
  de balanceamento).
- Demais limitações da v1 (proxy de recorrência, sem sanções) permanecem.
