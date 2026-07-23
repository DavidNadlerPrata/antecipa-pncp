# ANTECIPA — SHAP (Gradient Boosting) × Regressão Logística

Comparação das duas formas de explicar a predição, para os **mesmos contratos do
STF** e no **mesmo espaço de variáveis** (ambos os modelos ajustados sobre a
mesma matriz pré-processada, 16783 contratos de treino).

- **SHAP sobre o Gradient Boosting**: atribuições do modelo que de fato produz a
  probabilidade exibida. Somadas ao valor-base, reconstroem exatamente a
  predição.
- **Contribuições da Regressão Logística**: exatas para *aquele* modelo linear,
  mas ele não é o modelo publicado — é substituto interpretável.

## Concordância entre as duas explicações

| Indicador | Valor |
|---|---|
| Correlação de Spearman média entre as atribuições | 0.222 |
| Correlação mediana | 0.227 |
| Contratos em que o **fator principal coincide** | 12.3% |
| Sobreposição média entre os 3 principais fatores | 56.3% |
| Contratos analisados | 293 |

## Importância global (média de |contribuição|)

| Variável | SHAP (GB) | Reg. Logística |
|---|---|---|
| duração (dias) | 1.521 | 0.156 |
| órgão: STF | 0.810 | 3.024 |
| log10(valor global) | 0.383 | 0.475 |
| nº contratos do fornecedor | 0.334 | 0.480 |
| idade do fornecedor (anos) | 0.129 | 0.021 |
| log10(capital social) | 0.114 | 0.214 |
| log10(capital/valor) | 0.105 | 0.025 |
| categoria: Compras | 0.078 | 0.463 |
| órgão: TSE | 0.039 | 0.000 |
| optante do Simples | 0.015 | 0.092 |

## Exemplos contrato a contrato

### Contrato 010294/2023 — probabilidade do GB: 84.8%

| # | SHAP (Gradient Boosting) | valor | Regressão Logística | valor |
|---|---|---|---|---|
| 1 | duração (dias) | +1.67 | órgão: STF | +3.02 |
| 2 | órgão: STF | +0.97 | log10(valor global) | +1.17 |
| 3 | log10(capital/valor) | +0.21 | log10(capital social) | +0.25 |
| 4 | log10(valor global) | +0.19 | duração (dias) | +0.11 |
| 5 | idade do fornecedor (anos) | -0.17 | dado ausente (idade do fornecedor (anos)) | +0.07 |

### Contrato 010771/2024 — probabilidade do GB: 95.9%

| # | SHAP (Gradient Boosting) | valor | Regressão Logística | valor |
|---|---|---|---|---|
| 1 | duração (dias) | +1.93 | órgão: STF | +3.02 |
| 2 | órgão: STF | +1.43 | log10(valor global) | +0.48 |
| 3 | log10(valor global) | +0.70 | nº contratos do fornecedor | -0.40 |
| 4 | log10(capital/valor) | +0.25 | log10(capital social) | +0.25 |
| 5 | idade do fornecedor (anos) | +0.13 | duração (dias) | +0.14 |

### Contrato 012732/2025 — probabilidade do GB: 5.4%

| # | SHAP (Gradient Boosting) | valor | Regressão Logística | valor |
|---|---|---|---|---|
| 1 | nº contratos do fornecedor | -1.51 | órgão: STF | +3.02 |
| 2 | log10(valor global) | +0.82 | nº contratos do fornecedor | -1.43 |
| 3 | duração (dias) | -0.57 | log10(valor global) | +0.45 |
| 4 | idade do fornecedor (anos) | -0.26 | log10(capital social) | +0.18 |
| 5 | órgão: STF | +0.24 | dado ausente (idade do fornecedor (anos)) | +0.07 |

## Como ler esta comparação

Quanto mais baixa a concordância, menos a explicação hoje exibida no dashboard
(logística) representa o raciocínio do modelo que produz a probabilidade (GB).
O Gradient Boosting supera a logística em PR-AUC por larga margem (0,139 contra
0,065 no teste temporal de 2025); essa diferença é justamente a estrutura não
linear que a logística não captura — e que, portanto, não aparece na explicação
substituta.

Decisão a tomar: (A) migrar as explicações do dashboard para SHAP sobre o GB —
fiel ao modelo publicado, ao custo de uma dependência e de valores conceitualmente
mais difíceis de comunicar; ou (B) publicar a própria regressão logística como
modelo, abrindo mão de metade do poder preditivo em troca de um sistema em que a
explicação **é** o modelo — defensável num contexto em que o princípio da
motivação pesa mais que pontos de acurácia.
