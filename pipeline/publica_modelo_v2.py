# -*- coding: utf-8 -*-
"""
ANTECIPA — Publicação do modelo v2 (horizonte 12 meses) CALIBRADO para o dashboard.

* Probabilidade exibida: Gradient Boosting dentro de CalibratedClassifierCV
  (isotônica, 5 folds) — as porcentagens são frequências reais, desfazendo a
  distorção do class_weight.
* Explicações: valores SHAP (TreeExplainer) calculados sobre o PRÓPRIO Gradient
  Boosting, e não mais sobre uma regressão logística substituta. A troca foi
  motivada por evidência: a comparação em compara_explicacoes.py mostrou que o
  fator principal da logística coincidia com o do GB em apenas 12,3% dos
  contratos (Spearman médio 0,222), porque contribuições de variáveis one-hot
  são constantes e dominavam a explicação sem discriminar nada.

Nota de fidelidade: o SHAP explica o GB ajustado sobre toda a base de treino,
enquanto a probabilidade vem do mesmo algoritmo calibrado em 5 partições. O
script mede e reporta a concordância entre os dois escores (Spearman); como a
calibração é monotônica, direção e importância relativa dos fatores são
preservadas.

Saída: dados/processados/ml_stf_v2.json (o ml_stf.json da v1 é preservado).
"""
import csv
import json
import math
from pathlib import Path

import numpy as np
import shap
from scipy.stats import spearmanr
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
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


def faz_pre():
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), list(range(n_num))),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
         list(range(n_num, n_num + len(CAT_COLS)))),
    ])


def faz_gb():
    return HistGradientBoostingClassifier(
        random_state=42, class_weight="balanced", max_depth=4,
        learning_rate=0.08, max_iter=250, l2_regularization=1.0)


treino = le("dataset_ml_multi_v2.csv")
stf_rows = [r for r in le("dataset_ml_multi.csv") if r["orgao"] == "STF"]
X_tr, X_stf = monta_X(treino), monta_X(stf_rows)
y_tr = np.array([int(r["label_adverso_12m"]) for r in treino])
print(f"treino (elegíveis v2): {len(treino)} contratos, {y_tr.sum()} adversos · STF: {len(stf_rows)}")

# ---------------------------------------------- probabilidade calibrada
cal = CalibratedClassifierCV(Pipeline([("pre", faz_pre()), ("clf", faz_gb())]),
                             method="isotonic", cv=5)
cal.fit(X_tr, y_tr)
p_stf = cal.predict_proba(X_stf)[:, 1]
print(f"probabilidade calibrada — mediana {np.median(p_stf)*100:.1f}%, máx {p_stf.max()*100:.1f}%")

# ---------------------------------------------- SHAP sobre o próprio GB
pre = faz_pre()
Xt_tr = pre.fit_transform(X_tr)
Xt_tr = Xt_tr.toarray() if hasattr(Xt_tr, "toarray") else Xt_tr
Xt_stf = pre.transform(X_stf)
Xt_stf = Xt_stf.toarray() if hasattr(Xt_stf, "toarray") else Xt_stf

gb = faz_gb()
gb.fit(Xt_tr, y_tr)
print("calculando SHAP (TreeExplainer)...")
sv = shap.TreeExplainer(gb).shap_values(Xt_stf)
if isinstance(sv, list):
    sv = sv[1]
if np.ndim(sv) == 3:
    sv = sv[:, :, 1]
shap_vals = np.asarray(sv)

# fidelidade: o GB explicado ordena os contratos como o calibrado?
rho = spearmanr(gb.decision_function(Xt_stf), p_stf).statistic
print(f"concordância de ordenação GB explicado × modelo calibrado: Spearman {rho:.4f}")

imp = pre.named_transformers_["num"].named_steps["imp"]
NOMES = ([n for n, _ in NUM_DEFS]
         + [f"faltante: {NUM_DEFS[i][0]}" for i in imp.indicator_.features_]
         + list(pre.named_transformers_["cat"].get_feature_names_out(CAT_COLS)))

# Agregação dos one-hot: o SHAP atribui valor a TODOS os níveis de uma variável
# categórica, inclusive aos que valem zero (ex.: "orgao_TSE" num contrato do
# STF, que mede a contribuição de NÃO ser do TSE). Exibir isso confunde o leitor.
# A prática correta é somar as contribuições dos níveis de uma mesma variável
# original e rotular com o valor que o contrato de fato assume.
GRUPOS = {c: [j for j, n in enumerate(NOMES) if n.startswith(f"{c}_")] for c in CAT_COLS}
ROTULO_GRUPO = {"orgao": "órgão", "categoria": "categoria", "porte": "porte do fornecedor"}
idx_simples = [j for j, n in enumerate(NOMES)
               if not any(n.startswith(f"{c}_") for c in CAT_COLS)]

ml = {}
for i, r in enumerate(stf_rows):
    itens = [(NOMES[j], float(shap_vals[i][j])) for j in idx_simples]
    for col, cols_idx in GRUPOS.items():
        if not cols_idx:
            continue
        total = float(shap_vals[i][cols_idx].sum())
        valor = (r.get(col) or "?").strip() or "?"
        itens.append((f"{ROTULO_GRUPO[col]}: {valor}", total))
    itens.sort(key=lambda t: -abs(t[1]))
    ml[r["pncp"]] = {
        "prob": round(float(p_stf[i]), 3),
        "fatores": [[n, round(v, 2)] for n, v in itens[:5] if abs(v) > 0.03],
    }

(PROC / "ml_stf_v2.json").write_text(json.dumps({
    "modelo": "Gradient Boosting v2 · calibração isotônica",
    "treinado_em": "16.783 contratos elegíveis de 11 órgãos do Judiciário federal "
                   "(2022–2025), rótulo de desfecho adverso em 12 meses",
    "explicacao": "valores SHAP (TreeExplainer) sobre o próprio Gradient Boosting",
    "fidelidade_shap_spearman": round(float(rho), 4),
    "contratos": ml}, ensure_ascii=False), encoding="utf-8")
print("ml_stf_v2.json publicado — explicações agora por SHAP sobre o modelo em uso")
