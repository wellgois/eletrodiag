"""Monta o app estático: injeta o dicionário de falhas (gold) e o motor JS num único HTML.

Saídas:
  app/index.html                      página autônoma (abre direto no navegador)
  app/build/eletrodiag-artifact.html  mesmo conteúdo sem esqueleto, para publicar como artefato
"""
from __future__ import annotations

from .pipeline import config as C


def build() -> dict:
    app = C.REPO / "app"
    template = (app / "index.template.html").read_text(encoding="utf-8")
    dictionary = (C.GOLD / "app" / "dictionary.json").read_text(encoding="utf-8")
    js = (app / "diagnose.js").read_text(encoding="utf-8")
    page = template.replace("/*__DICTIONARY__*/null", dictionary).replace("/*__DIAGNOSE_JS__*/", js)
    head, content = page.split("<!--BODY-->")
    standalone = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        f"{head}</head>\n<body>{content}</body>\n</html>\n"
    )
    (app / "index.html").write_text(standalone, encoding="utf-8")
    (app / "build").mkdir(exist_ok=True)
    (app / "build" / "eletrodiag-artifact.html").write_text(head + content, encoding="utf-8")
    return {"app_bytes": len(standalone.encode()), "dictionary_version": __import__("json").loads(dictionary)["version"]}
