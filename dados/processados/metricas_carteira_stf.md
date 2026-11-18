# ANTECIPA — Critérios de alerta na carteira do STF

293 contratos · 62 com desfecho adverso · taxa base 21,2 % · escala oficial da Res. STF 781/2022 (risco inerente 0–100).

| Critério | Alertas | Acertos | Precisão | Recall | Lift |
|---|---|---|---|---|---|
| Ex-ante (Res. 781) — Elevado/Crítico | 0 | 0 | — | 0,0 % | — |
| Ex-ante (Res. 781) — Moderado ou acima | 158 | 32 | 20,2 % | 51,6 % | 0,96× |
| Matriz ML — Elevado/Crítico | 91 | 29 | 31,9 % | 46,8 % | 1,51× |
| Matriz ML — só Crítico | 40 | 18 | 45,0 % | 29,0 % | 2,13× |
| ML ≥ 20% | 82 | 45 | 54,9 % | 72,6 % | 2,59× |
| ML ≥ 10% | 128 | 51 | 39,8 % | 82,3 % | 1,88× |
| ML ≥ 5% | 184 | 56 | 30,4 % | 90,3 % | 1,44× |
| Ex-ante top-50 (risco inerente + pontos) | 50 | 9 | 18,0 % | 14,5 % | 0,85× |
| ML top-50 (probabilidade) | 50 | 27 | 54,0 % | 43,5 % | 2,55× |
| Ex-ante top-100 (risco inerente + pontos) | 100 | 19 | 19,0 % | 30,6 % | 0,90× |
| ML top-100 (probabilidade) | 100 | 49 | 49,0 % | 79,0 % | 2,32× |
| (referência, circular) Observado — Elevado/Crítico | 20 | 17 | 85,0 % | 27,4 % | 4,02× |

## Distribuição por nível

| Leitura | Baixo | Moderado | Elevado | Crítico |
|---|---|---|---|---|
| ex-ante | 135 | 158 | 0 | 0 |
| ML (matriz) | 80 | 122 | 51 | 40 |
| observado | 119 | 154 | 16 | 4 |

Números do ML otimistas (contratos do STF no treino); a leitura observada é circular (usa o desfecho). Ver RESULTADOS.md.
