#!/usr/bin/env bash
# Instala o serviço de leitura de fotos (Python padrão, sem pip). Rode na VPS, :
#   sudo bash instalar_fotos.sh
# Pede a chave da Anthropic e escolhe um código de acesso; grava em /etc/eletrodiag.env (só root lê).
set -euo pipefail
D=/opt/eletrodiag-board; mkdir -p $D/eletrodiag; touch $D/eletrodiag/__init__.py
cat > $D/eletrodiag/board_api.py <<'PYEOF'
"""Serviço que lê fotos da placa com o Claude e devolve o que viu, para o app montar o diagrama.

Só biblioteca padrão (roda com `python3 -m eletrodiag.board_api`, sem pip). Fica atrás do nginx, em /api/.
O app envia as fotos (JPEG reduzido) e um resumo do que já se sabe; o serviço chama a API da Anthropic com uma
ferramenta de saída estruturada e devolve só um "delta" saneado (peças, ligações, perguntas). Quem mescla é o app.

Variáveis de ambiente:
  ANTHROPIC_API_KEY  chave da API (obrigatória; fica só na VPS, nunca vai ao navegador)
  BOARD_TOKEN        código de acesso que o dono digita no app (obrigatório: sem ele qualquer visitante gastaria a chave)
  BOARD_MODEL        modelo (padrão claude-sonnet-5-5)
  BOARD_DAILY_LIMIT  análises por dia (padrão 40)
  BOARD_PORT         porta local (padrão 8787)
As fotos não são gravadas em disco nem registradas em log.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_URL = "https://api.anthropic.com/v1/messages"
MAX_IMAGES, MAX_IMAGE_BYTES, MAX_BODY = 4, 3_000_000, 14_000_000
KINDS = ["mosfet", "igbt", "diodo", "resistor", "capacitor", "ci", "transformador", "fusivel", "fio", "conector", "transistor", "outro"]
BLOCKS = ["entrada", "comando", "controle", "primario", "trafo", "barramento", "ponte_h", "saida", "desconhecido"]
LINK_KINDS = ["trilha", "fio", "jumper", "componente"]
TOOL_NAME = "registrar_leitura"

TOOL = {
    "name": TOOL_NAME,
    "description": "Registra o que as fotos mostram da placa: peças identificadas, ligações visíveis e o que falta ver.",
    "input_schema": {
        "type": "object",
        "properties": {
            "parts": {"type": "array", "maxItems": 60, "items": {"type": "object", "properties": {
                "id": {"type": "string", "description": "Posição serigrafada (Q22, R59, U1...). Reutilize os ids já conhecidos."},
                "kind": {"type": "string", "enum": KINDS},
                "marking": {"type": "string", "description": "Texto impresso no corpo, exatamente como lido; use ? nas letras incertas."},
                "model": {"type": "string", "description": "Modelo provável, se a marcação permitir; vazio se não souber."},
                "block": {"type": "string", "enum": BLOCKS},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "string", "description": "O que na foto sustenta a leitura (foto N, onde)."}},
                "required": ["id", "kind", "block", "confidence", "evidence"]}},
            "links": {"type": "array", "maxItems": 60, "items": {"type": "object", "properties": {
                "a": {"type": "string", "description": "Ponto A, como PEÇA.PINO (Q22.E) ou só a peça."},
                "b": {"type": "string"},
                "kind": {"type": "string", "enum": LINK_KINDS},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "string"}}, "required": ["a", "b", "confidence", "evidence"]}},
            "open_questions": {"type": "array", "maxItems": 8, "items": {"type": "string"},
                               "description": "O que não deu para ver e qual foto ou medição resolveria."},
        },
        "required": ["parts", "links", "open_questions"],
    },
}

SYSTEM = (
    "Você ajuda a fazer engenharia reversa de uma placa de inversor CC-CA (12 V para 110 V) a partir de fotos.\n"
    "Regras:\n"
    "1. Registre só o que está visível. Nunca invente trilhas escondidas sob componentes, sob verniz ou no outro lado da placa.\n"
    "2. Copie as marcações exatamente como lidas; use ? nas letras incertas. Não complete códigos de memória.\n"
    "3. A confiança deve ser calibrada: 0,9 ou mais só para texto nítido; 0,5 ou menos para leitura duvidosa.\n"
    "4. Ligue dois pontos só quando a trilha ou o fio for contínuo na foto; senão, não registre a ligação e faça uma pergunta.\n"
    "5. Reutilize os ids e blocos já conhecidos. Os fatos marcados como confirmados pelo dono não devem ser contestados.\n"
    "6. Atribua cada peça a um bloco: entrada, comando (drivers de gate), controle (CI PWM), primario (MOSFETs de baixa tensão "
    "e trafo), trafo, barramento (retificador e capacitores de alta tensão), ponte_h (IGBTs ou MOSFETs de saída), saida (filtro) "
    "ou desconhecido.\n"
    "7. Em open_questions, peça a foto ou o teste de continuidade que mais reduziria a dúvida (ex.: foto de perto do CI U1)."
)


def summarize_known(model: dict | None) -> str:
    """Resumo curto do modelo atual para o prompt (o app manda o modelo inteiro; aqui só entra o essencial)."""
    if not isinstance(model, dict):
        return "Nenhum fato prévio."
    lines = []
    for p in list((model.get("parts") or {}).values())[:80]:
        if not isinstance(p, dict):
            continue
        st = "CONFIRMADO pelo dono" if p.get("status") == "confirmado" else "hipótese"
        lines.append(f"- {str(p.get('id'))[:20]} ({str(p.get('kind'))[:12]}, bloco {str(p.get('block'))[:14]}): "
                     f"{str(p.get('model') or p.get('marking') or '')[:60]} [{st}]")
    open_q = [str(q)[:160] for q in (model.get("open_questions") or [])[:6]]
    out = "Já se sabe:\n" + ("\n".join(lines) if lines else "(nada)")
    if open_q:
        out += "\nPerguntas abertas:\n" + "\n".join(f"- {q}" for q in open_q)
    return out


def decode_images(images: list) -> list[dict]:
    """Valida as fotos recebidas (data URL base64 de JPEG, PNG ou WebP) e monta os blocos de imagem da API."""
    if not isinstance(images, list) or not 1 <= len(images) <= MAX_IMAGES:
        raise ValueError(f"envie de 1 a {MAX_IMAGES} fotos")
    blocks = []
    magic = {"image/jpeg": (b"\xff\xd8\xff",), "image/png": (b"\x89PNG",), "image/webp": (b"RIFF",)}
    for img in images:
        if not isinstance(img, str) or not img.startswith("data:") or ";base64," not in img:
            raise ValueError("foto em formato inválido")
        head, data = img.split(";base64,", 1)
        mt = head[5:]
        if mt not in magic:
            raise ValueError("só JPEG, PNG ou WebP")
        try:
            raw = base64.b64decode(data, validate=True)
        except Exception as e:  # noqa: BLE001
            raise ValueError("base64 inválido") from e
        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError("foto grande demais (reduza para até ~3 MB)")
        if not raw.startswith(magic[mt]):
            raise ValueError("o conteúdo não é a imagem declarada")
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
    return blocks


def build_request(blocks: list[dict], known: str, hint: str, model_name: str) -> dict:
    text = (f"{known}\n\n"
            f"{('Observação do dono: ' + hint[:400]) if hint else ''}\n"
            f"Analise as {len(blocks)} foto(s) acima, na ordem em que foram enviadas (foto 1, foto 2...), e registre a leitura.")
    return {"model": model_name, "max_tokens": 4096, "system": SYSTEM,
            "tools": [TOOL], "tool_choice": {"type": "tool", "name": TOOL_NAME},
            "messages": [{"role": "user", "content": blocks + [{"type": "text", "text": text}]}]}


def call_anthropic(payload: dict, api_key: str, timeout: float = 150.0) -> dict:
    req = urllib.request.Request(API_URL, data=json.dumps(payload).encode(), method="POST",
                                 headers={"content-type": "application/json", "x-api-key": api_key,
                                          "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL fixa, https)
        return json.loads(r.read())


def _s(x, n):
    return str(x if x is not None else "")[:n]


def _num(x):
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def sanitize(tool_input: dict) -> dict:
    """Nada do que o modelo devolve entra no app sem checagem de tipo, tamanho e valores permitidos."""
    out = {"parts": [], "links": [], "open_questions": []}
    for p in (tool_input.get("parts") or [])[:60]:
        if not isinstance(p, dict) or not _s(p.get("id"), 24).strip():
            continue
        out["parts"].append({"id": _s(p["id"], 24).strip().upper(), "kind": p.get("kind") if p.get("kind") in KINDS else "outro",
                             "marking": _s(p.get("marking"), 60), "model": _s(p.get("model"), 80),
                             "block": p.get("block") if p.get("block") in BLOCKS else "desconhecido",
                             "confidence": _num(p.get("confidence")), "evidence": _s(p.get("evidence"), 200)})
    for l in (tool_input.get("links") or [])[:60]:
        if not isinstance(l, dict) or not _s(l.get("a"), 30).strip() or not _s(l.get("b"), 30).strip():
            continue
        out["links"].append({"a": _s(l["a"], 30).strip().upper(), "b": _s(l["b"], 30).strip().upper(),
                             "kind": l.get("kind") if l.get("kind") in LINK_KINDS else "trilha",
                             "confidence": _num(l.get("confidence")), "evidence": _s(l.get("evidence"), 200)})
    out["open_questions"] = [_s(q, 200) for q in (tool_input.get("open_questions") or [])[:8] if _s(q, 200).strip()]
    return out


class Quota:
    def __init__(self, limit: int):
        self.limit, self.day, self.n, self.lock = limit, time.strftime("%Y-%m-%d"), 0, threading.Lock()

    def take(self) -> bool:
        with self.lock:
            today = time.strftime("%Y-%m-%d")
            if today != self.day:
                self.day, self.n = today, 0
            if self.n >= self.limit:
                return False
            self.n += 1
            return True


def analyze(body: dict, cfg: dict) -> dict:
    blocks = decode_images(body.get("images"))
    payload = build_request(blocks, summarize_known(body.get("model")), _s(body.get("hint"), 400), cfg["model"])
    resp = cfg.get("call", call_anthropic)(payload, cfg["api_key"])
    tool = next((b for b in resp.get("content", []) if b.get("type") == "tool_use" and b.get("name") == TOOL_NAME), None)
    if tool is None:
        raise RuntimeError("o modelo não devolveu a leitura estruturada")
    u = resp.get("usage") or {}
    return {"delta": sanitize(tool.get("input") or {}), "usage": {"in": u.get("input_tokens"), "out": u.get("output_tokens")}}


def make_handler(cfg: dict):
    quota = Quota(cfg["limit"])

    class H(BaseHTTPRequestHandler):
        server_version = "board-api"

        def log_message(self, *a):  # sem log de requisição: o corpo tem fotos e o cabeçalho tem o código de acesso
            pass

        def _send(self, code: int, obj: dict):
            data = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("content-type", "application/json; charset=utf-8")
            self.send_header("content-length", str(len(data)))
            self.send_header("cache-control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") == "/api/board/health":
                return self._send(200, {"ok": True, "model": cfg["model"], "limit_per_day": cfg["limit"]})
            self._send(404, {"error": "não encontrado"})

        def do_POST(self):  # noqa: N802
            if self.path.rstrip("/") != "/api/board/analyze":
                return self._send(404, {"error": "não encontrado"})
            token = self.headers.get("X-Board-Token", "")
            if not hmac.compare_digest(token.encode(), cfg["token"].encode()):
                return self._send(401, {"error": "código de acesso inválido"})
            try:
                n = int(self.headers.get("content-length", "0"))
            except ValueError:
                n = 0
            if not 0 < n <= MAX_BODY:
                return self._send(413, {"error": "envio vazio ou grande demais"})
            try:
                body = json.loads(self.rfile.read(n))
                if not isinstance(body, dict):
                    raise ValueError("corpo inválido")
                decode_images(body.get("images"))  # valida antes de gastar a cota
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            if not quota.take():
                return self._send(429, {"error": "limite diário de análises atingido"})
            try:
                self._send(200, analyze(body, cfg))
            except urllib.error.HTTPError as e:
                self._send(502, {"error": f"a API do modelo respondeu {e.code}"})
            except (urllib.error.URLError, TimeoutError):
                self._send(502, {"error": "não consegui falar com a API do modelo"})
            except Exception as e:  # noqa: BLE001
                self._send(502, {"error": _s(e, 160)})

    return H


def config_from_env() -> dict:
    key, token = os.environ.get("ANTHROPIC_API_KEY", ""), os.environ.get("BOARD_TOKEN", "")
    if not key or len(token) < 8:
        raise SystemExit("defina ANTHROPIC_API_KEY e BOARD_TOKEN (mínimo de 8 caracteres)")
    return {"api_key": key, "token": token, "model": os.environ.get("BOARD_MODEL", "claude-sonnet-5-5"),
            "limit": int(os.environ.get("BOARD_DAILY_LIMIT", "40"))}


def main() -> None:
    cfg = config_from_env()
    port = int(os.environ.get("BOARD_PORT", "8787"))
    ThreadingHTTPServer(("127.0.0.1", port), make_handler(cfg)).serve_forever()


if __name__ == "__main__":
    main()
PYEOF
if [ ! -f /etc/eletrodiag.env ]; then
  read -rsp "Chave da API da Anthropic (sk-ant-...): " KEY; echo
  read -rsp "Código de acesso que você vai digitar no app (mín. 8 caracteres): " TOK; echo
  umask 077
  printf 'ANTHROPIC_API_KEY=%s\nBOARD_TOKEN=%s\nBOARD_DAILY_LIMIT=40\nPYTHONPATH=%s\n' "$KEY" "$TOK" "$D" > /etc/eletrodiag.env
fi
cat > /etc/systemd/system/eletrodiag-board.service <<UNIT
[Unit]
Description=EletroDiag leitura de fotos da placa
After=network.target
[Service]
EnvironmentFile=/etc/eletrodiag.env
ExecStart=/usr/bin/python3 -m eletrodiag.board_api
Restart=on-failure
DynamicUser=yes
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload && systemctl enable --now eletrodiag-board && systemctl restart eletrodiag-board
# nginx: encaminha /api/ para o serviço (em todos os blocos server do site, inclusive o HTTPS do certbot)
SITE=/etc/nginx/sites-available/multimetro
if ! grep -q "location /api/" "$SITE"; then
  sed -i '/location \/ {/i\  location /api/ { proxy_pass http://127.0.0.1:8787; client_max_body_size 14m; proxy_read_timeout 180s; }' "$SITE"
fi
nginx -t && systemctl reload nginx
sleep 1; curl -s http://127.0.0.1:8787/api/board/health; echo
