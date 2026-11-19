# ANTECIPA — Critérios de alerta na carteira do STF

293 contratos · 62 com desfecho adverso · taxa base 21,2 % · escala oficial da Res. STF 781/2022 (risco inerente 0–100).

| Critério | Alertas | Acertos | Precisão | Recall | Lift |
|---|---|---|---|---|---|
| Ex-ante (Res. 781) — Elevado/Crítico | 2 | 0 | 0,0 % | 0,0 % | 0,00× |
| Ex-ante (Res. 781) — Moderado ou acima | 72 | 14 | 19,4 % | 22,6 % | 0,92× |
| Matriz ML — Elevado/Crítico | 91 | 29 | 31,9 % | 46,8 % | 1,51× |
| Matriz ML — só Crítico | 40 | 18 | 45,0 % | 29,0 % | 2,13× |
| ML ≥ 20% | 82 | 45 | 54,9 % | 72,6 % | 2,59× |
| ML ≥ 10% | 128 | 51 | 39,8 % | 82,3 % | 1,88× |
| ML ≥ 5% | 184 | 56 | 30,4 % | 90,3 % | 1,44× |
| Ex-ante top-50 (risco inerente + pontos) | 50 | 11 | 22,0 % | 17,7 % | 1,04× |
| ML top-50 (probabilidade) | 50 | 27 | 54,0 % | 43,5 % | 2,55× |
| Ex-ante top-100 (risco inerente + pontos) | 100 | 21 | 21,0 % | 33,9 % | 0,99× |
| ML top-100 (probabilidade) | 100 | 49 | 49,0 % | 79,0 % | 2,32× |
| (referência, circular) Observado — Elevado/Crítico | 19 | 15 | 79,0 % | 24,2 % | 3,73× |

## Distribuição por nível

| Leitura | Baixo | Moderado | Elevado | Crítico |
|---|---|---|---|---|
| ex-ante | 221 | 70 | 2 | 0 |
| ML (matriz) | 80 | 122 | 51 | 40 |
| observado | 198 | 76 | 16 | 3 |

Números do ML otimistas (contratos do STF no treino); a leitura observada é circular (usa o desfecho). Ver RESULTADOS.md.
