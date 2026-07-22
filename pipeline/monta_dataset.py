# -*- coding: utf-8 -*-
"""
ANTECIPA — Monta o dataset multi-órgão rotulado pelo desfecho real.

Um registro por contrato (STF + 10 tribunais federais), com features conhecidas
NO MOMENTO DA ASSINATURA (para não vazar o futuro) e rótulo derivado do que
aconteceu depois (termos publicados no PNCP):
  desfecho_adverso = rescisão/extinção OU acréscimo de valor > 25% OU
                     prorrogação > 365 dias.

Saída: dados/processados/dataset_ml_multi.csv
"""
import csv
import json
from datetime import date
from pathlib import Path

from coleta_pncp import RAW

OUT = RAW.parent / "processados"
OUT.mkdir(parents=True, exist_ok=True)


def d(s):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def desfecho(c, ts):
    n_aditivos = rescindido = 0
    valor_acrescido = 0.0
    prazo_aditado = 0
    fim_original = d(c.get("dataVigenciaFim"))
    fim_atual = fim_original
    for t in ts:
        nome = (t.get("tipoTermoContratoNome") or "").lower()
        if "adit" in nome:
            n_aditivos += 1
        if "rescis" in nome or "extin" in nome or "anula" in nome:
            rescindido = 1
        valor_acrescido += t.get("valorAcrescido") or 0
        prazo_aditado += t.get("prazoAditadoDias") or 0
        fim_t = d(t.get("dataVigenciaFim"))
        if fim_t and fim_atual and fim_t > fim_atual:
            fim_atual = fim_t
    v0 = c.get("valorInicial") or 0
    vac = c.get("valorAcumulado") or c.get("valorGlobal") or 0
    acresc = max((vac - v0), valor_acrescido) / v0 if v0 else 0
    prazo_extra = (fim_atual - fim_original).days if fim_original and fim_atual else 0
    prazo_extra = max(prazo_extra, prazo_aditado)
    adverso = int(bool(rescindido or acresc > 0.249 or prazo_extra > 365))
    return n_aditivos, rescindido, round(acresc, 4), prazo_extra, adverso


def carrega_orgaos():
    pares = [("STF", RAW / "contratos_stf.json", RAW / "termos_stf.json")]
    for f in sorted((RAW / "multi").glob("contratos_*.json")):
        sigla = f.stem.replace("contratos_", "")
        pares.append((sigla, f, RAW / "multi" / f"termos_{sigla}.json"))
    for sigla, fc, ft in pares:
        contratos = json.loads(fc.read_text(encoding="utf-8"))
        # dedup por numeroControlePNCP (republicações/retificações aparecem
        # repetidas na paginação) — fica a versão com atualização mais recente
        vistos = {}
        for c in contratos:
            k = c.get("numeroControlePNCP")
            atual = c.get("dataAtualizacaoGlobal") or c.get("dataAtualizacao") or ""
            if k not in vistos or atual > (vistos[k].get("dataAtualizacaoGlobal")
                                           or vistos[k].get("dataAtualizacao") or ""):
                vistos[k] = c
        termos = json.loads(ft.read_text(encoding="utf-8")) if ft.exists() else {}
        yield sigla, list(vistos.values()), termos


if __name__ == "__main__":
    cadastros = json.loads((RAW / "cadastros.json").read_text(encoding="utf-8"))
    # contagem de contratos por fornecedor no dataset inteiro (proxy de recorrência)
    n_forn = {}
    for _, contratos, _t in carrega_orgaos():
        for c in contratos:
            ni = c.get("niFornecedor") or ""
            if len(ni) == 14:
                n_forn[ni] = n_forn.get(ni, 0) + 1

    linhas = []
    for sigla, contratos, termos in carrega_orgaos():
        for c in contratos:
            ni = c.get("niFornecedor") or ""
            cad = cadastros.get(ni) or {}
            ass = d(c.get("dataAssinatura")) or d(c.get("dataVigenciaInicio"))
            ini, fim = d(c.get("dataVigenciaInicio")), d(c.get("dataVigenciaFim"))
            abertura = d(cad.get("abertura"))
            idade = round((ass - abertura).days / 365.25, 2) if ass and abertura else ""
            valor = c.get("valorGlobal") or 0
            capital = cad.get("capital_social")
            nat = (cad.get("natureza") or "")
            n_adit, resc, acresc, prazo, adverso = desfecho(
                c, termos.get(c["numeroControlePNCP"]) or [])
            linhas.append({
                "pncp": c["numeroControlePNCP"], "orgao": sigla,
                "assinatura": ass.isoformat() if ass else "",
                "valor_global": valor,
                "duracao_dias": (fim - ini).days if ini and fim else "",
                "categoria": (c.get("categoriaProcesso") or {}).get("nome") or "",
                "capital_social": capital if capital is not None else "",
                "idade_forn_anos": idade,
                "porte": cad.get("porte") or "",
                "simples": {True: 1, False: 0}.get(cad.get("opcao_simples"), ""),
                "situacao_ativa": 1 if (cad.get("situacao") or "").upper() == "ATIVA" else 0,
                "consorcio": 1 if "CONS" in nat.upper() and "RCIO" in nat.upper() else 0,
                "razao_capital_valor": round(capital / valor, 6) if capital and valor else "",
                "n_contratos_forn_dataset": n_forn.get(ni, 0),
                "n_aditivos": n_adit, "rescindido": resc,
                "acrescimo_pct": acresc, "prazo_extra_dias": prazo,
                "label_desfecho_adverso": adverso,
            })
    arq = OUT / "dataset_ml_multi.csv"
    with open(arq, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(linhas[0].keys()))
        w.writeheader()
        w.writerows(linhas)
    pos = sum(r["label_desfecho_adverso"] for r in linhas)
    por_orgao = {}
    for r in linhas:
        o = por_orgao.setdefault(r["orgao"], [0, 0])
        o[0] += 1
        o[1] += r["label_desfecho_adverso"]
    print(f"{arq.name}: {len(linhas)} contratos, {pos} adversos ({100*pos/len(linhas):.1f}%)")
    for o, (n, p) in sorted(por_orgao.items()):
        print(f"  {o}: {n} contratos, {p} adversos")
