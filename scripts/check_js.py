"""
Valida a sintaxe de todo <script> inline do public/index.html com `node --check`.

Existe porque ja entrou em producao um erro de runtime que o olho nao pegou
('nderer3D' em vez de 'renderer3D'). node --check pega erro de SINTAXE; erro
de referencia continua exigindo teste de verdade — mas e a primeira barreira.
"""
import re
import subprocess
import sys
import tempfile
import pathlib

html = pathlib.Path("public/index.html").read_text(encoding="utf-8")
blocks = re.findall(r"<script(?![^>]*src)[^>]*>(.*?)</script>", html, re.S)
if not blocks:
    print("Nenhum script inline encontrado — index.html mudou de forma?")
    sys.exit(1)

falhas = 0
for i, code in enumerate(blocks):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    status = "OK" if r.returncode == 0 else "ERRO"
    print(f"script[{i}] ({len(code)} chars): {status}")
    if r.returncode != 0:
        print(r.stderr)
        falhas += 1

sys.exit(1 if falhas else 0)
