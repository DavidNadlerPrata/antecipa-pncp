# -*- coding: utf-8 -*-
"""
ANTECIPA — Etapa de processamento dos dados reais coletados do PNCP.

Produz:
  dados/processados/antecipa_dados.json  -> consumido pelo dashboard
  dados/processados/dataset_ml.csv       -> dataset rotulado pelo DESFECHO REAL,
                                            pronto para treino supervisionado
                                            (endereça a fragilidade 2.1 da análise
                                            crítica: rótulo = desfecho, não regra)

Classificação exibida no dashboard: ESCORE HEURÍSTICO TRANSPARENTE (baseline),
nas escalas OFICIAIS da Res. STF 781/2022 (níveis 1-2-5-8-10, risco inerente de
0 a 100 — ver escala_781.py). Não é ML — é a régua de comparação sobre a qual o
modelo supervisionado é avaliado.
"""
import csv
import json
import statistics as st
from collections import defaultdict
from datetime import date
from pathlib import Path

import escala_781 as E

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "dados" / "brutos"
OUT = BASE / "dados" / "processados"
OUT.mkdir(parents=True, exist_ok=True)
HOJE = date(2026, 7, 20)          # data da coleta do PNCP


def load(nome):
    return json.loads((RAW / nome).read_text(encoding="utf-8"))


def d(s):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def dbr(s):
    """Data no formato do Portal da Transparência (dd/mm/aaaa)."""
    try:
        dd, mm, aa = s.strip().split("/")
        return date(int(aa), int(mm), int(dd))
    except (AttributeError, ValueError):
        return None


def deduplica(cs):
    """A paginação do PNCP repete contratos (republicações/retificações): mantém um
    registro por numeroControlePNCP — o de atualização mais recente."""
    v = {}
    for c in cs:
        k = c.get("numeroControlePNCP")
        at = c.get("dataAtualizacaoGlobal") or c.get("dataAtualizacao") or ""
        if k not in v or at > (v[k].get("dataAtualizacaoGlobal") or v[k].get("dataAtualizacao") or ""):
            v[k] = c
    return list(v.values())


_brutos = load("contratos_stf.json")
contratos = deduplica(_brutos)
N_REGISTROS_BRUTOS = len(_brutos)
termos = load("termos_stf.json")
fornecedores = load("fornecedores.json")
itens_stf = load("itens_stf.json")
precos = load("precos_referencia.json")
# cadastro aberto da Receita (capital, abertura, situação) de TODOS os
# fornecedores — base dos fatores F1–F5 e F7 do escore heurístico
_arq_cad = RAW / "cadastros.json"
CADASTROS = json.loads(_arq_cad.read_text(encoding="utf-8")) if _arq_cad.exists() else {}

# sanções CEIS/CNEP (Portal da Transparência) — opcional: sem o arquivo, o painel
# mostra a verificação como não realizada, em vez de "nada consta"
_arq_sanc = RAW / "sancoes_stf.json"
_sanc = json.loads(_arq_sanc.read_text(encoding="utf-8")) if _arq_sanc.exists() else {}
SANCOES = _sanc.get("fornecedores", {})
SANC_DATA = d(_sanc.get("coletado_em")) if _sanc else None


def sancoes_de(ni):
    v = SANCOES.get(ni)
    return None if v is None else (v.get("ceis") or []) + (v.get("cnep") or [])


def sancao_vigente_em(s, dia):
    """A sanção estava em vigor no dia? Fim ausente/'Sem informação' = indeterminado."""
    ini, fim = dbr(s.get("inicio")), dbr(s.get("fim"))
    return bool(ini and ini <= dia and (fim is None or dia <= fim))


def sancao_conhecida_em(s, dia):
    """A sanção já estava PUBLICADA no dia (logo, consultável antes de contratar)?"""
    pub = dbr(s.get("publicacao")) or dbr(s.get("inicio"))
    return bool(pub and pub <= dia)

# valor contratado pelo STF por fornecedor, recalculado sobre contratos únicos
# (o valor_no_stf gravado no cache da coleta somava as cópias duplicadas)
VALOR_NO_STF = defaultdict(float)
for _c in contratos:
    VALOR_NO_STF[_c.get("niFornecedor")] += _c.get("valorGlobal") or 0


