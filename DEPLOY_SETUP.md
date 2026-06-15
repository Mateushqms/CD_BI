# Deploy PBIP → OneDrive via GitHub Actions

Pipeline que envia automaticamente os arquivos do projeto PBIP para o OneDrive sempre que houver um push na branch `main` com alterações na pasta `PBIP/`.

---

## Estrutura dos scripts

```
.github/
├── workflows/
│   └── deploy-onedrive.yml       # Pipeline principal
└── scripts/
    ├── upload_personal.py        # Upload via conta pessoal (@outlook.com)
    ├── upload_corporate.py       # Upload via conta corporativa
    └── get_token.py              # Geração do refresh token (somente conta pessoal)
```

---

## Conta Pessoal (@outlook.com / @hotmail.com)

### Como funciona

O deploy usa **Delegated Authorization com Refresh Token**. Você se autentica uma vez localmente e o token gerado é salvo como secret no GitHub. A pipeline o usa em cada deploy para obter um novo access token.

```
1ª vez:  Você → navegador → login Microsoft → aprova → refresh token gerado
Deploys: GitHub Actions → troca refresh token por access token → upload OneDrive
```

> O refresh token expira após **90 dias sem uso**. Se a pipeline rodar ao menos uma vez nesse período, ele se renova automaticamente.

---

### Passo 1 — Criar o App Registration no Azure

1. Acesse [portal.azure.com](https://portal.azure.com)
2. Vá em **Microsoft Entra ID → App registrations → New registration**
3. Preencha:
   - **Name:** qualquer nome (ex: `github-pbip-deploy`)
   - **Supported account types:** `Personal Microsoft accounts only`
4. Clique em **Register**
5. Anote o **Application (client) ID** — você vai precisar dele

---

### Passo 2 — Configurar o App como cliente público

1. No App Registration, vá em **Authentication**
2. Clique em **Add a platform → Mobile and desktop applications**
3. Marque o redirect URI: `https://login.microsoftonline.com/common/oauth2/nativeclient`
4. Em **Advanced settings**, mude **Allow public client flows** para **Yes**
5. Clique em **Save**

---

### Passo 3 — Adicionar permissões

1. Vá em **API permissions → Add a permission → Microsoft Graph**
2. Selecione **Delegated permissions** e adicione:
   - `Files.ReadWrite`
   - `offline_access`
3. Clique em **Add permissions**

> Não é necessário admin consent para permissões delegadas em conta pessoal.

---

### Passo 4 — Gerar o Refresh Token (uma vez só)

No terminal, dentro do repositório:

```bash
pip install requests
python .github/scripts/get_token.py
```

O script vai pedir o `CLIENT_ID`, exibir um link e um código. Abra o link no navegador, faça login com sua conta `@outlook.com` e autorize o app. O refresh token será impresso no terminal.

---

### Passo 5 — Configurar Secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|---|---|
| `CLIENT_ID` | Application (client) ID do App Registration |
| `ONEDRIVE_REFRESH_TOKEN` | Token gerado pelo `get_token.py` |

---

### Passo 6 — (Opcional) Definir pasta de destino

**Settings → Secrets and variables → Actions → Variables → New repository variable**

| Variável | Valor padrão |
|---|---|
| `ONEDRIVE_FOLDER_PATH` | `PBIP_Deploy` |

---

## Conta Corporativa / Universitária

### Como funciona

O deploy usa **Client Credentials Flow**. O App se autentica diretamente sem interação humana — ideal para CI/CD.

```
GitHub Actions → Azure AD (client_id + secret) → access token → upload OneDrive for Business
```

> Não expira enquanto o `CLIENT_SECRET` for válido. Totalmente automático.

---

### Passo 1 — Criar o App Registration no Azure da organização

> O App deve ser criado no **tenant da organização** (Azure AD da empresa/universidade), não em conta pessoal.

1. Acesse [portal.azure.com](https://portal.azure.com) com a conta corporativa
2. Vá em **Microsoft Entra ID → App registrations → New registration**
3. Preencha:
   - **Name:** qualquer nome (ex: `github-pbip-deploy`)
   - **Supported account types:** `Accounts in this organizational directory only`
4. Clique em **Register**
5. Anote o **Application (client) ID** e o **Directory (tenant) ID**

---

### Passo 2 — Criar um Client Secret

1. No App Registration, vá em **Certificates & secrets → New client secret**
2. Defina uma descrição e prazo de expiração
3. Clique em **Add** e **copie o valor imediatamente** (ele só aparece uma vez)

---

### Passo 3 — Adicionar permissões

1. Vá em **API permissions → Add a permission → Microsoft Graph**
2. Selecione **Application permissions** e adicione:
   - `Files.ReadWrite.All`
3. Clique em **Add permissions**
4. Clique em **Grant admin consent for [organização]** e confirme

> Admin consent é obrigatório para Application permissions. Sem ele o deploy retorna 403.

---

### Passo 4 — Provisionar o OneDrive do usuário alvo

O usuário cujo OneDrive será usado precisa ter acessado o OneDrive ao menos uma vez para que o drive seja criado no sistema da Microsoft. Peça para ele acessar o OneDrive pelo navegador antes de rodar o deploy pela primeira vez.

---

### Passo 5 — Configurar Secrets no GitHub

No repositório: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Valor |
|---|---|
| `TENANT_ID` | Directory (tenant) ID do Azure AD |
| `CLIENT_ID` | Application (client) ID do App Registration |
| `CLIENT_SECRET` | Secret gerado no Passo 2 |
| `ONEDRIVE_USER_ID` | Email corporativo do usuário alvo (ex: `user@empresa.com`) |

---

### Passo 6 — (Opcional) Definir pasta de destino

**Settings → Secrets and variables → Actions → Variables → New repository variable**

| Variável | Valor padrão |
|---|---|
| `ONEDRIVE_FOLDER_PATH` | `PBIP_Deploy` |

---

### Passo 7 — Alterar o script usado no workflow

Edite `.github/workflows/deploy-onedrive.yml` e mude o script chamado:

```yaml
# de:
run: python .github/scripts/upload_personal.py

# para:
run: python .github/scripts/upload_corporate.py
```

E atualize as variáveis de ambiente no mesmo step:

```yaml
env:
  TENANT_ID: ${{ secrets.TENANT_ID }}
  CLIENT_ID: ${{ secrets.CLIENT_ID }}
  CLIENT_SECRET: ${{ secrets.CLIENT_SECRET }}
  ONEDRIVE_USER_ID: ${{ secrets.ONEDRIVE_USER_ID }}
  ONEDRIVE_FOLDER_PATH: ${{ vars.ONEDRIVE_FOLDER_PATH || 'PBIP_Deploy' }}
```

---

## Comparativo rápido

| | Conta Pessoal | Conta Corporativa |
|---|---|---|
| Tipo de conta | `@outlook.com`, `@hotmail.com` | `@empresa.com`, `@universidade.edu` |
| Autenticação | Refresh token (passo manual inicial) | Client credentials (totalmente automático) |
| Expira? | 90 dias sem uso | Somente quando o client secret expirar |
| Admin consent necessário? | Não | Sim |
| Script usado | `upload_personal.py` | `upload_corporate.py` |

---

## Arquivos excluídos do upload

O script respeita o `.gitignore` do projeto e nunca envia:

- `localSettings.json` — configurações locais da máquina
- `cache.abf` — cache binário do Analysis Services
- `.gitignore`
