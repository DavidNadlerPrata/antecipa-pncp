# -*- coding: utf-8 -*-
"""
ANTECIPA — SHAP (Gradient Boosting) × contribuições da Regressão Logística.

Compara, para os MESMOS contratos e no MESMO espaço de variáveis, as duas
formas de explicar a predição:

  (A) SHAP sobre o Gradient Boosting — atribuições exatas do modelo que de fato
      decide (é o que o projeto de qualificação prometia);
  (B) contribuições aditivas (log-odds) da Regressão Logística — o modelo
      substituto interpretável hoje exibido no dashboard.

Ambos os modelos são ajustados sobre a MESMA matriz pré-processada, de modo que
as atribuições sejam comparáveis variável a variável.

Saídas em dados/processados/:
  comparacao_explicacoes.png   figura com contratos lado a lado
  comparacao_explicacoes.md    tabelas + métricas de concordância
"""
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import shap
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"

with open(PROC / "dataset_ml_multi_v2.csv", encoding="utf-8") as fh:
    treino_rows = list(csv.DictReader(fh))
with open(PROC / "dataset_ml_multi.csv", encoding="utf-8") as fh:
    stf_rows = [r for r in csv.DictReader(fh) if r["orgao"] == "STF"]


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


X_tr, X_stf = monta_X(treino_rows), monta_X(stf_rows)
y_tr = np.array([int(r["label_adverso_12m"]) for r in treino_rows])

# pré-processamento comum aos dois modelos -> mesmo espaço de variáveis
pre = ColumnTransformer([
    ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                      ("sc", StandardScaler())]), list(range(n_num))),
    ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
     list(range(n_num, n_num + len(CAT_COLS)))),
])
Xt_tr = pre.fit_transform(X_tr)
Xt_tr = Xt_tr.toarray() if hasattr(Xt_tr, "toarray") else Xt_tr
Xt_stf = pre.transform(X_stf)
Xt_stf = Xt_stf.toarray() if hasattr(Xt_stf, "toarray") else Xt_stf

imp = pre.named_transformers_["num"].named_steps["imp"]
NOMES = ([n for n, _ in NUM_DEFS]
         + [f"faltante: {NUM_DEFS[i][0]}" for i in imp.indicator_.features_]
         + list(pre.named_transformers_["cat"].get_feature_names_out(CAT_COLS)))


def bonito(nome):
    if nome.startswith("orgao_"):
        return f"órgão: {nome[6:]}"
    if nome.startswith("categoria_"):
        return f"categoria: {nome[10:]}"
    if nome.startswith("porte_"):
        return f"porte: {nome[6:].replace('DEMAIS', 'demais/grande').replace('_', ' ').lower()}"
    if nome.startswith("faltante: "):
        return f"dado ausente ({nome[10:]})"
    return nome


NOMES_B = [bonito(n) for n in NOMES]
print(f"treino: {Xt_tr.shape[0]} contratos × {Xt_tr.shape[1]} variáveis · STF: {Xt_stf.shape[0]}")

gb = HistGradientBoostingClassifier(random_state=42, class_weight="balanced", max_depth=4,
                                    learning_rate=0.08, max_iter=250, l2_regularization=1.0)
gb.fit(Xt_tr, y_tr)
lr = LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5)
lr.fit(Xt_tr, y_tr)

print("calculando SHAP (TreeExplainer) sobre o Gradient Boosting...")
expl = shap.TreeExplainer(gb)
sv = expl.shap_values(Xt_stf)
if isinstance(sv, list):          # algumas versões devolvem lista por classe
    sv = sv[1]
if sv.ndim == 3:                  # (n, features, classes)
    sv = sv[:, :, 1]
shap_vals = np.asarray(sv)
lr_vals = Xt_stf * lr.coef_[0]    # contribuição aditiva exata em log-odds
print(f"SHAP: {shap_vals.shape} · logística: {lr_vals.shape}")

# ------------------------------------------------------- concordância global
rhos, top1, top3 = [], [], []
for i in range(len(stf_rows)):
    a, b = shap_vals[i], lr_vals[i]
    if np.allclose(a, 0) or np.allclose(b, 0):
        continue
    rhos.append(spearmanr(a, b).statistic)
    ta = set(np.argsort(-np.abs(a))[:3])
    tb = set(np.argsort(-np.abs(b))[:3])
    top1.append(int(np.argmax(np.abs(a)) == np.argmax(np.abs(b))))
    top3.append(len(ta & tb) / 3)
concord = {
    "spearman_medio": round(float(np.mean(rhos)), 3),
    "spearman_mediano": round(float(np.median(rhos)), 3),
    "pct_mesmo_fator_principal": round(100 * float(np.mean(top1)), 1),
    "sobreposicao_media_top3": round(100 * float(np.mean(top3)), 1),
    "n_contratos": len(rhos),
}
print("concordância:", concord)

# importância global média |contribuição|
imp_shap = np.abs(shap_vals).mean(axis=0)
imp_lr = np.abs(lr_vals).mean(axis=0)

