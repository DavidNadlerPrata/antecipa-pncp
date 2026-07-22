# ANTECIPA — Relatório do modelo supervisionado

**Tarefa**: prever `desfecho_adverso` (rescisão, acréscimo >25% ou prorrogação
>1 ano, observados nos termos do PNCP) no momento da **assinatura** do contrato.

**Dados**: 25488 contratos de 11 órgãos do Judiciário federal (2023–2026).
Treino 2023–2024: 12483 contratos (5.2% adversos).
Teste temporal 2025: 9014 contratos (1.6% adversos).
Contratos de 2026 excluídos da avaliação (rótulo imaturo/censurado).

## Métricas no teste (classe positiva = desfecho adverso)

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC | Alertas |
|---|---|---|---|---|---|---|
| Regressão Logística | 0.049 | 0.35 | 0.086 | 0.04 | 0.746 | 998 |
| Gradient Boosting | 0.064 | 0.393 | 0.111 | 0.071 | 0.798 | 853 |
| Baseline heurístico (Res. 781) | 0.067 | 0.129 | 0.088 | 0.033 | 0.705 | 267 |

Prevalência no teste (classificador aleatório teria PR-AUC ≈): 0.016.
Limiar de decisão escolhido no treino (máximo F1 em validação cruzada 5-fold).

## Fatores mais informativos (importância de permutação, PR-AUC, teste)

| Feature | Δ PR-AUC |
|---|---|
| duração (dias) | 0.0353 |
| log10(valor global) | 0.0149 |
| nº contratos do fornecedor | 0.0099 |
| faltante: log10(capital social) | 0.0087 |
| log10(capital/valor) | 0.0067 |
| faltante: optante do Simples | 0.0066 |
| log10(capital social) | 0.0059 |
| idade do fornecedor (anos) | 0.0035 |
| optante do Simples | 0.0015 |
| consórcio | 0.0 |
| situação cadastral ativa | -0.0 |
| faltante: idade do fornecedor (anos) | -0.0002 |

## Modelo publicado no dashboard

**Gradient Boosting** (maior PR-AUC), reajustado em 2023–2025. As explicações por
contrato usam as contribuições aditivas (log-odds) da regressão logística —
explicação exata, não aproximação; equivalente a SHAP para modelo linear.

## Limitações e leitura honesta

- O rótulo captura desfechos *administráveis* (aditivos, rescisões) — não
  fraude ou conluio, que são raros e não observáveis nestas bases.
- Censura à direita: contratos recentes tiveram menos tempo para acumular
  termos; a validação temporal mitiga, não elimina.
- `nº contratos do fornecedor` é contado no dataset completo (leve vazamento;
  em produção, contar apenas contratos anteriores à assinatura).
- Prevalência e composição de carteira variam por órgão; o modelo aprende o
  padrão do Judiciário federal, não peculiaridades de um único órgão.
- A predição dispara **diligência humana** (Res. 781/2022), nunca decisão
  automática — ver salvaguardas no projeto.