# ---------------------------------------------------------------- fornecedores
def perfil_fornecedor(ni):
    f = fornecedores.get(ni)
    if not f:
        return None
    cad = f.get("cadastro") or {}
    nac = f.get("contratos_nacionais") or []
    por_ano = defaultdict(int)
    vol_nacional = 0.0
    vigentes = 0
    for c in nac:
        ano = c.get("ano")
        if ano:
            por_ano[str(ano)] += 1
        vol_nacional += c.get("valor") or 0
        fim = d(c.get("fim_vigencia"))
        if fim and fim >= HOJE:
            vigentes += 1
    anos = sorted(por_ano)
    serie = [{"ano": a, "n": por_ano[a]} for a in anos][-5:]
    capital = cad.get("capital_social") or 0
    abertura = d(cad.get("abertura"))
    idade = (HOJE - abertura).days / 365.25 if abertura else None
    # crescimento atípico: nº de contratos no melhor ano recente vs mediana anterior
    ns = [por_ano[a] for a in anos]
    cresc = None
    if len(ns) >= 3 and max(ns[:-1] or [0]) > 0:
        cresc = ns[-1] / max(st.median(ns[:-1]), 1)
    return {
        "ni": ni, "nome": cad.get("razao_social") or f.get("nome"),
        "capital_social": capital, "porte": cad.get("porte"),
        "idade_anos": round(idade, 1) if idade else None,
        "cnae": cad.get("cnae_principal"), "situacao": cad.get("situacao"),
        "municipio": cad.get("municipio"), "uf": cad.get("uf"),
        "vol_nacional": round(vol_nacional, 2), "contratos_nacionais": len(nac),
        "contratos_vigentes": vigentes, "serie_anual": serie,
        "valor_no_stf": round(VALOR_NO_STF.get(ni, 0.0), 2),
        "razao_capital_volume": round(capital / vol_nacional, 4) if vol_nacional else None,
        "crescimento_recente": round(cresc, 2) if cresc else None,
        # None = não consultado; [] = consultado, nada consta
        "sancoes": sancoes_de(ni),
        "sancoes_consulta": SANC_DATA.isoformat() if SANC_DATA else None,
    }


perfis = {}
for ni in fornecedores:
    p = perfil_fornecedor(ni)
    if p:
        perfis[ni] = p

# ------------------------------------------------------------------- desfechos
TIPOS_RESCISAO = ("rescis", "extin", "anula")


def desfecho_contrato(c):
    ts = termos.get(c["numeroControlePNCP"]) or []
    n_aditivos = 0
    rescindido = False
    valor_acrescido = 0.0
    prazo_aditado = 0
    fim_original = d(c.get("dataVigenciaFim"))
    fim_atual = fim_original
    for t in ts:
        nome_l = (t.get("tipoTermoContratoNome") or "").lower()
        if "adit" in nome_l:
            n_aditivos += 1
        if any(k in nome_l for k in TIPOS_RESCISAO):
            rescindido = True
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
    return {
        "n_termos": len(ts), "n_aditivos": n_aditivos, "rescindido": rescindido,
        "acrescimo_valor_pct": round(acresc, 4), "prazo_extra_dias": prazo_extra,
        # rótulo de desfecho adverso (para o dataset de ML):
        "desfecho_adverso": bool(rescindido or acresc > 0.249 or prazo_extra > 365),
    }


# ------------------------------------------- escore heurístico (Res. 781/2022)
valores = sorted((c.get("valorGlobal") or 0) for c in contratos)


def quantil(v):
    import bisect
    return bisect.bisect_left(valores, v) / max(len(valores), 1)


