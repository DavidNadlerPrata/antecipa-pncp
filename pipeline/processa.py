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
nas escalas 1–5 de probabilidade e impacto da Res. STF 781/2022. Não é ML — é a
régua de comparação sobre a qual o modelo supervisionado será avaliado.
"""
import csv
import json
import statistics as st
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "dados" / "brutos"
OUT = BASE / "dados" / "processados"
OUT.mkdir(parents=True, exist_ok=True)
HOJE = date(2026, 7, 20)


def load(nome):
    return json.loads((RAW / nome).read_text(encoding="utf-8"))


def d(s):
    try:
        return date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


contratos = load("contratos_stf.json")
termos = load("termos_stf.json")
fornecedores = load("fornecedores.json")
itens_stf = load("itens_stf.json")
precos = load("precos_referencia.json")

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
        "valor_no_stf": f.get("valor_no_stf"),
        "razao_capital_volume": round(capital / vol_nacional, 4) if vol_nacional else None,
        "crescimento_recente": round(cresc, 2) if cresc else None,
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
    distinguir as duas leituras.
    """
    fatores = []  # [texto, contribuição, ex_ante]
    prob = 1.0      # observado (todos os fatores)
    prob_ex = 1.0   # ex-ante (só fatores conhecidos na assinatura)

    def add(texto, pts, ex_ante):
        nonlocal prob, prob_ex
        fatores.append([texto, pts, ex_ante])
        prob += pts
        if ex_ante:
            prob_ex += pts

    # -- fornecedor (tudo conhecido na assinatura)
    if perfil:
        r = perfil.get("razao_capital_volume")
        if not perfil.get("capital_social"):
            add("Capital social não informado na base aberta da Receita (comum em consórcios) — verificar", 0.3, True)
        elif r is not None and r < 0.02:
            add(f"Capital social (R$ {perfil['capital_social']:,.0f}) muito inferior ao volume contratado nacional (R$ {perfil['vol_nacional']:,.0f})".replace(",", "."), 1.2, True)
        elif r is not None and r > 0.3:
            add("Capital social compatível com o volume contratado", -0.5, True)
        idade = perfil.get("idade_anos")
        if idade is not None and idade < 3:
            add(f"Empresa recente ({idade:.1f} ano(s) de CNPJ)", 0.8, True)
        elif idade is not None and idade > 10:
            add(f"Empresa consolidada ({idade:.0f} anos de CNPJ)", -0.4, True)
        cresc = perfil.get("crescimento_recente")
        if cresc is not None and cresc >= 3:
            add(f"Crescimento contratual atípico ({cresc:.1f}× a mediana histórica no PNCP)", 1.0, True)
        if perfil.get("situacao") and perfil["situacao"].upper() != "ATIVA":
            add(f"Situação cadastral na Receita: {perfil['situacao']}", 1.5, True)
    else:
        add("Fornecedor fora do top-15 monitorado (perfil nacional não coletado)", 0.3, True)

    # -- duração prevista (conhecida na assinatura)
    ini, fim = d(c.get("dataVigenciaInicio")), d(c.get("dataVigenciaFim"))
    if ini and fim and (fim - ini).days > 360:
        add("Vigência superior a 12 meses (serviço continuado)", 0.4, True)

    # -- histórico do próprio contrato: SÓ observado (posterior à assinatura)
    if desf["n_aditivos"] >= 2:
        add(f"{desf['n_aditivos']} termos aditivos já firmados", 0.8, False)
    if desf["acrescimo_valor_pct"] > 0.10:
        add(f"Valor acumulado {desf['acrescimo_valor_pct']*100:.0f}% acima do inicial", 0.8, False)
    if desf["rescindido"]:
        add("Contrato com termo de rescisão/extinção registrado", 1.5, False)

    prob_i = max(1, min(5, round(prob)))
    prob_ex_i = max(1, min(5, round(prob_ex)))
    # -- impacto: quantil do valor na carteira do STF (conhecido na assinatura)
    q = quantil(c.get("valorGlobal") or 0)
    imp_i = 1 + int(q * 4.999) if q < 1 else 5
    imp_i = max(1, min(5, imp_i))
    fatores.append([f"Impacto orçamentário: valor no percentil {q*100:.0f} da carteira STF", None, True])
    return prob_i, prob_ex_i, imp_i, fatores


NIVEIS = [(4, "Baixo"), (9, "Moderado"), (16, "Elevado"), (25, "Crítico")]


def nivel(prob, imp):
    s = prob * imp
    for mx, n in NIVEIS:
        if s <= mx:
            return n


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
ALTOS = ("Elevado", "Crítico")
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
    "valor_total": round(sum(p["valor"] for p in procs), 2),
    "n_aditivos": sum(p["desfecho"]["n_aditivos"] for p in procs),
    "n_rescindidos": sum(1 for p in procs if p["desfecho"]["rescindido"]),
    "n_desfecho_adverso": n_adversos,
    "pct_desfecho_adverso": round(100 * n_adversos / max(len(procs), 1), 1),
    "n_altos_ex_ante": n_altos_ex,
    "adversos_sinalizados_ex_ante": adv_sinalizados,
    "pct_adversos_sinalizados_ex_ante": round(100 * adv_sinalizados / max(n_adversos, 1), 1),
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
