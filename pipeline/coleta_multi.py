# -*- coding: utf-8 -*-
"""
ANTECIPA — Coleta multi-órgão (recomendação nº 2 da análise crítica).

Coleta contratos e termos (aditivos/rescisões) de tribunais do Judiciário
federal no PNCP, no mesmo recorte temporal do STF (2023 → hoje), para compor
o dataset de treino supervisionado. Saída: dados/brutos/multi/.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from coleta_pncp import RAW, HOJE, get_json

MULTI = RAW / "multi"
MULTI.mkdir(parents=True, exist_ok=True)

ORGAOS = {
    "00488478000102": "STJ",
    "00509968000148": "TST",
    "00509018000113": "TSE",
    "00497560000101": "STM",
    "07421906000129": "CNJ",
    "32243347000151": "TRF2",
    "59949362000176": "TRF3",
    "92518737000119": "TRF4",
    "24130072000111": "TRF5",
    "47784477000179": "TRF6",
}

PERIODOS = [("20230101", "20231231"), ("20240101", "20241231"),
            ("20250101", "20251231"), ("20260101", HOJE)]


def coleta_contratos(cnpj, sigla):
    arq = MULTI / f"contratos_{sigla}.json"
    if arq.exists():
        dados = json.loads(arq.read_text(encoding="utf-8"))
        print(f"{sigla}: contratos em cache ({len(dados)})")
        return dados
    todos = []
    for ini, fim in PERIODOS:
        pagina, total_paginas = 1, 1
        while pagina <= total_paginas:
            st, j = get_json("https://pncp.gov.br/api/consulta/v1/contratos",
                             {"dataInicial": ini, "dataFinal": fim,
                              "cnpjOrgao": cnpj, "pagina": pagina, "tamanhoPagina": 50})
            if not j:
                break
            total_paginas = j.get("totalPaginas", 1)
            todos.extend(j.get("data") or [])
            pagina += 1
            time.sleep(0.12)
    arq.write_text(json.dumps(todos, ensure_ascii=False), encoding="utf-8")
    print(f"{sigla}: {len(todos)} contratos")
    return todos


def coleta_termos(cnpj, sigla, contratos):
    arq = MULTI / f"termos_{sigla}.json"
    if arq.exists():
        dados = json.loads(arq.read_text(encoding="utf-8"))
        print(f"{sigla}: termos em cache ({len(dados)})")
        return dados
    termos = {}

    def um(c):
        st, j = get_json(f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/"
                         f"{c['anoContrato']}/{c['sequencialContrato']}/termos")
        return c["numeroControlePNCP"], (j if isinstance(j, list) else [])

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(um, c) for c in contratos]
        for i, f in enumerate(as_completed(futs), 1):
            k, v = f.result()
            termos[k] = v
            if i % 200 == 0:
                print(f"  {sigla} termos {i}/{len(contratos)}")
    arq.write_text(json.dumps(termos, ensure_ascii=False), encoding="utf-8")
    n = sum(1 for v in termos.values() if v)
    print(f"{sigla}: termos coletados ({n} contratos com termo)")
    return termos


if __name__ == "__main__":
    t0 = time.time()
    tot_c = tot_t = 0
    for cnpj, sigla in ORGAOS.items():
        cs = coleta_contratos(cnpj, sigla)
        ts = coleta_termos(cnpj, sigla, cs)
        tot_c += len(cs)
        tot_t += sum(len(v) for v in ts.values())
    print(f"\nConcluído em {time.time()-t0:.0f}s — {tot_c} contratos e {tot_t} termos "
          f"em {len(ORGAOS)} órgãos (além do STF já coletado).")