def classifica(c, desf, perfil):
    """Calcula DOIS escores na escala de probabilidade da Res. 781/2022:

      prob_ex  — EX-ANTE: só o que se sabia no dia da assinatura. É o escore que
                 o sistema teria exibido ao gestor no momento da decisão de
                 contratar, e o único comparável à predição do modelo de ML.
      prob     — OBSERVADO: acrescenta o que já aconteceu com o contrato
                 (aditivos, acréscimos, rescisão). Leitura retrospectiva, útil
                 para gestão de contratos vigentes.

    Cada fator é marcado com ex_ante=True/False para que o painel possa
    distinguir as duas leituras, e com o identificador (F1…F10, O1…O3) da
    tabela de pontos em escala_781.PESOS — o mesmo da planilha de validação.
    """
    P = E.PESOS
    fatores = []  # [texto, contribuição, ex_ante, id]
    prob = E.BASE_PONTOS      # observado (todos os fatores)
    prob_ex = E.BASE_PONTOS   # ex-ante (só fatores conhecidos na assinatura)

    def add(fid, texto, ex_ante):
        nonlocal prob, prob_ex
        pts = P[fid]
        fatores.append([texto, pts, ex_ante, fid])
        prob += pts
        if ex_ante:
            prob_ex += pts

    # -- fornecedor, pelo cadastro aberto da Receita (todos os fornecedores).
    #    Mesmas regras do baseline avaliado em treina_modelo.py: capital social
    #    comparado ao VALOR DO CONTRATO e idade do CNPJ NA DATA DA ASSINATURA.
    ini, fim = d(c.get("dataVigenciaInicio")), d(c.get("dataVigenciaFim"))
    ass = d(c.get("dataAssinatura")) or ini
    cad = CADASTROS.get(c.get("niFornecedor")) or {}
    valor = c.get("valorGlobal") or 0
    if cad:
        cap = cad.get("capital_social")
        if not cap:
            add("F3", "Capital social não informado na base aberta da Receita (comum em consórcios) — verificar", True)
        elif valor and cap / valor < 0.02:
            add("F1", f"Capital social (R$ {cap:,.0f}) inferior a 2% do valor do contrato (R$ {valor:,.0f})".replace(",", "."), True)
        elif valor and cap / valor > 0.3:
            add("F2", "Capital social superior a 30% do valor do contrato", True)
        abertura = d(cad.get("abertura"))
        if abertura and ass:
            idade = (ass - abertura).days / 365.25
            if idade < 3:
                add("F4", f"Empresa recente ({idade:.1f} ano(s) de CNPJ na assinatura)", True)
            elif idade > 10:
                add("F5", f"Empresa consolidada ({idade:.0f} anos de CNPJ na assinatura)", True)
        if (cad.get("situacao") or "").upper() not in ("", "ATIVA"):
            add("F7", f"Situação cadastral na Receita: {cad['situacao']}", True)
    # crescimento atípico exige a série nacional de contratos, coletada só para
    # os 15 maiores fornecedores (perfil)
    cresc = (perfil or {}).get("crescimento_recente")
    if cresc is not None and cresc >= 3:
        add("F6", f"Crescimento contratual atípico ({cresc:.1f}× a mediana histórica no PNCP)", True)

    # -- duração prevista (conhecida na assinatura)
    if ini and fim and (fim - ini).days > 360:
        add("F8", "Vigência superior a 12 meses (serviço continuado)", True)

    # -- sanção CEIS/CNEP em vigor E já publicada na data da assinatura: era
    #    consultável antes de contratar, logo é informação legitimamente ex-ante
    #    (vale para todos os fornecedores, não só o top-15 com perfil)
    sancs = sancoes_de(c.get("niFornecedor"))
    if sancs and ass:
        vig = [s for s in sancs if sancao_vigente_em(s, ass) and sancao_conhecida_em(s, ass)]
        if vig:
            s0 = vig[0]
            add("F9", f"Sanção vigente na assinatura ({s0['cadastro']}: {s0['tipo']} — {s0['orgao']})",
                True)

    # -- histórico do próprio contrato: SÓ observado (posterior à assinatura)
    if desf["n_aditivos"] >= 2:
        add("O1", f"{desf['n_aditivos']} termos aditivos já firmados", False)
    if desf["acrescimo_valor_pct"] > 0.10:
        add("O2", f"Valor acumulado {desf['acrescimo_valor_pct']*100:.0f}% acima do inicial", False)
    if desf["rescindido"]:
        add("O3", "Contrato com termo de rescisão/extinção registrado", False)

    prob_i = E.posicao_probabilidade(prob)        # 0,5 arredonda para cima
    prob_ex_i = E.posicao_probabilidade(prob_ex)
    # -- impacto: quantil do valor na carteira do STF (conhecido na assinatura)
    q = quantil(c.get("valorGlobal") or 0)
    imp_i = 1 + int(q * 4.999) if q < 1 else 5
    imp_i = max(1, min(5, imp_i))
    fatores.append([f"Impacto orçamentário: valor no percentil {q*100:.0f} da carteira STF", None, True, "IMP"])
    return prob_i, prob_ex_i, imp_i, fatores


