# -*- coding: utf-8 -*-
"""
ANTECIPA — Sanções dos fornecedores do STF no Portal da Transparência
(CEIS — Cadastro de Empresas Inidôneas e Suspensas; CNEP — Cadastro Nacional de
Empresas Punidas).

A API exige chave pessoal. Ela NUNCA fica no repositório: é lida, nesta ordem,
  1. da variável de ambiente PORTAL_TRANSPARENCIA_CHAVE, ou
  2. do arquivo ~/.antecipa/portal_transparencia.key
Sem chave, o script avisa e termina sem erro — o restante do pipeline segue
funcionando com o cache já coletado (dados/brutos/sancoes_stf.json), que é
dado público e é versionado normalmente.

Endpoints: /api-de-dados/ceis e /api-de-dados/cnep com codigoSancionado=<CNPJ>.
Limite da API: ~90 requisições/min das 6h à meia-noite — o script respeita ~80/min.
Coleta incremental: CNPJs já consultados não são consultados de novo.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "dados" / "brutos"
ARQ = RAW / "sancoes_stf.json"
API = "https://api.portaldatransparencia.gov.br/api-de-dados"
PAUSA = 0.75  # s entre requisições (~80/min)


def le_chave():
    chave = os.environ.get("PORTAL_TRANSPARENCIA_CHAVE", "").strip()
    if chave:
        return chave
    arq = Path.home() / ".antecipa" / "portal_transparencia.key"
    return arq.read_text(encoding="utf-8").strip() if arq.exists() else ""


def consulta(endpoint, cnpj, chave):
    """Todas as páginas de sanções de um CNPJ num cadastro (CEIS ou CNEP)."""
    regs, pagina = [], 1
    while True:
        url = f"{API}/{endpoint}?codigoSancionado={cnpj}&pagina={pagina}"
        req = urllib.request.Request(url, headers={"chave-api-dados": chave,
                                                   "Accept": "application/json"})
        for tentativa in range(5):
            try:
                with urllib.request.urlopen(req, timeout=40) as r:
                    dados = json.loads(r.read().decode("utf-8"))
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:            # limite estourado: espera e repete
                    time.sleep(20 * (tentativa + 1))
                    continue
                if e.code in (401, 403):
                    raise SystemExit("Chave recusada pela API (HTTP %d)." % e.code)
                time.sleep(3 * (tentativa + 1))
            except Exception:
                time.sleep(3 * (tentativa + 1))
        else:
            return None                      # falhou: não grava, tenta na próxima execução
        time.sleep(PAUSA)
        for s in dados:
            regs.append({
                "cadastro": endpoint.upper(),
                "tipo": (s.get("tipoSancao") or {}).get("descricaoResumida"),
                "orgao": (s.get("orgaoSancionador") or {}).get("nome"),
                "inicio": s.get("dataInicioSancao"),
                "fim": s.get("dataFimSancao"),
                "publicacao": s.get("dataPublicacaoSancao"),
                "fundamentacao": "; ".join(
                    (f.get("descricao") or "")[:120] for f in (s.get("fundamentacao") or [])),
            })
        if len(dados) < 15:                  # página incompleta = última
            return regs
        pagina += 1


if __name__ == "__main__":
    chave = le_chave()
    if not chave:
        print("Sem chave do Portal da Transparência (PORTAL_TRANSPARENCIA_CHAVE ou "
              "~/.antecipa/portal_transparencia.key). Mantido o cache existente.")
        raise SystemExit(0)

    contratos = json.loads((RAW / "contratos_stf.json").read_text(encoding="utf-8"))
    cnpjs = sorted({c["niFornecedor"] for c in contratos
                    if len(c.get("niFornecedor") or "") == 14})
    cache = json.loads(ARQ.read_text(encoding="utf-8")) if ARQ.exists() else {}
    forn = cache.get("fornecedores", {})
    alvo = [c for c in cnpjs if c not in forn]
    print(f"{len(cnpjs)} fornecedores PJ do STF · {len(forn)} em cache · {len(alvo)} a consultar")

    t0 = time.time()
    for i, cnpj in enumerate(alvo, 1):
        ceis = consulta("ceis", cnpj, chave)
        cnep = consulta("cnep", cnpj, chave)
        if ceis is None or cnep is None:
            print(f"  !! {cnpj}: falha — fica para a próxima execução")
            continue
        forn[cnpj] = {"ceis": ceis, "cnep": cnep}
        if i % 25 == 0 or i == len(alvo):
            ARQ.write_text(json.dumps({"coletado_em": date.today().isoformat(),
                                       "fonte": "Portal da Transparência — CEIS e CNEP",
                                       "fornecedores": forn}, ensure_ascii=False, indent=1),
                           encoding="utf-8")
            print(f"  {i}/{len(alvo)} ({time.time()-t0:.0f}s)")

    com = {k: v for k, v in forn.items() if v["ceis"] or v["cnep"]}
    print(f"\nConcluído: {len(forn)} fornecedores consultados, {len(com)} com algum registro.")
    for k, v in com.items():
        for s in v["ceis"] + v["cnep"]:
            print(f"  {k} [{s['cadastro']}] {s['tipo']} · {s['inicio']}→{s['fim']} · {s['orgao']}")