# ------------------------------------------------------------------ figura
alvos = []
ids = [r["pncp"] for r in stf_rows]
proc_ids = {}
try:
    dados = json.loads((PROC / "antecipa_dados.json").read_text(encoding="utf-8"))
    proc_ids = {p["pncp"]: p["id"] for p in dados["processos"]}
except Exception:
    pass
p_gb = gb.predict_proba(Xt_stf)[:, 1]
# contrato discutido + o de maior e o de menor escore
alvo_ids = [i for i, r in enumerate(stf_rows) if proc_ids.get(r["pncp"]) == "010294/2023"]
alvos = (alvo_ids[:1] + [int(np.argmax(p_gb))] + [int(np.argmin(p_gb))])[:3]

fig, axes = plt.subplots(len(alvos), 2, figsize=(13, 3.1 * len(alvos)))
plt.rcParams.update({"font.size": 9})
if len(alvos) == 1:
    axes = np.array([axes])
for lin, idx in enumerate(alvos):
    rot = proc_ids.get(stf_rows[idx]["pncp"], stf_rows[idx]["pncp"])
    for col, (titulo, vals, cor_pos, cor_neg) in enumerate([
            ("SHAP · Gradient Boosting", shap_vals[idx], "#e34948", "#2a78d6"),
            ("Contribuições · Regressão Logística", lr_vals[idx], "#eb6834", "#1baf7a")]):
        ax = axes[lin, col]
        ordem = np.argsort(-np.abs(vals))[:7][::-1]
        v = vals[ordem]
        ax.barh(range(len(ordem)), v, color=[cor_pos if x > 0 else cor_neg for x in v])
        ax.set_yticks(range(len(ordem)))
        ax.set_yticklabels([NOMES_B[j][:38] for j in ordem], fontsize=7.5)
        ax.axvline(0, color="#898781", lw=.8)
        ax.set_title(f"{rot} — {titulo}", fontsize=9, fontweight="bold")
        ax.tick_params(axis="x", labelsize=7.5)
        ax.grid(axis="x", alpha=.25, lw=.6)
fig.suptitle("ANTECIPA — a mesma predição explicada de duas formas "
             "(mesmos contratos, mesmas variáveis)", fontsize=11, fontweight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.97])
fig.savefig(PROC / "comparacao_explicacoes.png", dpi=200, bbox_inches="tight")
print("figura: comparacao_explicacoes.png")

# ------------------------------------------------------------------ markdown
def tabela_contrato(idx):
    rot = proc_ids.get(stf_rows[idx]["pncp"], stf_rows[idx]["pncp"])
    linhas = [f"\n### Contrato {rot} — probabilidade do GB: {p_gb[idx]*100:.1f}%\n",
              "| # | SHAP (Gradient Boosting) | valor | Regressão Logística | valor |",
              "|---|---|---|---|---|"]
    oa = np.argsort(-np.abs(shap_vals[idx]))[:5]
    ob = np.argsort(-np.abs(lr_vals[idx]))[:5]
    for k in range(5):
        linhas.append(f"| {k+1} | {NOMES_B[oa[k]]} | {shap_vals[idx][oa[k]]:+.2f} "
                      f"| {NOMES_B[ob[k]]} | {lr_vals[idx][ob[k]]:+.2f} |")
    return "\n".join(linhas)


ordem_g = np.argsort(-imp_shap)[:10]
md = f"""# ANTECIPA — SHAP (Gradient Boosting) × Regressão Logística

Comparação das duas formas de explicar a predição, para os **mesmos contratos do
STF** e no **mesmo espaço de variáveis** (ambos os modelos ajustados sobre a
mesma matriz pré-processada, {Xt_tr.shape[0]} contratos de treino).

- **SHAP sobre o Gradient Boosting**: atribuições do modelo que de fato produz a
  probabilidade exibida. Somadas ao valor-base, reconstroem exatamente a
  predição.
- **Contribuições da Regressão Logística**: exatas para *aquele* modelo linear,
  mas ele não é o modelo publicado — é substituto interpretável.

## Concordância entre as duas explicações

| Indicador | Valor |
|---|---|
| Correlação de Spearman média entre as atribuições | {concord['spearman_medio']} |
| Correlação mediana | {concord['spearman_mediano']} |
| Contratos em que o **fator principal coincide** | {concord['pct_mesmo_fator_principal']}% |
| Sobreposição média entre os 3 principais fatores | {concord['sobreposicao_media_top3']}% |
| Contratos analisados | {concord['n_contratos']} |

## Importância global (média de |contribuição|)

| Variável | SHAP (GB) | Reg. Logística |
|---|---|---|
""" + "\n".join(f"| {NOMES_B[j]} | {imp_shap[j]:.3f} | {imp_lr[j]:.3f} |" for j in ordem_g) + """

## Exemplos contrato a contrato
""" + "\n".join(tabela_contrato(i) for i in alvos) + f"""

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
"""
(PROC / "comparacao_explicacoes.md").write_text(md, encoding="utf-8")
(PROC / "comparacao_explicacoes.json").write_text(
    json.dumps({"concordancia": concord}, ensure_ascii=False, indent=1), encoding="utf-8")
print("relatório: comparacao_explicacoes.md")