def nivel(prob, imp):
    """Nível oficial da Res. 781/2022 a partir das posições ordinais 1–5
    (valores 1-2-5-8-10, risco inerente 0–100, faixas 10/40/80)."""
    return E.nivel(prob, imp)


# ------------------------------------------------------------------ montagem
ml_path = OUT / "ml_stf_v2.json"        # v2 calibrado tem precedência
if not ml_path.exists():
    ml_path = OUT / "ml_stf.json"       # fallback: v1
ml_stf = json.loads(ml_path.read_text(encoding="utf-8")) if ml_path.exists() else {}
ml_contratos = ml_stf.get("contratos") or {}


def nome_fator_ml(nome):
    """Torna legíveis os nomes de variáveis vindos do modelo.

    O ml_stf_v2.json (SHAP) já entrega nomes prontos e agregados por variável
    original; os prefixos crus abaixo só ocorrem no ml_stf.json da v1, mantido
    como fallback. O tratamento de 'faltante:' continua valendo para ambos.
    """
    if nome.startswith("orgao_"):
        return f"padrão histórico do órgão ({nome[6:]})"
    if nome.startswith("categoria_"):
        return f"categoria: {nome[10:]}"
    if nome.startswith("porte_"):
        return f"porte do fornecedor: {nome[6:].replace('DEMAIS', 'demais/grande')}"
    if nome.startswith("faltante: "):
        return f"dado indisponível ({nome[10:]})"
    return nome


for v in ml_contratos.values():
    v["fatores"] = [[nome_fator_ml(n), c] for n, c in v.get("fatores") or []]

procs = []
for c in contratos:
    desf = desfecho_contrato(c)
    perfil = perfis.get(c.get("niFornecedor"))
    prob, prob_ex, imp, fatores = classifica(c, desf, perfil)
    ini = c.get("dataVigenciaInicio")
    procs.append({
        "id": c.get("processo") or c.get("numeroControlePNCP"),
        "pncp": c.get("numeroControlePNCP"),
        "obj": (c.get("objetoContrato") or "").strip()[:220],
        "categoria": (c.get("categoriaProcesso") or {}).get("nome"),
        "valor": c.get("valorGlobal") or 0,
        "assinatura": c.get("dataAssinatura"),
        "vig_ini": ini, "vig_fim": c.get("dataVigenciaFim"),
        "forn_ni": c.get("niFornecedor"),
        "forn_nome": c.get("nomeRazaoSocialFornecedor"),
        "prob": prob, "imp": imp, "nivel": nivel(prob, imp),
        "prob_ex": prob_ex, "nivel_ex": nivel(prob_ex, imp),
        # risco inerente oficial (0–100) = valor da probabilidade × valor do impacto
        "score": E.pontuacao(prob, imp), "score_ex": E.pontuacao(prob_ex, imp),
        "sancoes": sancoes_de(c.get("niFornecedor")),
        "fatores": fatores, "desfecho": desf,
        "ml": ml_contratos.get(c.get("numeroControlePNCP")),
    })
procs.sort(key=lambda p: (p["assinatura"] or ""), reverse=True)

# ------------------------------------------------------------- preços (Mód. 1)
cat_precos = []
for cod, info in precos.items():
    ps = [p["preco"] for p in info["precos_nacionais"] if p.get("preco") and p["preco"] > 0]
    if len(ps) < 8 or not info.get("estimado_stf"):
        continue
    ps_sorted = sorted(ps)
    # poda outliers extremos (unidades de fornecimento heterogêneas — ver análise 2.4)
    n = len(ps_sorted)
    ps_core = ps_sorted[int(n * 0.05):max(int(n * 0.95), int(n * 0.05) + 1)]
    desc = info.get("rotulo") or info["descricao_stf"]
    if info.get("pdm_nome"):
        desc += f" · PDM {info['pdm_nome']}"
    cat_precos.append({
        "cod": cod, "tipo": info["tipo"],
        "desc": desc[:160], "un": info.get("unidade_stf"),
        "estimado_stf": info["estimado_stf"],
        "n_amostra": len(ps_core),
        "precos": ps_core[:120],
        "mediana": round(st.median(ps_core), 2),
    })

