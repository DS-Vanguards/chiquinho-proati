# Proati — Inventário de equipamentos

Sistema de contabilização de tablets e notebooks do curso técnico, com login, cargos e persistência no Neon (PostgreSQL).

## Cargos

| Cargo | Acesso |
|---|---|
| **Admin** | Todas as abas + administração de usuários. Pode adicionar, alterar e remover equipamentos. |
| **Proati** | Tablets, Regular, Técnico, Manutenção e Manutenção Técnico. Pode adicionar, alterar e remover. |
| **Coordenador** | Visualiza todas as abas de equipamentos, sem editar. |
| **Visualizador** | Cargo padrão ao criar conta. Vê apenas a tela de acesso restrito. |

Login fixo de administrador:

- usuário: `admin`
- senha: `adminvgsproati`

Cadastro público só aceita e-mails `@prof.educacao.sp.gov.br` e `@professor.educacao.sp.gov.br`.

## Como rodar

1. Crie um banco no [Neon](https://neon.tech) e copie a connection string.
2. Copie `.env.example` para `.env` e preencha:

```env
DATABASE_URL=postgresql://usuario:senha@host/neondb?sslmode=require
SECRET_KEY=uma-chave-secreta
ADMIN_PASSWORD=adminvgsproati
```

3. Instale e inicie:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:5000`. Sem `DATABASE_URL`, o sistema usa SQLite local (`proati.db`) para testes.

## Deploy (Vercel)

Na Vercel o SQLite não funciona: o banco precisa ser o Neon.

### 1. Criar o banco no Neon

1. Acesse [neon.tech](https://neon.tech) e crie um projeto.
2. Em **Dashboard → Connection string**, escolha **Pooled connection**.
3. Copie a URL. Ela deve ter `-pooler` no host e terminar com `?sslmode=require`.

### 2. Subir o código no GitHub

Na pasta do projeto:

```bash
git init
git add .
git commit -m "Primeira versão do Proati Inventário"
```

No GitHub, crie um repositório vazio e envie:

```bash
git remote add origin https://github.com/SEU-USUARIO/proati-inventario.git
git branch -M main
git push -u origin main
```

### 3. Importar na Vercel

1. Acesse [vercel.com](https://vercel.com) → **Add New…** → **Project**.
2. Importe o repositório do GitHub.
3. **Antes de clicar em Deploy**, abra **Environment Variables** e cadastre:

| Nome | Valor |
|---|---|
| `DATABASE_URL` | connection string pooled do Neon |
| `SECRET_KEY` | qualquer texto longo e aleatório |
| `ADMIN_USERNAME` | `admin` |
| `ADMIN_EMAIL` | `admin@proati.local` |
| `ADMIN_PASSWORD` | `adminvgsproati` |

Marque Production, Preview e Development.

4. Clique em **Deploy**.
5. Se as variáveis forem adicionadas depois do primeiro deploy, vá em **Deployments** e faça **Redeploy**.

Login inicial: usuário `admin`, senha `adminvgsproati`.
