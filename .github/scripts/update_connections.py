"""
Substitui conexões locais (File.Contents) por links públicos do OneDrive (Web.Contents)
nos arquivos .tmdl do SemanticModel.

Os arquivos CSV devem estar previamente na pasta ONEDRIVE_FOLDER_PATH do OneDrive.
Este script cria um sharing link anônimo para cada CSV encontrado nas conexões
e substitui os caminhos locais pelas URLs geradas.

Suporta conta pessoal (refresh token) e corporativa (client credentials).
"""

import re
import sys
import os
import base64
import requests
from pathlib import Path

TMDL_DIR = Path("PBIP/Teste_Pbip.SemanticModel/definition")
FOLDER_PATH = os.environ.get("ONEDRIVE_FOLDER_PATH", "PBIP_Deploy")
GRAPH = "https://graph.microsoft.com/v1.0"

CLIENT_ID = os.environ.get("CLIENT_ID")
REFRESH_TOKEN = os.environ.get("ONEDRIVE_REFRESH_TOKEN")
TENANT_ID = os.environ.get("TENANT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
USER_ID = os.environ.get("ONEDRIVE_USER_ID")


def get_access_token() -> str:
    if not CLIENT_ID:
        print("ERROR: CLIENT_ID não configurado.", file=sys.stderr)
        sys.exit(1)

    if REFRESH_TOKEN:
        resp = requests.post(
            "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            data={
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "refresh_token": REFRESH_TOKEN,
                "scope": "Files.ReadWrite offline_access",
            },
        )
        if resp.status_code == 400:
            print("\nERROR: Refresh token inválido ou expirado (400).", file=sys.stderr)
            print("  Rode novamente: python .github/scripts/get_token.py", file=sys.stderr)
            print("  E atualize o secret ONEDRIVE_REFRESH_TOKEN no GitHub.", file=sys.stderr)
            sys.exit(1)
    elif CLIENT_SECRET and TENANT_ID:
        resp = requests.post(
            f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            },
        )
    else:
        print("ERROR: credenciais não encontradas.", file=sys.stderr)
        print("  Conta pessoal: defina CLIENT_ID e ONEDRIVE_REFRESH_TOKEN.", file=sys.stderr)
        print("  Conta corporativa: defina CLIENT_ID, TENANT_ID e CLIENT_SECRET.", file=sys.stderr)
        sys.exit(1)

    resp.raise_for_status()
    return resp.json()["access_token"]


def drive_root(token: str) -> str:
    if USER_ID:
        return f"{GRAPH}/users/{USER_ID}/drive/root:"
    return f"{GRAPH}/me/drive/root:"


def resolve_download_url(web_url: str) -> str:
    """Segue o redirect do link de compartilhamento e retorna a URL de download direto.

    O link de compartilhamento (1drv.ms) redireciona para onedrive.live.com/?authkey=...
    Trocando o path para /download obtemos uma URL permanente de download direto,
    que o Power BI acessa anonimamente sem precisar de credenciais extras.
    """
    try:
        resp = requests.get(web_url, allow_redirects=True, timeout=15, stream=True)
        resp.close()
        final_url = resp.url
        if "onedrive.live.com" in final_url and "?" in final_url:
            query = final_url.split("?", 1)[1]
            return f"https://onedrive.live.com/download?{query}"
    except requests.RequestException as e:
        print(f"  AVISO: não foi possível resolver URL direta ({e}).", file=sys.stderr)
    # Fallback: codificação via api.onedrive.com
    encoded = base64.urlsafe_b64encode(web_url.encode()).rstrip(b"=").decode()
    return f"https://api.onedrive.com/v1.0/shares/u!{encoded}/root/content"


def create_sharing_link(token: str, filename: str) -> str:
    root = drive_root(token)
    remote_path = f"{FOLDER_PATH}/{filename}"

    check = requests.get(
        f"{root}/{remote_path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    if check.status_code == 404:
        print(f"\nERROR: '{filename}' não encontrado em '{FOLDER_PATH}/' no OneDrive.", file=sys.stderr)
        print("  Verifique se o arquivo foi enviado manualmente antes de rodar o pipeline.", file=sys.stderr)
        sys.exit(1)
    check.raise_for_status()

    resp = requests.post(
        f"{root}/{remote_path}:/createLink",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"type": "view", "scope": "anonymous"},
    )
    resp.raise_for_status()

    web_url = resp.json()["link"]["webUrl"]
    return resolve_download_url(web_url)


def extract_filenames(content: str) -> list[str]:
    matches = re.findall(r'File\.Contents\("([^"]+)"\)', content)
    return [Path(m.replace("\\", "/")).name for m in matches]


def replace_connection(content: str, mapping: dict) -> tuple[str, list[str]]:
    replaced = []

    def substituir(match):
        local_path = match.group(1)
        filename = Path(local_path.replace("\\", "/")).name
        if filename in mapping:
            replaced.append(filename)
            return f'Web.Contents("{mapping[filename]}")'
        return match.group(0)

    new_content = re.sub(r'File\.Contents\("([^"]+)"\)', substituir, content)
    return new_content, replaced


def main() -> None:
    if not TMDL_DIR.exists():
        print(f"ERROR: Pasta {TMDL_DIR} não encontrada.", file=sys.stderr)
        sys.exit(1)

    tmdl_files = list(TMDL_DIR.rglob("*.tmdl"))
    print(f"Verificando {len(tmdl_files)} arquivo(s) .tmdl...\n")

    all_filenames: set[str] = set()
    for tmdl_file in tmdl_files:
        content = tmdl_file.read_text(encoding="utf-8")
        all_filenames.update(extract_filenames(content))

    if not all_filenames:
        print("Nenhuma conexão local encontrada para substituir.")
        return

    print(f"Conexões encontradas: {', '.join(sorted(all_filenames))}")
    print("\nAutenticando no OneDrive...")
    token = get_access_token()
    print("Token obtido.\n")

    mapping: dict[str, str] = {}
    for filename in sorted(all_filenames):
        print(f"  Criando link para '{filename}'...")
        mapping[filename] = create_sharing_link(token, filename)
        print(f"  OK  {filename}")

    print()

    total_replaced = []
    for tmdl_file in tmdl_files:
        content = tmdl_file.read_text(encoding="utf-8")
        new_content, replaced = replace_connection(content, mapping)
        if replaced:
            tmdl_file.write_text(new_content, encoding="utf-8")
            for name in replaced:
                print(f"  OK  {tmdl_file.name} → {name}")
            total_replaced.extend(replaced)

    if not total_replaced:
        print("Nenhuma conexão substituída.")
    else:
        print(f"\nConexões atualizadas: {len(total_replaced)}")


if __name__ == "__main__":
    main()
