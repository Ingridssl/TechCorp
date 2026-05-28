# 🧑‍💼 NewRH — Sistema de Recrutamento e Admissão

Sistema web completo de RH desenvolvido com **Flask + PostgreSQL + Vanilla JS**, cobrindo o ciclo completo do colaborador: da abertura de vaga à admissão.

> ⚠️ Este repositório é uma versão de demonstração com dados fictícios, para fins de portfólio.

---

## ✨ Funcionalidades

- 📋 **Gestão de Vagas** — abertura, publicação e encerramento automático por data
- 🔍 **Funil de Candidaturas** — pipeline completo: Triagem → Entrevista → Aprovação Final
- 🧾 **Portal do Candidato** — login com e-mail/senha, acompanhamento da candidatura e upload de documentos
- 🏢 **Fluxo de Admissão** — etapas multi-departamentais (RH, DP, SESMT) com aprovações e documentos
- 🔒 **Autenticação dupla** — usuários internos via Microsoft Azure AD (SSO) + candidatos via e-mail/senha
- 📁 **Integração SharePoint** — criação automática de pastas e upload de documentos via Microsoft Graph API
- 📧 **Notificações por e-mail** — alertas automáticos via Microsoft Graph (sem SMTP)
- 📊 **Audit Log** — registro imutável de todas as ações no sistema
- ⏰ **Scheduler de Alertas** — notificação automática de candidaturas paradas há X dias
- 👶 **Módulo Menor Aprendiz** — formulário e gestão separados

---

## 🛠️ Stack

| Camada | Tecnologias |
|---|---|
| Backend | Python 3.11, Flask 3.1, SQLAlchemy 2.0 |
| Banco de Dados | PostgreSQL (pg8000) |
| Frontend | Vanilla JS (SPA), HTML5, CSS3 |
| Autenticação | JWT, Azure AD / MSAL, bcrypt |
| Integrações | Microsoft Graph API, SharePoint |
| Deploy | Render (gunicorn + gevent) |

---

## 🗂️ Estrutura do Projeto

```
newrh/
├── backend/
│   ├── main.py                  # App Flask, blueprints, configuração
│   ├── models.py                # Models SQLAlchemy (User, Job, Candidatura, Admission...)
│   ├── database.py              # Engine PostgreSQL com pg8000
│   ├── schemas.py               # Validação de dados
│   ├── security.py              # JWT + bcrypt
│   ├── email_service.py         # Envio via Microsoft Graph (sem SMTP)
│   ├── sharepoint_service.py    # Criação de pastas e upload no SharePoint
│   ├── auth_microsoft.py        # SSO Azure AD / MSAL
│   ├── candidato_auth.py        # Autenticação do portal do candidato
│   ├── alertas.py               # Scheduler APScheduler
│   ├── audit.py                 # Registro de audit log
│   ├── routers/
│   │   ├── auth.py              # Login/logout de usuários internos
│   │   ├── jobs.py              # CRUD de vagas
│   │   ├── candidaturas.py      # Gestão de candidaturas
│   │   ├── processos.py         # Fluxo de admissão
│   │   ├── solicitacoes.py      # Solicitações de abertura de vaga
│   │   └── menor_aprendiz.py    # Módulo menor aprendiz
│   └── requirements.txt
└── frontend/
    ├── index.html               # Painel principal (SPA)
    ├── app.js                   # Lógica SPA completa
    ├── styles.css               # Estilos globais
    ├── admissao.html            # Fluxo de admissão
    ├── admissoes.html           # Lista de admissões
    └── acompanhar.html          # Portal do candidato
```

---

## ⚙️ Como Rodar Localmente

### 1. Pré-requisitos
- Python 3.11+
- PostgreSQL rodando localmente
- Variáveis de ambiente configuradas (ver `.env.example`)

### 2. Instalar dependências
```bash
cd backend
pip install -r requirements.txt
```

### 3. Configurar variáveis
```bash
cp .env.example .env
# Edite o .env com seus valores
```

### 4. Rodar
```bash
python main.py
# Acesse: http://localhost:8080
# Login padrão: admin / 1234
```

---

## 🔑 Variáveis de Ambiente

| Variável | Descrição |
|---|---|
| `DATABASE_URL` | URL do PostgreSQL |
| `SECRET_KEY` | Chave JWT |
| `MS_TENANT_ID` | Azure AD Tenant ID |
| `MS_CLIENT_ID` | Azure AD Client ID |
| `MS_CLIENT_SECRET` | Azure AD Client Secret |
| `SHAREPOINT_SITE` | URL do site SharePoint |
| `EMAIL_ENABLED` | `true` para habilitar envio de e-mails |

---

## 🔄 Funil de Candidaturas

```
PENDING → TRIAGEM → TRIAGEM_OK → ENTREVISTA → ENTREVISTA_OK → APROVACAO_FINAL → APPROVED
                                                                               ↘ REJECTED
```

---

## 📋 Fluxo de Admissão Multi-departamental

| Etapa | Departamento | Tipo |
|---|---|---|
| Agendar ASO | RH | Checklist |
| Realizar admissão | DP Externo | Checklist |
| Encaminhar documentação | DP Externo | Upload |
| Cadastrar no sistema | DP Pessoal | Checklist |
| Coletar assinaturas | DP Pessoal | Upload |
| Aprovação do colaborador | RH | Aprovação |
| Formação NRs | SESMT | Upload |
| Liberado para Campo | RH | Checklist |

---

## 👤 Perfis de Acesso

| Role | Permissões |
|---|---|
| `ROLE_ADMIN` | Acesso total |
| `ROLE_RH` | Vagas, candidaturas, admissões |
| `ROLE_GESTOR` | Visualização e aprovações do setor |
| Candidato | Portal próprio (acompanhar + upload documentos) |

---

## 📄 Licença

MIT
