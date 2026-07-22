# -*- coding: utf-8 -*-
"""
ANTECIPA — Coleta de preços de referência (v2).

O STF não preenche o campo catalogoCodigoItem nos itens publicados no PNCP
(achado real de qualidade de dados — confirma o item 2.4 da análise crítica).
Caminho alternativo usando o catálogo oficial do compras.gov.br:

  1. Baixa o catálogo de PDMs (padrões descritivos de material);
  2. Casa por palavra-chave os itens mais recorrentes do STF com um PDM;
  3. Lista os códigos CATMAT do PDM;
  4. Consulta preços homologados nacionais por código na API de pesquisa
     de preços, agregando até obter amostra suficiente.

Também refaz fornecedores cuja busca nacional falhou na coleta principal.
"""
import json
import re
import statistics as st
import time
import unicodedata
from pathlib import Path

from coleta_pncp import RAW, get_json, salvar, carregar

def norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return s.upper()


# ---------------------------------------------------------- catálogo de PDMs
def baixa_pdms():
    cache = carregar("pdm_catalogo.json")
    if cache:
        print(f"PDMs em cache: {len(cache)}")
        return cache
    print("Baixando catálogo de PDMs do compras.gov.br...")
    pdms = []
    pagina = 1
    while True:
        stc, j = get_json("https://dadosabertos.compras.gov.br/modulo-material/3_consultarPdmMaterial",
                          {"pagina": pagina, "tamanhoPagina": 500})
        res = (j or {}).get("resultado") or []
        if not res:
            break
        pdms.extend({"codigo": r["codigoPdm"], "nome": r["nomePdm"],
                     "classe": r["codigoClasse"], "nomeClasse": r["nomeClasse"],
                     "ativo": r["statusPdm"]} for r in res)
        total = j.get("totalRegistros") or 0
        if pagina * 500 >= total:
            break
        pagina += 1
        time.sleep(0.25)
    salvar("pdm_catalogo.json", pdms)
    return pdms


# --------------------------------------------------- alvos: STF -> PDM oficial
# (rótulo, regex p/ descrição do item STF, código do PDM verificado no catálogo)
ALVOS = [
    # Switch de rede foi avaliado e descartado: o PDM nacional mistura produtos
    # domésticos e corporativos — comparação unitária sem sentido (análise 2.4).
    ("Microcomputador",        r"^microcomputador", 6661),   # MICROCOMPUTADOR
    ("Poltrona",               r"^poltrona",        10984),  # POLTRONA
    ("Sofá",                   r"^sof",             12177),  # SOFÁ
    ("Armário",                r"^armario",         328),    # ARMÁRIO ESCRITÓRIO
    ("Fruta (alimentação)",    r"^fruta",           19789),  # FRUTA
    ("Biscoito",               r"^biscoito",        883),    # BISCOITO
    ("Chá",                    r"^cha\b|^cha ",     4805),   # CHÁ ALIMENTAÇÃO
]


def precos_por_pdm(pdm_cod, max_codigos=18, alvo_amostra=90):
    stc, j = get_json("https://dadosabertos.compras.gov.br/modulo-material/4_consultarItemMaterial",
                      {"pagina": 1, "tamanhoPagina": 500, "codigoPdm": pdm_cod, "statusItem": "true"})
    itens = (j or {}).get("resultado") or []
    precos = []
    usados = 0
    for it in itens:
        if usados >= max_codigos or len(precos) >= alvo_amostra:
            break
        cod = it.get("codigoItem")
        stc, pj = get_json("https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/1_consultarMaterial",
                           {"pagina": 1, "tamanhoPagina": 100, "codigoItemCatalogo": cod})
        res = (pj or {}).get("resultado") or []
        usados += 1
        for r in res:
            p = r.get("precoUnitario")
            if p and p > 0:
                precos.append({"preco": p, "data": r.get("dataResultado") or r.get("dataCompra"),
                               "orgao": r.get("nomeOrgao"), "uf": r.get("estado"),
                               "descricao": (r.get("descricaoItem") or "")[:160],
                               "quantidade": r.get("quantidade"),
                               "fornecedor": r.get("nomeFornecedor"), "catmat": cod})
        time.sleep(0.25)
    return precos, usados, len(itens)


def coleta_precos():
    pdms = baixa_pdms()
    por_codigo = {p["codigo"]: p for p in pdms}
    itens_stf = carregar("itens_stf.json") or {}
    out = {}
    for rotulo, re_stf, pdm_codigo in ALVOS:
        # lado STF: preços unitários reais dos itens que casam com a descrição
        stf_unit = []
        stf_desc, stf_un = "", ""
        for its in itens_stf.values():
            for it in its:
                if it["tipo"] == "M" and re.search(re_stf, norm(it["descricao"]), re.I):
                    v = it.get("valorUnitarioEstimado")
                    if v and v > 0:
                        stf_unit.append(v)
                        stf_desc = stf_desc or it["descricao"]
                        stf_un = stf_un or (it.get("unidade") or "")
        if not stf_unit:
            print(f"- {rotulo}: sem itens no STF, pulando")
            continue
        # lado nacional: PDM -> códigos -> preços
        pdm = por_codigo.get(pdm_codigo)
        if not pdm:
            print(f"- {rotulo}: PDM {pdm_codigo} não encontrado")
            continue
        precos, usados, n_itens = precos_por_pdm(pdm["codigo"])
        print(f"- {rotulo}: PDM {pdm['codigo']} ({pdm['nome']}) · {n_itens} códigos · "
              f"{usados} consultados · {len(precos)} preços · STF n={len(stf_unit)}")
        if len(precos) < 8:
            continue
        out[f"PDM-{pdm['codigo']}"] = {
            "tipo": "M",
            "rotulo": rotulo,
            "pdm_nome": pdm["nome"],
            "descricao_stf": stf_desc[:200],
            "unidade_stf": stf_un,
            "estimado_stf": round(st.median(stf_unit), 2),
            "ocorrencias_stf": len(stf_unit),
            "precos_nacionais": precos,
        }
    salvar("precos_referencia.json", out)
    return out


# ------------------------------------------- reparo de fornecedores com falha
def repara_fornecedores():
    forn = carregar("fornecedores.json") or {}
    mudou = False
    for ni, f in forn.items():
        if f.get("contratos_nacionais"):
            continue
        print(f"Refazendo busca nacional de {ni} ({f.get('nome')})...")
        nacionais = []
        for pagina in range(1, 5):
            stc, j = get_json("https://pncp.gov.br/api/search/",
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
            time.sleep(0.4)
        if nacionais:
            f["contratos_nacionais"] = nacionais
            mudou = True
            print(f"  {len(nacionais)} contratos nacionais")
        time.sleep(0.4)
    if mudou:
        salvar("fornecedores.json", forn)


if __name__ == "__main__":
    t0 = time.time()
    repara_fornecedores()
    out = coleta_precos()
    print(f"\nConcluído em {time.time()-t0:.0f}s — {len(out)} itens com referência nacional.")
