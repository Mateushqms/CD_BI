"""
Atualiza conexões nos arquivos .tmdl do SemanticModel, substituindo o caminho
original pelo caminho local da pasta do OneDrive sincronizado.

Variáveis necessárias:
  ONEDRIVE_LOCAL_PATH  - Caminho local da pasta raiz do OneDrive (ex: C:\Users\usuario\OneDrive)
  ONEDRIVE_FOLDER_PATH - Subpasta de destino no OneDrive (default: PBIP_Deploy)

Resultado: File.Contents("qualquer\caminho\arquivo.csv")
        → File.Contents("C:\Users\usuario\OneDrive\PBIP_Deploy\arquivo.csv")
"""

import re
import sys
import os
from pathlib import Path

TMDL_DIR = Path("PBIP/Teste_Pbip.SemanticModel/definition")
ONEDRIVE_LOCAL_PATH = os.environ.get("ONEDRIVE_LOCAL_PATH", "")
FOLDER_PATH = os.environ.get("ONEDRIVE_FOLDER_PATH", "PBIP_Deploy")


def build_new_path(filename: str) -> str:
    base = ONEDRIVE_LOCAL_PATH.rstrip("\\/")
    return f"{base}\\{FOLDER_PATH}\\{filename}"


def replace_connection(content: str) -> tuple[str, list[str]]:
    replaced = []

    def substituir(match):
        local_path = match.group(1)
        filename = Path(local_path.replace("\\", "/")).name
        replaced.append(filename)
        return f'File.Contents("{build_new_path(filename)}")'

    new_content = re.sub(r'File\.Contents\("([^"]+)"\)', substituir, content)
    return new_content, replaced


def main() -> None:
    if not ONEDRIVE_LOCAL_PATH:
        print("ERROR: ONEDRIVE_LOCAL_PATH não configurado.", file=sys.stderr)
        print("  Adicione em: Settings → Variables → Actions → New repository variable", file=sys.stderr)
        print("  Nome: ONEDRIVE_LOCAL_PATH", file=sys.stderr)
        print("  Valor: ex. C:\\Users\\usuario\\OneDrive", file=sys.stderr)
        sys.exit(1)

    if not TMDL_DIR.exists():
        print(f"ERROR: Pasta {TMDL_DIR} não encontrada.", file=sys.stderr)
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
                print(f"  OK  {tmdl_file.name} → {name}")
            total_replaced.extend(replaced)

    if not total_replaced:
        print("Nenhuma conexão encontrada para substituir.")
    else:
        print(f"\nConexões atualizadas: {len(total_replaced)}")
        print(f"Caminho base aplicado: {ONEDRIVE_LOCAL_PATH}\\{FOLDER_PATH}\\")


if __name__ == "__main__":
    main()
