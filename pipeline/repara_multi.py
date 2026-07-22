# -*- coding: utf-8 -*-
"""
ANTECIPA — Reparo das janelas de coleta que falharam por rate-limit (HTTP 429).
Refaz os períodos afetados com ritmo mais lento, mescla por numeroControlePNCP
e coleta termos apenas dos contratos novos.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from coleta_pncp import get_json
from coleta_multi import MULTI

# (sigla, cnpj, período) das falhas registradas nos logs
FALHAS = [
    ("TST",  "00509968000148", ("20230101", "20231231")),
    ("TSE",  "00509018000113", ("20230101", "20231231")),
    ("TSE",  "00509018000113", ("20240101", "20241231")),
    ("TSE",  "00509018000113", ("20250101", "20251231")),
    ("TRF5", "24130072000111", ("20260101", "20260720")),
    ("TRF6", "47784477000179", ("20250101", "20251231")),
]


def refetch(cnpj, ini, fim):
    todos, pagina, total_paginas = [], 1, 1
    while pagina <= total_paginas:
        st, j = get_json("https://pncp.gov.br/api/consulta/v1/contratos",
                         {"dataInicial": ini, "dataFinal": fim, "cnpjOrgao": cnpj,
                          "pagina": pagina, "tamanhoPagina": 50}, retries=6)
        if not j:
            print(f"  !! página {pagina} ainda falhando — seguindo com o obtido")
            break
        total_paginas = j.get("totalPaginas", 1)
        todos.extend(j.get("data") or [])
        pagina += 1
        time.sleep(0.4)
    return todos


if __name__ == "__main__":
    t0 = time.time()
    novos_total = 0
    for sigla, cnpj, (ini, fim) in FALHAS:
        arq_c = MULTI / f"contratos_{sigla}.json"
        arq_t = MULTI / f"termos_{sigla}.json"
        contratos = json.loads(arq_c.read_text(encoding="utf-8"))
        termos = json.loads(arq_t.read_text(encoding="utf-8"))
        conhecidos = {c["numeroControlePNCP"] for c in contratos}
        lote = refetch(cnpj, ini, fim)
        novos = [c for c in lote if c["numeroControlePNCP"] not in conhecidos]
        # dedup dentro do lote novo
        vistos = {}
        for c in novos:
            vistos[c["numeroControlePNCP"]] = c
        novos = list(vistos.values())
        print(f"{sigla} {ini}-{fim}: {len(lote)} baixados, {len(novos)} novos")
        if not novos:
            continue
        contratos.extend(novos)
        arq_c.write_text(json.dumps(contratos, ensure_ascii=False), encoding="utf-8")

        def um(c):
            st, j = get_json(f"https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/contratos/"
                             f"{c['anoContrato']}/{c['sequencialContrato']}/termos")
            return c["numeroControlePNCP"], (j if isinstance(j, list) else [])

        with ThreadPoolExecutor(max_workers=4) as ex:
            for f in as_completed([ex.submit(um, c) for c in novos]):
                k, v = f.result()
                termos[k] = v
        arq_t.write_text(json.dumps(termos, ensure_ascii=False), encoding="utf-8")
        novos_total += len(novos)
        time.sleep(1)
    print(f"Reparo concluído em {time.time()-t0:.0f}s — {novos_total} contratos adicionados.")
