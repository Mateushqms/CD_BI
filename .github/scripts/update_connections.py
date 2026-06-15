"""
Atualiza conexoes nos arquivos .tmdl do SemanticModel, substituindo o caminho
original pelo caminho local da pasta do OneDrive sincronizado.

Variavel necessaria:
  ONEDRIVE_LOCAL_PATH - Caminho completo da pasta onde estao os CSVs no OneDrive
                        ex: C:/Users/usuario/OneDrive/PBIP_Deploy

Resultado:
  File.Contents("qualquer/caminho/arquivo.csv")
  -> File.Contents("C:/Users/usuario/OneDrive/PBIP_Deploy/arquivo.csv")
"""

import re
import sys
import os
from pathlib import Path

TMDL_DIR = Path("PBIP/Teste_Pbip.SemanticModel/definition")
ONEDRIVE_LOCAL_PATH = os.environ.get("ONEDRIVE_LOCAL_PATH", "")


def build_new_path(filename: str) -> str:
    base = ONEDRIVE_LOCAL_PATH.rstrip("/\\")
    return base + "\\" + filename


def replace_connection(content: str) -> tuple[str, list[str]]:
    replaced = []

    def substituir(match):
        local_path = match.group(1)
        filename = Path(local_path.replace("\\", "/")).name
        replaced.append(filename)
        return 'File.Contents("' + build_new_path(filename) + '")'

    new_content = re.sub(r'File\.Contents\("([^"]+)"\)', substituir, content)
    return new_content, replaced


def main() -> None:
    if not ONEDRIVE_LOCAL_PATH:
        print("ERROR: ONEDRIVE_LOCAL_PATH nao configurado.", file=sys.stderr)
        print("  Adicione em: Settings -> Variables -> Actions -> New repository variable", file=sys.stderr)
        print("  Nome: ONEDRIVE_LOCAL_PATH", file=sys.stderr)
        print("  Valor: caminho completo da pasta dos CSVs no OneDrive", file=sys.stderr)
        sys.exit(1)

    if not TMDL_DIR.exists():
        print(f"ERROR: Pasta {TMDL_DIR} nao encontrada.", file=sys.stderr)
        sys.exit(1)

    tmdl_files = list(TMDL_DIR.rglob("*.tmdl"))
    print(f"Verificando {len(tmdl_files)} arquivo(s) .tmdl...\n")

    total_replaced = []
    for tmdl_file in tmdl_files:
        content = tmdl_file.read_text(encoding="utf-8")
        new_content, replaced = replace_connection(content)

        if replaced:
            tmdl_file.write_text(new_content, encoding="utf-8")
            for name in replaced:
                print(f"  OK  {tmdl_file.name} -> {name}")
            total_replaced.extend(replaced)

    if not total_replaced:
        print("Nenhuma conexao encontrada para substituir.")
    else:
        print(f"\nConexoes atualizadas: {len(total_replaced)}")
        print(f"Caminho aplicado: {ONEDRIVE_LOCAL_PATH}")


if __name__ == "__main__":
    main()
