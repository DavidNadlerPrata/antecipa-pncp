# ANTECIPA — Pipeline de dados reais (PNCP) e modelo preditivo

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DavidNadlerPrata/antecipa-pncp/blob/main/ANTECIPA_colab_github.ipynb)
*Reprodução completa no Google Colab sem instalar nada: o notebook clona este
repositório (que inclui os caches de dados públicos) e treina os modelos em ~5 min.
Quem tem acesso à pasta do projeto no Drive pode usar o `ANTECIPA_colab.ipynb`
(variante que monta o Drive e grava os resultados de volta).*

Evolução da PoC do projeto **ANTECIPA** (dissertação de Cristina Harumi Matsunaga,
Mestrado Profissional em Administração Pública, FACE/UnB): substitui os dados
simulados do primeiro protótipo por **dados reais e públicos** coletados das APIs
oficiais e treina o **modelo supervisionado de desfecho adverso** prometido no
projeto. Responde diretamente às recomendações nº 1, 2, 3, 7 e 9 da
`../analise_critica_ANTECIPA.md`.

Histórico de versões:

- **v1** — dados reais do STF nos 3 módulos do dashboard; dataset multi-órgão;
  primeiro modelo supervisionado (rótulo sem horizonte).
- **v2 (atual no dashboard)** — rótulo com **horizonte fixo de 12 meses**
  (corrige a censura à direita) e **probabilidades calibradas** (isotônica).
  Todos os artefatos da v1 foram preservados; o `processa.py` usa a v2 quando
  `ml_stf_v2.json` existe, com fallback automático para a v1.

## O que é real nesta versão

| Fonte | O que fornece | Uso |
|---|---|---|
| API de Consulta do PNCP (`pncp.gov.br/api/consulta`) | Contratos publicados desde 2023 pelo STF **e por 10 tribunais federais** (STJ, TST, TSE, STM, CNJ, TRF2–TRF6) — 25.488 contratos únicos | Módulo 3 + treino |
| API do PNCP — termos de contrato | Aditivos, apostilamentos e rescisões, com data → **desfecho real datado** | Rótulo do modelo |
| API de busca do PNCP (`pncp.gov.br/api/search`) | Presença nacional dos 15 maiores fornecedores do STF | Módulo 2 |
| Dados abertos do CNPJ — Receita Federal (via minhareceita.org) | Capital social, porte, idade, CNAE, situação de **9.598 fornecedores** | Módulo 2 + features |
| API de pesquisa de preços do compras.gov.br | Distribuição nacional de preços homologados por item de catálogo | Módulo 1 |

**Ainda não coletado** (exige credenciamento institucional): CEIS/CNEP, SICAF,
CNDT/TST — o dashboard indica esses itens como pendentes, conforme a
recomendação de usar APIs oficiais em vez de raspagem (análise crítica, 2.3).

## Modelo supervisionado (v2)

- **Rótulo**: evento adverso **em até 12 meses da assinatura** — rescisão/
  extinção, acréscimo de valor > 25 % ou prorrogação > 365 dias, datados pelo
  `dataAssinatura` dos termos. Só entram contratos com 12 meses completos de
  observação (16.783 elegíveis; 296 adversos, 1,8 %). Com isso a prevalência
  fica estável por coorte (1,5 % → 1,7 % → 2,1 %), eliminando o artefato de
  censura que na v1 fazia a taxa "cair" de 5,2 % para 1,6 %.
- **Features**: apenas informação disponível na assinatura (valor, duração,
  categoria, órgão, capital social, idade, porte, situação cadastral,
  capital/valor, recorrência do fornecedor). Nada da matriz de risco entra como
  rótulo — resposta direta à circularidade apontada no item 2.1.
- **Validação temporal** (treino ≤ 2024, teste 2025), métricas para classe rara
  (nunca acurácia — item 2.7):

| Modelo (teste 2025) | Precision | Recall | F1 | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|
| Gradient Boosting v2 | 0,109 | 0,494 | 0,179 | **0,139** (lift 6,6×) | 0,806 |
| Regressão Logística v2 | 0,052 | 0,647 | 0,096 | 0,065 | 0,755 |
| v1 · Gradient Boosting | 0,064 | 0,393 | 0,111 | 0,071 (lift 4,4×) | 0,798 |
| v1 · Baseline heurístico (Res. 781) | 0,067 | 0,129 | 0,088 | 0,033 | 0,705 |

  Visão operacional (fila de diligência): entre os 100 contratos de 2025 com
  maior escore, 16 tiveram desfecho adverso real (7,6× a taxa base).
- **Publicação no dashboard**: `CalibratedClassifierCV` isotônica (5 folds) —
  as porcentagens exibidas são frequências reais (mediana 7,8 %, máx. 24,5 % na
  carteira do STF), não escores inflados pelo `class_weight`. Explicações por
  contribuições aditivas (log-odds) da regressão logística — insumo da
  motivação humana, não a motivação (item 2.8).
- **Evidência da calibração** (`diagrama_calibracao.py` → `diagrama_calibracao.png`):
  no teste temporal de 2025, o modelo bruto prevê em média 24,5 % onde a
  frequência real é 2,1 % (superestimativa de ~12×); calibrado, a média vai a
  2,0 % e o ECE cai de 0,224 para 0,006. O ROC-AUC praticamente não se altera
  (0,806 → 0,802), confirmando que a transformação monotônica preserva a
  ordenação — a calibração torna a escala interpretável sem alterar a
  capacidade de discriminar.
