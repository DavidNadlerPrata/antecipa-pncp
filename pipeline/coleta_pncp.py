# -*- coding: utf-8 -*-
"""
ANTECIPA — Etapa de coleta de dados reais (PNCP + compras.gov.br + Receita/CNPJ aberto)

Coleta, para o STF (CNPJ 00531640000128), desde a vigência da Lei 14.133/2021:
  A. Contratos publicados no PNCP (API de consulta oficial)
  B. Termos de cada contrato (aditivos, apostilamentos, rescisões) -> DESFECHO REAL
  C. Perfil nacional dos principais fornecedores (API de busca do PNCP + dados
     cadastrais abertos da Receita via minhareceita.org)
  D. Itens CATMAT/CATSER das compras do STF + preços homologados nacionais
     (API de pesquisa de preços do compras.gov.br)

Saída: JSONs brutos em ../dados/brutos/  (reexecutável; usa cache em disco)
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "dados" / "brutos"
RAW.mkdir(parents=True, exist_ok=True)

CNPJ_STF = "00531640000128"
UA = "Mozilla/5.0 (pesquisa academica UnB - Mestrado Adm Publica - projeto ANTECIPA)"
HOJE = "20260720"


def get_json(url, params=None, retries=4, timeout=60):
    """GET com retry/backoff; retorna (status, obj) — 204 vira lista vazia."""
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if r.status == 204:
                    return 204, []
                return r.status, json.loads(r.read().decode("utf-8"))
        except Exception as e:  # HTTPError, URLError, timeout, JSON
            last = e
            code = getattr(e, "code", None)
            if code in (400, 404, 422):
                return code, None
            time.sleep(1.5 * (i + 1))
    print(f"  !! falhou: {url} ({last})")
    return 0, None


def salvar(nome, obj):
    p = RAW / nome
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  -> {p.relative_to(BASE)} ({p.stat().st_size/1024:.0f} KB)")


def carregar(nome):
    p = RAW / nome
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return None


# ---------------------------------------------------------------- A. contratos
def coleta_contratos():
    cache = carregar("contratos_stf.json")
    if cache:
        print(f"A. contratos: cache com {len(cache)} registros")
        return cache
    print("A. Coletando contratos do STF no PNCP...")
    periodos = [("20230101", "20231231"), ("20240101", "20241231"),
                ("20250101", "20251231"), ("20260101", HOJE)]
    todos = []
    for ini, fim in periodos:
        pagina, total_paginas = 1, 1
        while pagina <= total_paginas:
            st, j = get_json("https://pncp.gov.br/api/consulta/v1/contratos",
                             {"dataInicial": ini, "dataFinal": fim,
                              "cnpjOrgao": CNPJ_STF, "pagina": pagina, "tamanhoPagina": 50})
            if not j:
                break
            total_paginas = j.get("totalPaginas", 1)
            todos.extend(j.get("data") or [])
            pagina += 1
            time.sleep(0.15)
        print(f"  período {ini}-{fim}: acumulado {len(todos)}")
    salvar("contratos_stf.json", todos)
    return todos


# ------------------------------------------------------------------- B. termos
def coleta_termos(contratos):
    cache = carregar("termos_stf.json")
    if cache:
        print(f"B. termos: cache com {len(cache)} contratos")
        return cache
    print(f"B. Coletando termos (aditivos/rescisões) de {len(contratos)} contratos...")
    termos = {}

    def um(c):
        ano, seq = c["anoContrato"], c["sequencialContrato"]
        st, j = get_json(f"https://pncp.gov.br/api/pncp/v1/orgaos/{CNPJ_STF}/contratos/{ano}/{seq}/termos")
        return c["numeroControlePNCP"], (j if isinstance(j, list) else [])

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(um, c) for c in contratos]
        for i, f in enumerate(as_completed(futs), 1):
            k, v = f.result()
            termos[k] = v
            if i % 100 == 0:
                print(f"  {i}/{len(contratos)}")
    salvar("termos_stf.json", termos)
    return termos


# ------------------------------------------------------------- C. fornecedores
def coleta_fornecedores(contratos, top_n=15):
    cache = carregar("fornecedores.json")
    if cache:
        print(f"C. fornecedores: cache com {len(cache)} CNPJs")
        return cache
    val = defaultdict(float)
    nome = {}
    for c in contratos:
        ni = c.get("niFornecedor") or ""
        if len(ni) == 14:  # só PJ
            val[ni] += c.get("valorGlobal") or 0
            nome[ni] = c.get("nomeRazaoSocialFornecedor")
    tops = sorted(val, key=val.get, reverse=True)[:top_n]
    print(f"C. Coletando perfil nacional de {len(tops)} fornecedores...")
    out = {}
    for ni in tops:
        # contratos em todos os órgãos (API de busca do portal)
        nacionais = []
        for pagina in range(1, 5):
            st, j = get_json("https://pncp.gov.br/api/search/",
                             {"tipos_documento": "contrato", "q": f'"{ni}"',
                              "status": "todos", "pagina": pagina, "tam_pagina": 50,
                              "ordenacao": "-data"})
            items = (j or {}).get("items") or []
            for it in items:
                nacionais.append({
                    "orgao": it.get("orgao_nome"), "esfera": it.get("esfera_nome"),
                    "uf": it.get("uf"), "ano": it.get("ano"),
                    "assinatura": it.get("data_assinatura"),
                    "valor": it.get("valor_global"),
                    "fim_vigencia": it.get("data_fim_vigencia"),
                })
            total = (j or {}).get("total") or 0
            if pagina * 50 >= total:
                break
            time.sleep(0.3)
        # dados cadastrais abertos (Receita Federal via minhareceita.org)
        st, rec = get_json(f"https://minhareceita.org/{ni}")
        cadastro = {}
        if isinstance(rec, dict):
            cadastro = {
                "razao_social": rec.get("razao_social"),
                "capital_social": rec.get("capital_social"),
                "porte": rec.get("porte"),
                "abertura": rec.get("data_inicio_atividade"),
                "cnae_principal": rec.get("cnae_fiscal_descricao"),
                "opcao_simples": rec.get("opcao_pelo_simples"),
                "situacao": rec.get("descricao_situacao_cadastral"),
                "municipio": rec.get("municipio"), "uf": rec.get("uf"),
            }
        out[ni] = {"nome": nome.get(ni), "valor_no_stf": round(val[ni], 2),
                   "contratos_nacionais": nacionais, "cadastro": cadastro}
        print(f"  {ni} {nome.get(ni)}: {len(nacionais)} contratos nacionais")
        time.sleep(0.3)
    salvar("fornecedores.json", out)
    return out


# ------------------------------------------------------ D. itens + preços ref.
def coleta_itens(contratos, max_compras=250):
    cache = carregar("itens_stf.json")
    if cache:
        print(f"D1. itens: cache com {len(cache)} compras")
        return cache
    compras = {}
    for c in contratos:
        ncc = c.get("numeroControlePncpCompra") or ""
        # formato: 00531640000128-1-000225/2024
        try:
            resto = ncc.split("-1-")[1]
            seq, ano = resto.split("/")
            compras[ncc] = (int(ano), int(seq))
        except (IndexError, ValueError):
            continue
    alvo = list(compras.items())[:max_compras]
    print(f"D1. Coletando itens de {len(alvo)} compras do STF...")
    out = {}

    def um(par):
        ncc, (ano, seq) = par
        st, j = get_json(
            f"https://pncp.gov.br/api/pncp/v1/orgaos/{CNPJ_STF}/compras/{ano}/{seq}/itens",
            {"pagina": 1, "tamanhoPagina": 50})
        return ncc, (j if isinstance(j, list) else [])

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(um, p) for p in alvo]
        for i, f in enumerate(as_completed(futs), 1):
            k, v = f.result()
            out[k] = [{
                "numeroItem": it.get("numeroItem"),
                "descricao": (it.get("descricao") or "")[:300],
                "tipo": it.get("materialOuServico"),
                "catmat": it.get("catalogoCodigoItem"),
                "valorUnitarioEstimado": it.get("valorUnitarioEstimado"),
                "quantidade": it.get("quantidade"),
                "unidade": it.get("unidadeMedida"),
                "situacao": it.get("situacaoCompraItemNome"),
            } for it in v]
            if i % 50 == 0:
                print(f"  {i}/{len(alvo)}")
    salvar("itens_stf.json", out)
    return out


def coleta_precos(itens_stf, top_codigos=8):
    cache = carregar("precos_referencia.json")
    if cache:
        print(f"D2. preços: cache com {len(cache)} códigos")
        return cache
    freq = Counter()
    info = {}
    for its in itens_stf.values():
        for it in its:
            cod = it.get("catmat")
            if cod:
                freq[(cod, it["tipo"])] += 1
                info[(cod, it["tipo"])] = it
    tops = [k for k, _ in freq.most_common(top_codigos * 2)][:top_codigos]
    print(f"D2. Coletando preços nacionais de {len(tops)} códigos CATMAT/CATSER...")
    out = {}
    for cod, tipo in tops:
        ep = ("1_consultarMaterial" if tipo == "M" else "3_consultarServico")
        st, j = get_json(f"https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/{ep}",
                         {"pagina": 1, "tamanhoPagina": 100, "codigoItemCatalogo": cod})
        res = (j or {}).get("resultado") or []
        out[str(cod)] = {
            "tipo": tipo,
            "descricao_stf": info[(cod, tipo)]["descricao"],
            "unidade_stf": info[(cod, tipo)].get("unidade"),
            "estimado_stf": info[(cod, tipo)].get("valorUnitarioEstimado"),
            "ocorrencias_stf": freq[(cod, tipo)],
            "precos_nacionais": [{
                "preco": r.get("precoUnitario"),
                "data": r.get("dataResultado") or r.get("dataCompra"),
                "orgao": r.get("nomeOrgao"), "uf": r.get("estado"),
                "descricao": (r.get("descricaoItem") or "")[:200],
                "quantidade": r.get("quantidade"),
                "fornecedor": r.get("nomeFornecedor"),
            } for r in res],
        }
        print(f"  {cod} ({tipo}): {len(res)} preços nacionais")
        time.sleep(0.4)
    salvar("precos_referencia.json", out)
    return out


if __name__ == "__main__":
    t0 = time.time()
    contratos = coleta_contratos()
    termos = coleta_termos(contratos)
    fornecedores = coleta_fornecedores(contratos)
    itens = coleta_itens(contratos)
    precos = coleta_precos(itens)
    print(f"\nConcluído em {time.time()-t0:.0f}s — {len(contratos)} contratos, "
          f"{sum(len(v) for v in termos.values())} termos, {len(fornecedores)} fornecedores, "
          f"{len(precos)} itens com preço de referência.")
