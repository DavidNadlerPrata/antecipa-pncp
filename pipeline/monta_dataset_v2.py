# -*- coding: utf-8 -*-
"""
ANTECIPA — Dataset v2: rótulo com HORIZONTE FIXO de 12 meses (censura corrigida).

Diferenças em relação ao monta_dataset.py (v1, mantido intacto):

  * label_adverso_12m = evento adverso ocorrido em até 365 dias da assinatura,
    datado pelo dataAssinatura de cada termo:
      - termo de rescisão/extinção assinado na janela; OU
      - soma de valorAcrescido dos termos da janela > 25% do valor inicial; OU
      - prorrogação concedida na janela > 365 dias.
  * Elegibilidade: só contratos com >= 12 meses de observação
    (assinados até HOJE - 365d). Coortes ficam comparáveis entre si e a
    prevalência deixa de cair artificialmente nos anos recentes (censura).

Saída: dados/processados/dataset_ml_multi_v2.csv
(inclui também o rótulo v1 para comparação)
"""
import csv
import json
from datetime import date, timedelta
from pathlib import Path

from coleta_pncp import RAW
from monta_dataset import carrega_orgaos, d, desfecho

OUT = RAW.parent / "processados"
HOJE = date(2026, 7, 21)
HORIZONTE = 365  # dias


def desfecho_12m(c, ts):
    """Eventos adversos datados dentro da janela [assinatura, assinatura+365d]."""
    ass = d(c.get("dataAssinatura")) or d(c.get("dataVigenciaInicio"))
    if not ass:
        return None
    corte = ass + timedelta(days=HORIZONTE)
    fim_original = d(c.get("dataVigenciaFim"))
    rescindido = 0
    valor_acrescido = 0.0
    prazo_janela = 0
    n_termos_janela = 0
    for t in ts:
        dt = d(t.get("dataAssinatura")) or d(t.get("dataPublicacaoPncp"))
        if not dt or dt > corte:
            continue
        n_termos_janela += 1
        nome = (t.get("tipoTermoContratoNome") or "").lower()
        if "rescis" in nome or "extin" in nome or "anula" in nome:
            rescindido = 1
        valor_acrescido += t.get("valorAcrescido") or 0
        prazo_janela += t.get("prazoAditadoDias") or 0
        fim_t = d(t.get("dataVigenciaFim"))
        if fim_t and fim_original and (fim_t - fim_original).days > prazo_janela:
            prazo_janela = (fim_t - fim_original).days
    v0 = c.get("valorInicial") or 0
    acresc = valor_acrescido / v0 if v0 else 0
    adverso = int(bool(rescindido or acresc > 0.249 or prazo_janela > 365))
    return {"n_termos_12m": n_termos_janela, "rescindido_12m": rescindido,
            "acrescimo_12m": round(acresc, 4), "prazo_12m": prazo_janela,
            "label_adverso_12m": adverso}


if __name__ == "__main__":
    cadastros = json.loads((RAW / "cadastros.json").read_text(encoding="utf-8"))
    n_forn = {}
    for _, contratos, _t in carrega_orgaos():
        for c in contratos:
            ni = c.get("niFornecedor") or ""
            if len(ni) == 14:
                n_forn[ni] = n_forn.get(ni, 0) + 1

    linhas, exclusos = [], 0
    for sigla, contratos, termos in carrega_orgaos():
        for c in contratos:
            ass = d(c.get("dataAssinatura")) or d(c.get("dataVigenciaInicio"))
            if not ass or (HOJE - ass).days < HORIZONTE:
                exclusos += 1  # observação insuficiente p/ rótulo de 12m
                continue
            ts = termos.get(c["numeroControlePNCP"]) or []
            d12 = desfecho_12m(c, ts)
            if d12 is None:
                exclusos += 1
                continue
            ni = c.get("niFornecedor") or ""
            cad = cadastros.get(ni) or {}
            ini, fim = d(c.get("dataVigenciaInicio")), d(c.get("dataVigenciaFim"))
            abertura = d(cad.get("abertura"))
            valor = c.get("valorGlobal") or 0
            capital = cad.get("capital_social")
            nat = (cad.get("natureza") or "")
            _na, _re, _ac, _pr, adverso_v1 = desfecho(c, ts)
            linhas.append({
                "pncp": c["numeroControlePNCP"], "orgao": sigla,
                "assinatura": ass.isoformat(),
                "valor_global": valor,
                "duracao_dias": (fim - ini).days if ini and fim else "",
                "categoria": (c.get("categoriaProcesso") or {}).get("nome") or "",
                "capital_social": capital if capital is not None else "",
                "idade_forn_anos": round((ass - abertura).days / 365.25, 2) if abertura else "",
                "porte": cad.get("porte") or "",
                "simples": {True: 1, False: 0}.get(cad.get("opcao_simples"), ""),
                "situacao_ativa": 1 if (cad.get("situacao") or "").upper() == "ATIVA" else 0,
                "consorcio": 1 if "CONS" in nat.upper() and "RCIO" in nat.upper() else 0,
                "razao_capital_valor": round(capital / valor, 6) if capital and valor else "",
                "n_contratos_forn_dataset": n_forn.get(ni, 0),
                **d12,
                "label_v1_sem_horizonte": adverso_v1,
            })
    arq = OUT / "dataset_ml_multi_v2.csv"
    with open(arq, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    pos = sum(r["label_adverso_12m"] for r in linhas)
    print(f"{arq.name}: {len(linhas)} contratos elegíveis (excluídos {exclusos} "
          f"com <12m de observação)")
    print(f"label 12m: {pos} adversos ({100*pos/len(linhas):.1f}%)")
    por_ano = {}
    for r in linhas:
        a = r["assinatura"][:4]
        s = por_ano.setdefault(a, [0, 0])
        s[0] += 1
        s[1] += r["label_adverso_12m"]
    for a, (n, p) in sorted(por_ano.items()):
        print(f"  {a}: {n} contratos, {p} adversos ({100*p/n:.1f}%)")
