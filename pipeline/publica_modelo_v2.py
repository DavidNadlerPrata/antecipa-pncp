# -*- coding: utf-8 -*-
"""
ANTECIPA — Publicação do modelo v2 (horizonte 12 meses) CALIBRADO para o dashboard.

* Treina o Gradient Boosting v2 em todos os contratos elegíveis (2022–2025,
  rótulo de 12 meses) dentro de CalibratedClassifierCV (isotônica, 5 folds):
  as probabilidades exibidas passam a ser frequências reais, desfazendo a
  distorção do class_weight.
* Pontua TODOS os contratos do STF (inclusive os recentes, não elegíveis para
  treino — prever é justamente o caso de uso deles) com features idênticas às
  do treino, lidas do dataset v1.
* Explicações: contribuições em log-odds da regressão logística v2.

Saída: dados/processados/ml_stf_v2.json (o ml_stf.json da v1 é preservado).
"""
import csv
import json
import math
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"

def le(nome):
    with open(PROC / nome, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

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

def monta_X(rows):
    Xn = np.array([[f(r) for _, f in NUM_DEFS] for r in rows], dtype=float)
    Xc = np.array([[r[c] or "?" for c in CAT_COLS] for r in rows], dtype=object)
    return np.concatenate([Xn, Xc], axis=1).astype(object)

treino = le("dataset_ml_multi_v2.csv")
X_tr = monta_X(treino)
y_tr = np.array([int(r["label_adverso_12m"]) for r in treino])
print(f"treino (elegíveis v2): {len(treino)} contratos, {y_tr.sum()} adversos")

def faz_pre():
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), list(range(n_num))),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
         list(range(n_num, n_num + len(CAT_COLS)))),
    ])

gb = Pipeline([("pre", faz_pre()), ("clf", HistGradientBoostingClassifier(
    random_state=42, class_weight="balanced", max_depth=4,
    learning_rate=0.08, max_iter=250, l2_regularization=1.0))])
cal = CalibratedClassifierCV(gb, method="isotonic", cv=5)
cal.fit(X_tr, y_tr)

lr = Pipeline([("pre", faz_pre()), ("clf", LogisticRegression(
    max_iter=5000, class_weight="balanced", C=0.5))])
lr.fit(X_tr, y_tr)

# ------------------------------------------------- pontua todos os contratos STF
stf_rows = [r for r in le("dataset_ml_multi.csv") if r["orgao"] == "STF"]
X_stf = monta_X(stf_rows)
p_stf = cal.predict_proba(X_stf)[:, 1]
print(f"STF pontuado: {len(stf_rows)} contratos · prob calibrada mediana "
      f"{np.median(p_stf)*100:.1f}%, máx {p_stf.max()*100:.1f}%")

Xt = lr.named_steps["pre"].transform(X_stf)
Xt = Xt.toarray() if hasattr(Xt, "toarray") else Xt
coefs = lr.named_steps["clf"].coef_[0]
contrib = Xt * coefs
imp = lr.named_steps["pre"].named_transformers_["num"].named_steps["imp"]
nomes = [n for n, _ in NUM_DEFS] + \
    [f"faltante: {NUM_DEFS[i][0]}" for i in imp.indicator_.features_] + \
    list(lr.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(CAT_COLS))

ml = {}
for i, r in enumerate(stf_rows):
    ordem = np.argsort(-np.abs(contrib[i]))[:5]
    ml[r["pncp"]] = {
        "prob": round(float(p_stf[i]), 3),
        "fatores": [[nomes[j], round(float(contrib[i][j]), 2)]
                    for j in ordem if abs(contrib[i][j]) > 0.05],
    }
(PROC / "ml_stf_v2.json").write_text(json.dumps({
    "modelo": "Gradient Boosting v2 · calibração isotônica",
    "treinado_em": "16.783 contratos elegíveis de 11 órgãos do Judiciário federal "
                   "(2022–2025), rótulo de desfecho adverso em 12 meses",
    "explicacao": "contribuições aditivas em log-odds da regressão logística v2",
    "contratos": ml}, ensure_ascii=False), encoding="utf-8")
print("ml_stf_v2.json publicado (probabilidades calibradas — % = frequência real)")
