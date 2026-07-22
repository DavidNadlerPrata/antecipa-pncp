# -*- coding: utf-8 -*-
"""
ANTECIPA — Cadastro aberto (Receita Federal via minhareceita.org) de todos os
fornecedores PJ únicos do dataset multi-órgão + STF. Gera dados/brutos/cadastros.json.
Incremental: pode ser interrompido e reexecutado.
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from coleta_pncp import RAW, get_json

ARQ = RAW / "cadastros.json"


def fornecedores_unicos():
    nis = set()
    fontes = [RAW / "contratos_stf.json"] + sorted((RAW / "multi").glob("contratos_*.json"))
    for f in fontes:
        for c in json.loads(f.read_text(encoding="utf-8")):
            ni = c.get("niFornecedor") or ""
            if len(ni) == 14:
                nis.add(ni)
    return nis


def um(ni):
    st, rec = get_json(f"https://minhareceita.org/{ni}", retries=3, timeout=30)
    if not isinstance(rec, dict):
        return ni, None
    return ni, {
        "razao_social": rec.get("razao_social"),
        "capital_social": rec.get("capital_social"),
        "porte": rec.get("porte"),
        "abertura": rec.get("data_inicio_atividade"),
        "cnae": rec.get("cnae_fiscal_descricao"),
        "natureza": rec.get("natureza_juridica"),
        "opcao_simples": rec.get("opcao_pelo_simples"),
        "situacao": rec.get("descricao_situacao_cadastral"),
        "uf": rec.get("uf"),
    }


if __name__ == "__main__":
    t0 = time.time()
    cad = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    alvo = sorted(fornecedores_unicos() - set(cad))
    print(f"{len(alvo)} fornecedores a consultar ({len(cad)} em cache)")
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(um, ni) for ni in alvo]
        for i, f in enumerate(as_completed(futs), 1):
            ni, d = f.result()
            cad[ni] = d
            if i % 100 == 0:
                ARQ.write_text(json.dumps(cad, ensure_ascii=False), encoding="utf-8")
                print(f"  {i}/{len(alvo)}")
    ARQ.write_text(json.dumps(cad, ensure_ascii=False), encoding="utf-8")
    ok = sum(1 for v in cad.values() if v)
    print(f"Concluído em {time.time()-t0:.0f}s — {ok}/{len(cad)} cadastros obtidos.")
