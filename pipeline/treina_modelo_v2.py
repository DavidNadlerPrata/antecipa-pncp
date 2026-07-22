# -*- coding: utf-8 -*-
"""
ANTECIPA — Treino v2: rótulo com horizonte fixo de 12 meses.

Mesmo protocolo da v1 (validação temporal, mesmos algoritmos e hiperparâmetros)
mudando apenas o rótulo/elegibilidade — para isolar o efeito da correção de
censura. Treino: assinados 2022–2024. Teste: assinados em 2025 (todos com 12
meses completos de observação, por construção do dataset v2).

Saídas: relatorio_modelo_v2.md e modelo_metrics_v2.json (v1 preservada).
"""
import csv
import json
import math
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"

with open(PROC / "dataset_ml_multi_v2.csv", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))

def num(r, k):
    v = r.get(k, "")
    try:
        return float(v)
    except ValueError:
        return np.nan

NUM_DEFS = [
    ("log10(valor global)",        lambda r: math.log10(max(num(r, "valor_global"), 1))),
    ("duração (dias)",             lambda r: num(r, "duracao_dias")),
    ("log10(capital social)",      lambda r: math.log10(num(r, "capital_social") + 1)
                                             if not np.isnan(num(r, "capital_social")) else np.nan),
    ("idade do fornecedor (anos)", lambda r: num(r, "idade_forn_anos")),
    ("optante do Simples",         lambda r: num(r, "simples")),
    ("situação cadastral ativa",   lambda r: num(r, "situacao_ativa")),
    ("consórcio",                  lambda r: num(r, "consorcio")),
    ("log10(capital/valor)",       lambda r: math.log10(max(num(r, "razao_capital_valor"), 1e-6))
                                             if not np.isnan(num(r, "razao_capital_valor")) else np.nan),
    ("nº contratos do fornecedor", lambda r: math.log1p(num(r, "n_contratos_forn_dataset"))),
]
CAT_COLS = ["categoria", "porte", "orgao"]
n_num = len(NUM_DEFS)

X_num = np.array([[f(r) for _, f in NUM_DEFS] for r in rows], dtype=float)
X_cat = np.array([[r[c] or "?" for c in CAT_COLS] for r in rows], dtype=object)
X = np.concatenate([X_num, X_cat], axis=1).astype(object)
y = np.array([int(r["label_adverso_12m"]) for r in rows])
ano = np.array([int(r["assinatura"][:4]) for r in rows])

tr = ano <= 2024
te = ano == 2025
print(f"treino ≤2024: {tr.sum()} ({y[tr].mean()*100:.1f}% adversos) | "
      f"teste 2025: {te.sum()} ({y[te].mean()*100:.1f}% adversos)")

pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                      ("sc", StandardScaler())]), list(range(n_num))),
    ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
     list(range(n_num, n_num + len(CAT_COLS)))),
])
modelos = {
    "Regressão Logística": Pipeline([("pre", pre), ("clf", LogisticRegression(
        max_iter=5000, class_weight="balanced", C=0.5))]),
    "Gradient Boosting": Pipeline([("pre", pre), ("clf", HistGradientBoostingClassifier(
        random_state=42, class_weight="balanced", max_depth=4,
        learning_rate=0.08, max_iter=250, l2_regularization=1.0))]),
}

res = {}
for nome, mdl in modelos.items():
    cvp = cross_val_predict(mdl, X[tr], y[tr], cv=5, method="predict_proba")[:, 1]
    ths = np.unique(np.round(cvp, 3))
    f1s = [f1_score(y[tr], (cvp >= t).astype(int), zero_division=0) for t in ths]
    thr = float(ths[int(np.argmax(f1s))])
    mdl.fit(X[tr], y[tr])
    p_te = mdl.predict_proba(X[te])[:, 1]
    yhat = (p_te >= thr).astype(int)
    pr, rc, f1, _ = precision_recall_fscore_support(
        y[te], yhat, average="binary", zero_division=0)
    # precision@k: fila de diligência com k = nº real de positivos e k = 100
    ordem = np.argsort(-p_te)
    k_pos = int(y[te].sum())
    res[nome] = {
        "limiar": thr,
        "precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3),
        "pr_auc": round(average_precision_score(y[te], p_te), 3),
        "roc_auc": round(roc_auc_score(y[te], p_te), 3),
        "alertas": int(yhat.sum()),
        "precision_at_100": round(float(y[te][ordem[:100]].mean()), 3),
        "recall_at_100": round(float(y[te][ordem[:100]].sum() / max(k_pos, 1)), 3),
    }
    print(nome, res[nome])

res["_prevalencia_teste"] = round(float(y[te].mean()), 3)

# comparação com a v1 (mesmos algoritmos, rótulo sem horizonte)
v1 = json.loads((PROC / "modelo_metrics.json").read_text(encoding="utf-8"))["metricas"]

def fmt(nome, m):
    return (f"| {nome} | {m['precision']} | {m['recall']} | {m['f1']} | "
            f"{m['pr_auc']} | {m['roc_auc']} |")

rel = f"""# ANTECIPA — Modelo v2: rótulo com horizonte fixo de 12 meses

Única mudança em relação à v1: o rótulo passa a ser *evento adverso em até 12
meses da assinatura* (datado pelo termo), e só entram contratos com 12 meses
completos de observação. Mesmo protocolo, algoritmos e hiperparâmetros.

**Efeito da correção de censura na prevalência por coorte de assinatura**
(v1 caía de 5,2% no treino para 1,6% no teste — artefato de censura):
2023 = 1,5% · 2024 = 1,7% · 2025 = 2,1% — estável, como deve ser.

**Dados**: {len(rows)} contratos elegíveis (8.705 excluídos por observação
insuficiente). Treino ≤2024: {tr.sum()} ({y[tr].mean()*100:.1f}% adversos).
Teste 2025: {te.sum()} ({y[te].mean()*100:.1f}% adversos).

## Métricas no teste (classe positiva = adverso em 12 meses)

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC |
|---|---|---|---|---|---|
{fmt('Regressão Logística (v2)', res['Regressão Logística'])}
{fmt('Gradient Boosting (v2)', res['Gradient Boosting'])}
{fmt('— v1 · Regressão Logística', v1['Regressão Logística'])}
{fmt('— v1 · Gradient Boosting', v1['Gradient Boosting'])}
{fmt('— v1 · Baseline heurístico', v1['Baseline heurístico (Res. 781)'])}

Prevalência no teste v2 (PR-AUC do acaso): {res['_prevalencia_teste']} ·
v1: {v1['_prevalencia_teste']}. **Atenção**: v1 e v2 têm testes e rótulos
diferentes — a comparação de PR-AUC deve ser feita em razão da prevalência
(lift sobre o acaso), não em valor absoluto.

## Visão operacional (fila de diligência)

| Modelo | Precision@100 | Recall@100 |
|---|---|---|
| Regressão Logística (v2) | {res['Regressão Logística']['precision_at_100']} | {res['Regressão Logística']['recall_at_100']} |
| Gradient Boosting (v2) | {res['Gradient Boosting']['precision_at_100']} | {res['Gradient Boosting']['recall_at_100']} |

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
"""
(PROC / "relatorio_modelo_v2.md").write_text(rel, encoding="utf-8")
(PROC / "modelo_metrics_v2.json").write_text(
    json.dumps({"metricas": res}, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nRelatório: dados/processados/relatorio_modelo_v2.md")
