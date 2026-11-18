# -*- coding: utf-8 -*-
"""
ANTECIPA — Métricas de alerta na carteira do STF (base da seção "a matriz
ex-ante não discrimina" do relatório e do RESULTADOS.md).

Aplica cada critério de alerta aos contratos do STF e mede, contra o desfecho
real observado ("adverso a qualquer momento" — rótulo do dashboard), quantos
alertas cada um emite, quantos acerta, precisão, recall e lift sobre a taxa base.
Todas as leituras usam a escala OFICIAL da Res. STF 781/2022 (escala_781.py).

ATENÇÃO na leitura: (i) os contratos do STF integraram o treino do modelo, então
os números do ML aqui são otimistas — a medição fora da amostra está em
relatorio_modelo_v2.md; (ii) a leitura "observado" usa o próprio desfecho, logo é
circular e serve só de referência.

Requer dados/processados/antecipa_dados.json (rodar processa.py antes).
Saídas: dados/processados/metricas_carteira_stf.{json,md}
"""
import json
from collections import Counter
from pathlib import Path

import escala_781 as E

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "dados" / "processados"
d = json.loads((PROC / "antecipa_dados.json").read_text(encoding="utf-8"))
ps = d["processos"]
adv = lambda p: bool(p["desfecho"]["desfecho_adverso"])
n_adv = sum(adv(p) for p in ps)
base = n_adv / len(ps)

FAIXAS_ML = [(0.02, 1), (0.05, 2), (0.10, 3), (0.20, 4), (9.0, 5)]   # = dashboard
nivel_ml_pos = lambda pr: next(i for mx, i in FAIXAS_ML if pr < mx)
pontos_ex = lambda p: 1.0 + sum(f[1] for f in p["fatores"]
                                if len(f) > 2 and f[2] and f[1] is not None)


def mede(nome, sel):
    sel = list(sel)
    ac = sum(adv(p) for p in sel)
    prec = ac / len(sel) if sel else None
    return {"criterio": nome, "alertas": len(sel), "acertos": ac,
            "precisao": round(prec, 4) if prec is not None else None,
            "recall": round(ac / n_adv, 4),
            "lift": round(prec / base, 2) if prec is not None else None}


com_ml = [p for p in ps if p.get("ml")]
ml_nivel = {p["pncp"]: E.nivel(nivel_ml_pos(p["ml"]["prob"]), p["imp"]) for p in com_ml}
ord_ml = sorted(com_ml, key=lambda p: -p["ml"]["prob"])
ord_ex = sorted(ps, key=lambda p: (-p["score_ex"], -pontos_ex(p)))

linhas = [
    mede("Ex-ante (Res. 781) — Elevado/Crítico", (p for p in ps if p["nivel_ex"] in E.ALTOS)),
    mede("Ex-ante (Res. 781) — Moderado ou acima", (p for p in ps if p["nivel_ex"] != "Baixo")),
    mede("Matriz ML — Elevado/Crítico", (p for p in com_ml if ml_nivel[p["pncp"]] in E.ALTOS)),
    mede("Matriz ML — só Crítico", (p for p in com_ml if ml_nivel[p["pncp"]] == "Crítico")),
    mede("ML ≥ 20%", (p for p in com_ml if p["ml"]["prob"] >= 0.20)),
    mede("ML ≥ 10%", (p for p in com_ml if p["ml"]["prob"] >= 0.10)),
    mede("ML ≥ 5%", (p for p in com_ml if p["ml"]["prob"] >= 0.05)),
]
for k in (50, 100):
    linhas.append(mede(f"Ex-ante top-{k} (risco inerente + pontos)", ord_ex[:k]))
    linhas.append(mede(f"ML top-{k} (probabilidade)", ord_ml[:k]))
linhas.append(mede("(referência, circular) Observado — Elevado/Crítico",
                   (p for p in ps if p["nivel"] in E.ALTOS)))

dist = {
    "ex-ante": Counter(p["nivel_ex"] for p in ps),
    "ML (matriz)": Counter(ml_nivel.values()),
    "observado": Counter(p["nivel"] for p in ps),
}
alvo = next((p for p in ps if p["id"] == "010294/2023"), None)
R = d["resumo"]
saida = {
    "n_contratos": len(ps), "n_adversos": n_adv, "taxa_base": round(base, 4),
    "escala": "Res. STF 781/2022 — níveis 1-2-5-8-10, risco inerente 0–100",
    "distribuicao": {k: dict(v) for k, v in dist.items()},
    "criterios": linhas,
    "contrato_010294_2023": None if not alvo else {
        "ex_ante": [alvo["nivel_ex"], alvo["score_ex"]],
        "observado": [alvo["nivel"], alvo["score"]],
        "ml_prob": alvo["ml"]["prob"] if alvo.get("ml") else None,
        "ml_matriz": ml_nivel.get(alvo["pncp"]),
    },
    "sancoes": {k: R.get(k) for k in ("sancoes_consulta", "fornecedores_verificados",
                                      "fornecedores_com_registro",
                                      "contratos_sancao_na_assinatura")},
}
(PROC / "metricas_carteira_stf.json").write_text(
    json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")

pct = lambda v: "—" if v is None else f"{v*100:.1f} %".replace(".", ",")
lx = lambda v: "—" if v is None else f"{v:.2f}×".replace(".", ",")
md = [f"# ANTECIPA — Critérios de alerta na carteira do STF\n",
      f"{len(ps)} contratos · {n_adv} com desfecho adverso · taxa base {pct(base)} · "
      f"escala oficial da Res. STF 781/2022 (risco inerente 0–100).\n",
      "| Critério | Alertas | Acertos | Precisão | Recall | Lift |", "|---|---|---|---|---|---|"]
for l in linhas:
    md.append(f"| {l['criterio']} | {l['alertas']} | {l['acertos']} | {pct(l['precisao'])} | "
              f"{pct(l['recall'])} | {lx(l['lift'])} |")
md.append("\n## Distribuição por nível\n\n| Leitura | Baixo | Moderado | Elevado | Crítico |\n|---|---|---|---|---|")
for k, v in dist.items():
    md.append(f"| {k} | {v['Baixo']} | {v['Moderado']} | {v['Elevado']} | {v['Crítico']} |")
md.append("\nNúmeros do ML otimistas (contratos do STF no treino); a leitura observada é "
          "circular (usa o desfecho). Ver RESULTADOS.md.")
(PROC / "metricas_carteira_stf.md").write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"taxa base {base*100:.1f}% · {len(ps)} contratos")
for l in linhas:
    print(f"  {l['criterio']:52} alertas={l['alertas']:4} acertos={l['acertos']:3} "
          f"prec={pct(l['precisao']):>7} rec={pct(l['recall']):>7} lift={lx(l['lift'])}")
print("distribuição:", {k: dict(v) for k, v in dist.items()})
print("010294/2023:", saida["contrato_010294_2023"])
print("sanções:", saida["sancoes"])
