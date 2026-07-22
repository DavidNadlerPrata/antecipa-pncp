# -*- coding: utf-8 -*-
"""
ANTECIPA — Experimento: treinar só com STF × treinar multi-órgão.

Testa empiricamente a fragilidade 2.2 da análise crítica ("o STF sozinho gera
volume insuficiente para treinar sem overfitting"). Ambos os modelos são
avaliados no MESMO conjunto de teste — contratos do STF assinados em 2025 —
com a mesma validação temporal do experimento principal:

  Modelo A ("só STF")      : treina em contratos do STF de 2023–2024
  Modelo B ("multi-órgão") : treina em contratos dos 11 órgãos de 2023–2024
  Baseline heurístico      : escore transparente da Res. 781/2022

Saída: dados/processados/comparacao_stf_vs_multi.md
"""
import csv
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

with open(PROC / "dataset_ml_multi.csv", encoding="utf-8") as fh:
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
y = np.array([int(r["label_desfecho_adverso"]) for r in rows])
ano = np.array([int(r["assinatura"][:4]) if r["assinatura"] else 0 for r in rows])
stf = np.array([r["orgao"] == "STF" for r in rows])

tr_periodo = (ano >= 2023) & (ano <= 2024)
tr_stf = tr_periodo & stf          # A: só STF
tr_multi = tr_periodo              # B: todos os órgãos
teste = (ano == 2025) & stf        # teste comum: STF 2025

print(f"treino só-STF: {tr_stf.sum()} contratos ({y[tr_stf].sum()} adversos, "
      f"{y[tr_stf].mean()*100:.1f}%)")
print(f"treino multi : {tr_multi.sum()} contratos ({y[tr_multi].sum()} adversos, "
      f"{y[tr_multi].mean()*100:.1f}%)")
print(f"teste STF/2025: {teste.sum()} contratos ({y[teste].sum()} adversos, "
      f"{y[teste].mean()*100:.1f}%)\n")


def faz_pipeline(clf):
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), list(range(n_num))),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
         list(range(n_num, n_num + len(CAT_COLS)))),
    ])
    return Pipeline([("pre", pre), ("clf", clf)])


def avalia(nome, mask_treino):
    out = {}
    for algo, clf in [
        ("LogReg", LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5)),
        ("GradBoost", HistGradientBoostingClassifier(
            random_state=42, class_weight="balanced", max_depth=4,
            learning_rate=0.08, max_iter=250, l2_regularization=1.0)),
    ]:
        mdl = faz_pipeline(clf)
        n_pos = int(y[mask_treino].sum())
        cv = min(5, n_pos)  # com poucos positivos, reduz folds
        cvp = cross_val_predict(mdl, X[mask_treino], y[mask_treino],
                                cv=cv, method="predict_proba")[:, 1]
        ths = np.unique(np.round(cvp, 3))
        f1s = [f1_score(y[mask_treino], (cvp >= t).astype(int), zero_division=0)
               for t in ths]
        thr = float(ths[int(np.argmax(f1s))])
        mdl.fit(X[mask_treino], y[mask_treino])
        p = mdl.predict_proba(X[teste])[:, 1]
        yhat = (p >= thr).astype(int)
        pr, rc, f1, _ = precision_recall_fscore_support(
            y[teste], yhat, average="binary", zero_division=0)
        out[algo] = {
            "precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3),
            "pr_auc": round(average_precision_score(y[teste], p), 3),
            "roc_auc": round(roc_auc_score(y[teste], p), 3),
            "alertas": int(yhat.sum()),
        }
        print(f"{nome} · {algo}: {out[algo]}")
    return out


res_stf = avalia("só-STF   ", tr_stf)
res_multi = avalia("multi    ", tr_multi)

