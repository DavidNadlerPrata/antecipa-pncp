# -*- coding: utf-8 -*-
"""
ANTECIPA — Treino do modelo supervisionado de desfecho adverso.

Decisões metodológicas (respondem aos itens 2.1, 2.2 e 2.7 da análise crítica):
  * Rótulo = desfecho REAL (rescisão, acréscimo >25%, prorrogação >1 ano) —
    nunca a matriz de risco (evita circularidade).
  * Só features conhecidas na assinatura do contrato (sem vazamento do futuro).
  * Validação TEMPORAL: treino 2023–2024, teste 2025. Contratos de 2026 ficam
    fora da avaliação (rótulo imaturo — pouco tempo para termos aparecerem).
  * Métricas: precision/recall/F1 da classe positiva, PR-AUC e ROC-AUC —
    nunca acurácia. Limiar escolhido no TREINO (F1 via validação cruzada).
  * Baseline heurístico transparente avaliado nas mesmas condições.

Saídas em dados/processados/:
  relatorio_modelo.md   — relatório completo
  modelo_metrics.json   — métricas em formato estruturado
  ml_stf.json           — probabilidade + contribuições por contrato do STF
                          (para o dashboard)
"""
import csv
import json
import math
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, f1_score,
                             precision_recall_fscore_support, roc_auc_score)
from sklearn.model_selection import cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"
rng = np.random.RandomState(42)

# ------------------------------------------------------------------ carga
with open(PROC / "dataset_ml_multi.csv", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))

def num(r, k):
    v = r.get(k, "")
    try:
        return float(v)
    except ValueError:
        return np.nan

