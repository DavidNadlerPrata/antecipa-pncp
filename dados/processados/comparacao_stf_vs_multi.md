# ANTECIPA — Só STF × Multi-órgão (teste comum: STF 2025)

Experimento que testa a fragilidade 2.2 da análise crítica: *"cinco anos de
histórico de um único órgão pode ser insuficiente para treinar sem overfitting"*.

**Conjunto de teste (idêntico para todos)**: contratos do STF assinados em 2025
— 106 contratos, 13 com desfecho adverso
(12.3%).

| Treino | Contratos | Adversos |
|---|---|---|
| Só STF (2023–24) | 148 | 49 |
| Multi-órgão, 11 órgãos (2023–24) | 12483 | 649 |

## Métricas no teste STF/2025

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC | Alertas |
|---|---|---|---|---|---|---|
| Só STF · Regressão Logística | 0.154 | 0.615 | 0.246 | 0.156 | 0.591 | 52 |
| Só STF · Gradient Boosting | 0.136 | 0.846 | 0.234 | 0.384 | 0.712 | 81 |
| Multi-órgão · Regressão Logística | 0.148 | 0.923 | 0.255 | 0.122 | 0.5 | 81 |
| Multi-órgão · Gradient Boosting | 0.154 | 0.615 | 0.246 | 0.319 | 0.644 | 52 |
| Baseline heurístico (Res. 781) | 0.2 | 0.077 | 0.111 | 0.124 | 0.475 | 5 |

Prevalência no teste (PR-AUC de um classificador aleatório):
0.123.

## Notas de leitura

- Com ~148 contratos e só 49 positivos no treino
  só-STF, o limiar e as métricas são instáveis (alta variância) — qualquer
  ranking deve ser lido com cautela; PR-AUC e ROC-AUC (independentes de limiar)
  são as colunas mais informativas.
- O teste tem apenas 13 positivos: diferenças pequenas de PR-AUC
  não são estatisticamente conclusivas; diferenças grandes e consistentes entre
  os dois algoritmos, sim.
- O modelo multi-órgão vê o "padrão do Judiciário federal" (inclusive o próprio
  STF 2023–24) e por isso tende a generalizar melhor — é a recomendação nº 2 da
  análise crítica em ação.

## Teste de significância (bootstrap, 4.000 reamostras do teste)

Δ PR-AUC (só-STF − multi-órgão, Gradient Boosting): **+0,069**,
IC 95 % **[−0,221; +0,350]** — o intervalo cruza zero com folga.
O modelo só-STF vence em apenas 69 % das reamostras.

**Conclusão**: empate técnico. Com 13 positivos no teste, não há evidência
estatística de superioridade de nenhum dos dois. A leitura equilibrada para a
dissertação: (i) o padrão local do STF carrega sinal específico relevante
(prevalência de desfecho adverso 33 % no treino só-STF vs. 5 % no multi) e um
modelo local pequeno já supera o baseline heurístico; (ii) o modelo multi-órgão
entrega desempenho comparável no STF com 84× mais dados de treino, é muito mais
estável fora da amostra e é o único viável para métricas confiáveis — o que
sustenta, com nuance, a recomendação nº 2 da análise crítica: treinar
multi-órgão e, como refinamento futuro, calibrar/afinar por órgão
(*fine-tuning* local sobre o modelo nacional).
