# -*- coding: utf-8 -*-
"""Injeta dados/processados/antecipa_dados.json no template e grava o
dashboard final em ../../ANTECIPA_dashboard_real.html (raiz da pasta unb)."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
dados = (BASE / "dados" / "processados" / "antecipa_dados.json").read_text(encoding="utf-8")
template = (BASE / "pipeline" / "dashboard_template.html").read_text(encoding="utf-8")
html = template.replace("/*__DADOS__*/null", dados, 1)
destino = BASE.parent / "ANTECIPA_dashboard_real.html"
destino.write_text(html, encoding="utf-8")
print(f"{destino} ({destino.stat().st_size/1024:.0f} KB)")
