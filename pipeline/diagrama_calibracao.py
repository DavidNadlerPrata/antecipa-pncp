# -*- coding: utf-8 -*-
"""
ANTECIPA — Diagrama de confiabilidade (curva de calibração).

Evidência visual de que a calibração isotônica funciona: compara, no conjunto
de TESTE TEMPORAL (contratos assinados em 2025, nunca vistos no treino), a
probabilidade prevista com a frequência de desfecho adverso efetivamente
observada — antes e depois da calibração.

Um modelo perfeitamente calibrado fica sobre a diagonal: entre os contratos aos
quais atribuiu 20%, exatamente 20% tiveram desfecho adverso.

Métricas reportadas:
  Brier score — erro quadrático médio da probabilidade (menor é melhor);
  ECE (Expected Calibration Error) — desvio médio absoluto entre probabilidade
       prevista e frequência observada, ponderado pelo nº de contratos no bin.

Saídas em dados/processados/:
  diagrama_calibracao.png   figura para a dissertação
  calibracao_metricas.json  números por bin e métricas agregadas
"""
import csv
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import brier_score_loss, roc_auc_score, average_precision_score
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

tr, te = ano <= 2024, ano == 2025
print(f"treino ≤2024: {tr.sum()} ({y[tr].mean()*100:.1f}% adversos) | "
      f"teste 2025: {te.sum()} ({y[te].mean()*100:.1f}% adversos)")


def faz_gb():
    pre = ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True)),
                          ("sc", StandardScaler())]), list(range(n_num))),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=5),
         list(range(n_num, n_num + len(CAT_COLS)))),
    ])
    return Pipeline([("pre", pre), ("clf", HistGradientBoostingClassifier(
        random_state=42, class_weight="balanced", max_depth=4,
        learning_rate=0.08, max_iter=250, l2_regularization=1.0))])


print("treinando modelo sem calibração...")
bruto = faz_gb()
bruto.fit(X[tr], y[tr])
p_bruto = bruto.predict_proba(X[te])[:, 1]

print("treinando modelo com calibração isotônica (5 folds)...")
cal = CalibratedClassifierCV(faz_gb(), method="isotonic", cv=5)
cal.fit(X[tr], y[tr])
p_cal = cal.predict_proba(X[te])[:, 1]


def ece(y_true, p, n_bins=10):
    """Expected Calibration Error com bins de igual frequência (quantis)."""
    qs = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    idx = np.clip(np.digitize(p, qs[1:-1]), 0, len(qs) - 2)
    tot, err = 0.0, 0.0
    for b in range(len(qs) - 1):
        m = idx == b
        if m.sum() == 0:
            continue
        err += m.sum() * abs(p[m].mean() - y_true[m].mean())
        tot += m.sum()
    return err / max(tot, 1)


metricas = {}
for nome, p in [("sem calibração", p_bruto), ("calibrado (isotônica)", p_cal)]:
    metricas[nome] = {
        "brier": round(float(brier_score_loss(y[te], p)), 5),
        "ece": round(float(ece(y[te], p)), 5),
        "roc_auc": round(float(roc_auc_score(y[te], p)), 4),
        "pr_auc": round(float(average_precision_score(y[te], p)), 4),
        "prob_media": round(float(p.mean()), 4),
        "prob_max": round(float(p.max()), 4),
    }
    print(f"{nome:24} Brier={metricas[nome]['brier']:.5f}  ECE={metricas[nome]['ece']:.5f}  "
          f"ROC-AUC={metricas[nome]['roc_auc']:.4f}  média={metricas[nome]['prob_media']:.3f}")
prev = float(y[te].mean())
print(f"{'frequência real (base)':24} {prev:.4f}")

# ------------------------------------------------------------------- figura
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})
fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.3))
cores = {"sem calibração": "#e34948", "calibrado (isotônica)": "#1c5cab"}
curvas = {}
for nome, p in [("sem calibração", p_bruto), ("calibrado (isotônica)", p_cal)]:
    fo, mp = calibration_curve(y[te], p, n_bins=10, strategy="quantile")
    curvas[nome] = (mp, fo)
    metricas[nome]["curva"] = {"prob_media_bin": [round(float(v), 4) for v in mp],
                               "freq_observada_bin": [round(float(v), 4) for v in fo]}

# --- painel 1: escala completa (mostra o quanto o modelo bruto se afasta) ---
ax = axes[0]
ax.plot([0, 1], [0, 1], "--", color="#898781", lw=1, label="calibração perfeita")
for nome, (mp, fo) in curvas.items():
    ax.plot(mp, fo, "o-", color=cores[nome], lw=1.6, ms=4.5,
            label=f"{nome} (ECE {metricas[nome]['ece']:.3f})")
ax.axhline(prev, color="#0ca30c", lw=1, ls=":", label=f"prevalência real ({prev*100:.1f}%)")
ax.set_xlabel("Probabilidade média prevista")
ax.set_ylabel("Frequência observada de desfecho adverso")
ax.set_title("(a) Escala completa", fontsize=10, fontweight="bold")
ax.legend(frameon=False, fontsize=7.5, loc="upper left")
ax.grid(alpha=.25, lw=.6)
ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.02, 1.02)

# --- painel 2: zoom na faixa onde ficam as probabilidades calibradas ---
lim = max(0.25, float(p_cal.max()) * 1.15)
ax = axes[1]
ax.plot([0, lim], [0, lim], "--", color="#898781", lw=1, label="calibração perfeita")
for nome, (mp, fo) in curvas.items():
    m = mp <= lim
    ax.plot(mp[m], fo[m], "o-", color=cores[nome], lw=1.8, ms=5, label=nome)
ax.axhline(prev, color="#0ca30c", lw=1, ls=":", label=f"prevalência real ({prev*100:.1f}%)")
ax.set_xlabel("Probabilidade média prevista")
ax.set_ylabel("Frequência observada")
ax.set_title(f"(b) Zoom em 0–{lim:.2f} — faixa do modelo calibrado", fontsize=10, fontweight="bold")
ax.legend(frameon=False, fontsize=7.5, loc="upper left")
ax.grid(alpha=.25, lw=.6)
ax.set_xlim(-0.005, lim); ax.set_ylim(-0.005, lim)

ax = axes[2]
bins = np.linspace(0, 1, 41)
ax.hist(p_bruto, bins=bins, alpha=.6, color=cores["sem calibração"], label="sem calibração")
ax.hist(p_cal, bins=bins, alpha=.75, color=cores["calibrado (isotônica)"], label="calibrado")
ax.axvline(prev, color="#0ca30c", lw=1, ls=":", label="prevalência real")
ax.set_yscale("log")
ax.set_xlabel("Probabilidade prevista")
ax.set_ylabel("Nº de contratos (escala log)")
ax.set_title("(c) Distribuição das probabilidades", fontsize=10, fontweight="bold")
ax.legend(frameon=False, fontsize=8)
ax.grid(alpha=.25, lw=.6)

fig.suptitle("ANTECIPA — efeito da calibração isotônica sobre as probabilidades do modelo",
             fontsize=11, fontweight="bold", y=1.0)
fig.tight_layout()
out_png = PROC / "diagrama_calibracao.png"
fig.savefig(out_png, dpi=200, bbox_inches="tight")
print(f"\nfigura: {out_png.name}")

metricas["_prevalencia_teste"] = round(prev, 5)
metricas["_n_teste"] = int(te.sum())
(PROC / "calibracao_metricas.json").write_text(
    json.dumps(metricas, ensure_ascii=False, indent=1), encoding="utf-8")
print("métricas: calibracao_metricas.json")