# ------------------------------------------------------------ KPIs e resumo
ALTOS = E.ALTOS
n_adversos = sum(1 for p in procs if p["desfecho"]["desfecho_adverso"])
adversos = [p for p in procs if p["desfecho"]["desfecho_adverso"]]
# quantos dos contratos que deram errado JÁ apareciam como Elevado/Crítico
# no escore ex-ante — ou seja, teriam sido sinalizados antes de contratar
adv_sinalizados = sum(1 for p in adversos if p["nivel_ex"] in ALTOS)
n_altos_ex = sum(1 for p in procs if p["nivel_ex"] in ALTOS)
resumo = {
    "coletado_em": HOJE.isoformat(),
    "orgao": "Supremo Tribunal Federal — CNPJ 00.531.640/0001-28",
    "n_contratos": len(procs),
    "n_registros_pncp": N_REGISTROS_BRUTOS,      # antes da deduplicação
    "valor_total": round(sum(p["valor"] for p in procs), 2),
    "n_aditivos": sum(p["desfecho"]["n_aditivos"] for p in procs),
    "n_rescindidos": sum(1 for p in procs if p["desfecho"]["rescindido"]),
    "n_desfecho_adverso": n_adversos,
    "pct_desfecho_adverso": round(100 * n_adversos / max(len(procs), 1), 1),
    "n_altos_ex_ante": n_altos_ex,
    "adversos_sinalizados_ex_ante": adv_sinalizados,
    "pct_adversos_sinalizados_ex_ante": round(100 * adv_sinalizados / max(n_adversos, 1), 1),
    # sanções: verificação realizada? em quantos contratos havia sanção vigente
    # e já publicada na data da assinatura?
    "sancoes_consulta": SANC_DATA.isoformat() if SANC_DATA else None,
    "fornecedores_verificados": len(SANCOES),
    "fornecedores_com_registro": sum(1 for v in SANCOES.values() if v.get("ceis") or v.get("cnep")),
    "contratos_sancao_na_assinatura": sum(
        1 for p in procs if any(f[0].startswith("Sanção vigente na assinatura") for f in p["fatores"])),
}

if ml_stf:
    resumo["modelo_ml"] = {"nome": ml_stf.get("modelo"),
                           "treino": ml_stf.get("treinado_em"),
                           "explicacao": ml_stf.get("explicacao"),
                           "fidelidade": ml_stf.get("fidelidade_shap_spearman")}

dados = {"resumo": resumo, "processos": procs,
         "fornecedores": sorted(perfis.values(), key=lambda p: -(p["valor_no_stf"] or 0)),
         "precos": cat_precos}
(OUT / "antecipa_dados.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
print(f"antecipa_dados.json: {len(procs)} processos, {len(perfis)} fornecedores, {len(cat_precos)} itens de preço")

# ------------------------------------------------------------- dataset de ML
with open(OUT / "dataset_ml.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["pncp", "valor_global", "duracao_dias", "categoria",
                "forn_capital_social", "forn_idade_anos", "forn_vol_nacional",
                "forn_n_contratos_nac", "forn_razao_capital_volume",
                "forn_crescimento_recente", "prob_heuristica_ex_ante",
                "prob_heuristica_observada", "imp_heuristica",
                "label_desfecho_adverso"])
    for p in procs:
        pf = perfis.get(p["forn_ni"]) or {}
        ini, fim = d(p["vig_ini"]), d(p["vig_fim"])
        dur = (fim - ini).days if ini and fim else ""
        w.writerow([p["pncp"], p["valor"], dur, p["categoria"],
                    pf.get("capital_social", ""), pf.get("idade_anos", ""),
                    pf.get("vol_nacional", ""), pf.get("contratos_nacionais", ""),
                    pf.get("razao_capital_volume", ""), pf.get("crescimento_recente", ""),
                    p["prob_ex"], p["prob"], p["imp"],
                    int(p["desfecho"]["desfecho_adverso"])])
print("dataset_ml.csv gravado (rótulo = desfecho real, não regra — ver análise crítica 2.1)")