- **Experimentos complementares**: `comparacao_stf_vs_multi.md` (só-STF ×
  multi-órgão no mesmo teste, com bootstrap — empate técnico; multi-órgão
  preferido por estabilidade, nuance empírica à recomendação nº 2) e
  `relatorio_modelo.md` / `relatorio_modelo_v2.md` (relatórios completos).

## Achados de qualidade de dados (relevantes para a dissertação)

1. **O STF não preenche `catalogoCodigoItem`** (CATMAT/CATSER) nos itens que
   publica no PNCP — 0 de 916 itens tinham código. A comparação nacional de
   preços exigiu reconstruir a ponte descrição → PDM → códigos CATMAT via
   catálogo do compras.gov.br (`coleta_precos_v2.py`). Confirma na prática o
   item 2.4 da análise crítica: a maior parte do esforço é engenharia de dados.
2. Serviços continuados são publicados como item único de valor global
   (quantidade 1), o que inviabiliza comparação unitária de preços de serviços
   sem normalização adicional (postos, m², etc.).
3. **As listas paginadas do PNCP contêm duplicatas** (republicações/
   retificações): o TST retorna 13.765 registros para 9.407 contratos únicos.
   Deduplicação por `numeroControlePNCP` é obrigatória.
4. Os CNPJs raiz de TST/TSE agregam unidades regionais (a coleta de um "órgão"
   pode trazer dezenas de unidades) e a API aplica rate-limit (HTTP 429) em
   coletas longas — o pipeline usa retry/backoff e passe de reparo
   (`repara_multi.py`).

## Como executar

```bash
cd pipeline
# Coleta (idempotente; apague o JSON em dados/brutos/ para recoletar)
python coleta_pncp.py         # STF: contratos, termos, fornecedores, itens
python coleta_precos_v2.py    # preços de referência via PDM/CATMAT + reparos
python coleta_multi.py        # 10 tribunais federais: contratos + termos
python repara_multi.py        # refaz janelas que falharam por rate-limit
python coleta_cadastros.py    # Receita Federal p/ todos os fornecedores únicos

# Datasets e modelos
python monta_dataset.py       # v1: dataset_ml_multi.csv (rótulo sem horizonte)
python treina_modelo.py       # v1: treino + relatorio_modelo.md + ml_stf.json
python monta_dataset_v2.py    # v2: rótulo com horizonte de 12 meses
python treina_modelo_v2.py    # v2: treino + relatorio_modelo_v2.md
python treina_stf_vs_multi.py # experimento só-STF × multi-órgão (bootstrap)
python diagrama_calibracao.py # diagrama de confiabilidade (figura + métricas)
python publica_modelo_v2.py   # v2 calibrado p/ dashboard (ml_stf_v2.json)

# Dashboard
python processa.py            # consolida STF + predições (v2 se existir, senão v1)
python gera_dashboard.py      # grava ../../ANTECIPA_dashboard_real.html
```

Dependências: biblioteca padrão do Python 3.10+ para a coleta;
`scikit-learn` para os scripts de treino (`pip install scikit-learn`).

## Estrutura

```
antecipa-real/
├── pipeline/                 scripts de coleta, treino e template do dashboard
├── dados/brutos/             JSONs como vieram das APIs (cache; multi/ por órgão)
├── dados/processados/
│   ├── antecipa_dados.json          dados consolidados do dashboard
│   ├── dataset_ml_multi.csv         dataset v1 (25.488 contratos, 11 órgãos)
│   ├── dataset_ml_multi_v2.csv      dataset v2 (16.783 elegíveis, rótulo 12m)
│   ├── relatorio_modelo.md          métricas v1
│   ├── relatorio_modelo_v2.md       métricas v2 + comparação com v1
│   ├── comparacao_stf_vs_multi.md   experimento só-STF × multi-órgão
│   ├── diagrama_calibracao.png      evidência visual da calibração
│   ├── calibracao_metricas.json     Brier, ECE e curvas por bin
│   ├── ml_stf.json / ml_stf_v2.json predições por contrato (v1 / v2 calibrado)
│   └── modelo_metrics*.json         métricas em formato estruturado
└── README.md
../ANTECIPA_dashboard_real.html   dashboard final (autocontido, abre no navegador)
```

## Limitações honestas desta iteração

- O horizonte de 12 meses não captura desfechos tardios (ex.: aditivos do 2º
  ano de serviços continuados) — recorte deliberado para comparabilidade;
  sensibilidade com 18/24 meses é extensão natural.
- O rótulo captura desfechos administráveis (aditivos, rescisões, prorrogações)
  — não fraude ou conluio, raros e não observáveis nestas bases.
- `nº contratos do fornecedor` é contado no dataset completo (leve vazamento
  temporal; em produção, contar só contratos anteriores à assinatura).
- A busca nacional por fornecedor usa o CNPJ como termo de busca textual
  (limite de ~200 contratos por fornecedor nesta coleta).
- Comparação de preços usa o PDM (agregado de itens CATMAT similares); unidades
  de fornecimento heterogêneas ainda podem distorcer — desvios disparam
  diligência, nunca conclusão automática.
- Pequenas lacunas de coleta permanecem onde o rate-limit persistiu (TRF5/2026
  e páginas profundas de TST/TSE 2023).