# baseline heurístico no mesmo teste
def heuristica(r):
    pts = 1.0
    cap, val = num(r, "capital_social"), num(r, "valor_global")
    razao = cap / val if (not np.isnan(cap)) and val else np.nan
    if np.isnan(cap) or cap == 0:
        pts += 0.3
    elif not np.isnan(razao) and razao < 0.02:
        pts += 1.2
    elif not np.isnan(razao) and razao > 0.3:
        pts -= 0.5
    idade = num(r, "idade_forn_anos")
    if not np.isnan(idade):
        pts += 0.8 if idade < 3 else (-0.4 if idade > 10 else 0)
    if num(r, "situacao_ativa") == 0:
        pts += 1.5
    dur = num(r, "duracao_dias")
    if not np.isnan(dur) and dur > 360:
        pts += 0.4
    return pts

vals_tr = np.array([num(r, "valor_global") for r in rows])[tr_stf]
quintis = np.nanpercentile(vals_tr, [20, 40, 60, 80])
imp_i = 1 + np.searchsorted(quintis, [num(r, "valor_global") for r in rows])
prob_i = np.clip(np.round([heuristica(r) for r in rows]), 1, 5)
heur_alto = ((prob_i * imp_i) > 9).astype(int)
heur_prob = (prob_i * imp_i) / 25
prh, rch, f1h, _ = precision_recall_fscore_support(
    y[teste], heur_alto[teste], average="binary", zero_division=0)
res_heur = {"precision": round(prh, 3), "recall": round(rch, 3), "f1": round(f1h, 3),
            "pr_auc": round(average_precision_score(y[teste], heur_prob[teste]), 3),
            "roc_auc": round(roc_auc_score(y[teste], heur_prob[teste]), 3),
            "alertas": int(heur_alto[teste].sum())}
print(f"baseline heurístico: {res_heur}")

# ------------------------------------------------------------------ relatório
def linha(nome, m):
    return (f"| {nome} | {m['precision']} | {m['recall']} | {m['f1']} | "
            f"{m['pr_auc']} | {m['roc_auc']} | {m['alertas']} |")

rel = f"""# ANTECIPA — Só STF × Multi-órgão (teste comum: STF 2025)

Experimento que testa a fragilidade 2.2 da análise crítica: *"cinco anos de
histórico de um único órgão pode ser insuficiente para treinar sem overfitting"*.

**Conjunto de teste (idêntico para todos)**: contratos do STF assinados em 2025
— {teste.sum()} contratos, {y[teste].sum()} com desfecho adverso
({y[teste].mean()*100:.1f}%).

| Treino | Contratos | Adversos |
|---|---|---|
| Só STF (2023–24) | {tr_stf.sum()} | {y[tr_stf].sum()} |
| Multi-órgão, 11 órgãos (2023–24) | {tr_multi.sum()} | {y[tr_multi].sum()} |

## Métricas no teste STF/2025

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC | Alertas |
|---|---|---|---|---|---|---|
{linha('Só STF · Regressão Logística', res_stf['LogReg'])}
{linha('Só STF · Gradient Boosting', res_stf['GradBoost'])}
{linha('Multi-órgão · Regressão Logística', res_multi['LogReg'])}
{linha('Multi-órgão · Gradient Boosting', res_multi['GradBoost'])}
{linha('Baseline heurístico (Res. 781)', res_heur)}

Prevalência no teste (PR-AUC de um classificador aleatório):
{round(float(y[teste].mean()), 3)}.

## Notas de leitura

- Com ~{tr_stf.sum()} contratos e só {y[tr_stf].sum()} positivos no treino
  só-STF, o limiar e as métricas são instáveis (alta variância) — qualquer
  ranking deve ser lido com cautela; PR-AUC e ROC-AUC (independentes de limiar)
  são as colunas mais informativas.
- O teste tem apenas {y[teste].sum()} positivos: diferenças pequenas de PR-AUC
  não são estatisticamente conclusivas; diferenças grandes e consistentes entre
  os dois algoritmos, sim.
- O modelo multi-órgão vê o "padrão do Judiciário federal" (inclusive o próprio
  STF 2023–24) e por isso tende a generalizar melhor — é a recomendação nº 2 da
  análise crítica em ação.
"""
(PROC / "comparacao_stf_vs_multi.md").write_text(rel, encoding="utf-8")
print("\nRelatório: dados/processados/comparacao_stf_vs_multi.md")