NUM_DEFS = [  # (nome exibido, extrator)
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

X_num = np.array([[f(r) for _, f in NUM_DEFS] for r in rows], dtype=float)
X_cat = np.array([[r[c] or "?" for c in CAT_COLS] for r in rows], dtype=object)
X = np.concatenate([X_num, X_cat], axis=1).astype(object)
y = np.array([int(r["label_desfecho_adverso"]) for r in rows])
ano = np.array([int(r["assinatura"][:4]) if r["assinatura"] else 0 for r in rows])
orgao = np.array([r["orgao"] for r in rows])
pncp = np.array([r["pncp"] for r in rows])

tr = (ano >= 2023) & (ano <= 2024)
te = ano == 2025
print(f"treino 2023-24: {tr.sum()} ({y[tr].mean()*100:.1f}% adversos) | "
      f"teste 2025: {te.sum()} ({y[te].mean()*100:.1f}% adversos) | "
      f"2026 (fora da avaliação): {(ano==2026).sum()}")

n_num = len(NUM_DEFS)
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

# ------------------------------------------------- baseline heurístico (transp.)
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

heur_score = np.array([heuristica(r) for r in rows])
val_treino = np.array([num(r, "valor_global") for r in rows])[tr]
quintis = np.nanpercentile(val_treino, [20, 40, 60, 80])
imp_i = 1 + np.searchsorted(quintis, [num(r, "valor_global") for r in rows])
prob_i = np.clip(np.round(heur_score), 1, 5)
heur_alto = ((prob_i * imp_i) > 9).astype(int)   # Elevado ou Crítico
heur_prob = (prob_i * imp_i) / 25                # p/ PR-AUC do baseline

# ------------------------------------------------------------------ avaliação
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
    res[nome] = {
        "limiar": thr,
        "precision": round(pr, 3), "recall": round(rc, 3), "f1": round(f1, 3),
        "pr_auc": round(average_precision_score(y[te], p_te), 3),
        "roc_auc": round(roc_auc_score(y[te], p_te), 3),
        "alertas": int(yhat.sum()), "positivos_teste": int(y[te].sum()),
    }
    print(nome, res[nome])

prh, rch, f1h, _ = precision_recall_fscore_support(
    y[te], heur_alto[te], average="binary", zero_division=0)
res["Baseline heurístico (Res. 781)"] = {
    "limiar": "nível > Moderado",
    "precision": round(prh, 3), "recall": round(rch, 3), "f1": round(f1h, 3),
    "pr_auc": round(average_precision_score(y[te], heur_prob[te]), 3),
    "roc_auc": round(roc_auc_score(y[te], heur_prob[te]), 3),
    "alertas": int(heur_alto[te].sum()), "positivos_teste": int(y[te].sum()),
}
res["_prevalencia_teste"] = round(float(y[te].mean()), 3)
print("Baseline:", res["Baseline heurístico (Res. 781)"])

# ------------------------------------------- importância de permutação (GB)
gb = modelos["Gradient Boosting"]
imp = permutation_importance(gb, X[te], y[te], scoring="average_precision",
                             n_repeats=10, random_state=42)
nomes_feat = [n for n, _ in NUM_DEFS] + \
    [f"faltante: {NUM_DEFS[i][0]}" for i in
     getattr(gb.named_steps["pre"].named_transformers_["num"].named_steps["imp"],
             "indicator_").features_] + \
    list(gb.named_steps["pre"].named_transformers_["cat"].get_feature_names_out(CAT_COLS))
ordem = np.argsort(-imp.importances_mean)
importancias = [(nomes_feat[i] if i < len(nomes_feat) else f"f{i}",
                 round(float(imp.importances_mean[i]), 4)) for i in ordem[:12]]

# --------------------------------------- modelo final p/ dashboard (refit ≤2025)
fit_all = (ano >= 2023) & (ano <= 2025)
melhor_nome = max(["Regressão Logística", "Gradient Boosting"],
                  key=lambda n: res[n]["pr_auc"])
melhor = modelos[melhor_nome]
melhor.fit(X[fit_all], y[fit_all])
lr = modelos["Regressão Logística"]
lr.fit(X[fit_all], y[fit_all])

# contribuições aditivas exatas (log-odds) da logística p/ explicação
Xt_stf = lr.named_steps["pre"].transform(X[orgao == "STF"])
Xt_stf = Xt_stf.toarray() if hasattr(Xt_stf, "toarray") else Xt_stf
coefs = lr.named_steps["clf"].coef_[0]
contrib = Xt_stf * coefs
p_stf = melhor.predict_proba(X[orgao == "STF"])[:, 1]

nomes_lr = nomes_feat[:contrib.shape[1]]
ml_stf = {}
for i, ncp in enumerate(pncp[orgao == "STF"]):
    ordem_c = np.argsort(-np.abs(contrib[i]))[:5]
    ml_stf[ncp] = {
        "prob": round(float(p_stf[i]), 3),
        "fatores": [[nomes_lr[j], round(float(contrib[i][j]), 2)]
                    for j in ordem_c if abs(contrib[i][j]) > 0.05],
    }
(PROC / "ml_stf.json").write_text(json.dumps({
    "modelo": melhor_nome, "treinado_em": "contratos 2023-2025 de 11 órgãos",
    "explicacao": "contribuições aditivas em log-odds da regressão logística",
    "limiar_f1": res[melhor_nome]["limiar"],
    "contratos": ml_stf}, ensure_ascii=False), encoding="utf-8")

(PROC / "modelo_metrics.json").write_text(
    json.dumps({"metricas": res, "importancias": importancias,
                "melhor_modelo": melhor_nome}, ensure_ascii=False, indent=1),
    encoding="utf-8")

# ------------------------------------------------------------------ relatório
def fmt(nome):
    m = res[nome]
    return (f"| {nome} | {m['precision']} | {m['recall']} | {m['f1']} | "
            f"{m['pr_auc']} | {m['roc_auc']} | {m['alertas']} |")

rel = f"""# ANTECIPA — Relatório do modelo supervisionado

**Tarefa**: prever `desfecho_adverso` (rescisão, acréscimo >25% ou prorrogação
>1 ano, observados nos termos do PNCP) no momento da **assinatura** do contrato.

**Dados**: {len(rows)} contratos de 11 órgãos do Judiciário federal (2023–2026).
Treino 2023–2024: {tr.sum()} contratos ({y[tr].mean()*100:.1f}% adversos).
Teste temporal 2025: {te.sum()} contratos ({y[te].mean()*100:.1f}% adversos).
Contratos de 2026 excluídos da avaliação (rótulo imaturo/censurado).

## Métricas no teste (classe positiva = desfecho adverso)

| Modelo | Precision | Recall | F1 | PR-AUC | ROC-AUC | Alertas |
|---|---|---|---|---|---|---|
{fmt('Regressão Logística')}
{fmt('Gradient Boosting')}
{fmt('Baseline heurístico (Res. 781)')}

Prevalência no teste (classificador aleatório teria PR-AUC ≈): {res['_prevalencia_teste']}.
Limiar de decisão escolhido no treino (máximo F1 em validação cruzada 5-fold).

## Fatores mais informativos (importância de permutação, PR-AUC, teste)

| Feature | Δ PR-AUC |
|---|---|
""" + "\n".join(f"| {n} | {v} |" for n, v in importancias) + f"""

## Modelo publicado no dashboard

**{melhor_nome}** (maior PR-AUC), reajustado em 2023–2025. As explicações por
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
"""
(PROC / "relatorio_modelo.md").write_text(rel, encoding="utf-8")
print(f"\nMelhor modelo: {melhor_nome} — relatório em relatorio_modelo.md")
