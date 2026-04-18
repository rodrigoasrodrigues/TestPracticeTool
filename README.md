# TestPracticeTool

Uma ferramenta para criar testes e simulados para prática a partir de uma base de questões.

## Tecnologias

- **Backend**: Python 3.10+ / Flask 3.x
- **Banco de Dados**: MySQL (suporta SQLite para desenvolvimento)
- **Frontend**: Bootstrap 5.3 + Bootstrap Icons
- **ORM**: SQLAlchemy + Flask-Migrate
- **Autenticação**: Flask-Login
- **Formulários**: Flask-WTF

## Funcionalidades

### Professor / Admin
- Cadastro e gerenciamento de **matérias**
- Cadastro de **questões** com 5 opções de resposta, imagem opcional e explicação para gabarito
- Criação de **provas** com seleção aleatória de questões por matéria (ordem das respostas aleatorizada e salva)
- Atribuição de provas a alunos com:
  - Tempo limite
  - Data de início e término
  - Número máximo de tentativas (melhor nota é mantida)
- Visualização do **gabarito** com explicações
- Acompanhamento de tentativas e notas dos alunos

### Aluno
- Painel com provas atribuídas
- Realização de provas com temporizador (quando configurado)
- Visualização do **resultado** com nota e explicações das respostas
- Questões incorretas destacadas em vermelho

## Instalação

### Pré-requisitos
- Python 3.10+
- MySQL 8.x (ou SQLite para desenvolvimento)

### Configuração

```bash
# Clone o repositório
git clone <url>
cd TestPracticeTool

# Instale as dependências
pip install -r requirements.txt

# Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas configurações de banco de dados

# Inicialize o banco de dados (primeira instalação)
flask db upgrade

# Execute a aplicação
python run.py
```

> **Atualizações futuras**: sempre que houver novas funcionalidades, basta executar `flask db upgrade` para aplicar as migrações sem perder dados existentes.

### Variáveis de Ambiente

```env
SECRET_KEY=sua-chave-secreta-aqui

# Opção 1: URL completa de conexão
DATABASE_URL=

# Opção 2: variáveis separadas (recomendado se a senha tiver caracteres especiais)
DB_DRIVER=mysql+pymysql
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testpracticetool
DB_USER=root
DB_PASSWORD=sua-senha

FLASK_RUN_HOST=0.0.0.0
FLASK_RUN_PORT=5000
IMAGE_S3_PATH=s3://seu-bucket/testpracticetool/uploads
APP_AWS_REGION=us-east-1
APP_AWS_ACCESS_KEY_ID=
APP_AWS_SECRET_ACCESS_KEY=
APP_AWS_SESSION_TOKEN=
AWS_S3_ENDPOINT_URL=
AWS_REGION=us-east-1
```

> Para acessar pela rede local durante o debug, inicie a aplicação normalmente no VS Code e abra `http://IP_DA_SUA_MAQUINA:5000` a partir de outro dispositivo da mesma rede.

> Se `IMAGE_S3_PATH` estiver definida, as imagens das questões serão gravadas no S3 nesse prefixo; sem essa variável, o comportamento continua local em `app/static/uploads`.

## Estrutura do Projeto

```
TestPracticeTool/
├── app/
│   ├── __init__.py          # Factory da aplicação
│   ├── models.py            # Modelos do banco de dados
│   ├── auth/                # Blueprint de autenticação
│   ├── teacher/             # Blueprint do professor
│   ├── student/             # Blueprint do aluno
│   ├── main/                # Blueprint principal
│   ├── static/              # CSS, JS, uploads
│   └── templates/           # Templates HTML (Jinja2 + Bootstrap)
├── config.py                # Configuração
├── run.py                   # Ponto de entrada
├── init_db.py               # Inicialização do banco de dados
├── requirements.txt
├── .env.example
└── README.md
```

## Docker / AWS Lightsail

### Gerar a imagem localmente

```bash
docker build -t testpracticetool .
```

### Executar o container

```bash
docker run -p 5000:5000 --env-file .env testpracticetool
```

> Na inicialização do container, o `init_db.py` é executado antes de subir a aplicação. Como esse script já verifica se o usuário admin existe e cria apenas o que falta, ele é seguro para reinicializações.

### Deploy no AWS Lightsail

Ao criar o serviço de container no Lightsail, configure:

- **Porta pública do container**: `5000`
- **Variáveis de ambiente**: `SECRET_KEY`, `DATABASE_URL` e demais necessárias
- **Comando de inicialização**: já está definido no `Dockerfile`

> Se o banco estiver fora do container, você pode usar `DATABASE_URL` **ou** as variáveis separadas `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` e `DB_PASSWORD`. Para senhas com `#`, `@`, `:` e similares, prefira as variáveis separadas.

### Deploy automatizado com GitHub Actions

O workflow `/.github/workflows/deploy-lightsail.yml` faz o build da imagem, envia para o Lightsail e cria uma nova deployment automaticamente em `push` para `main`/`master` ou via execução manual.

**Repository Variables**
- `AWS_REGION`
- `LIGHTSAIL_SERVICE_NAME`
- `LIGHTSAIL_CONTAINER_NAME` *(opcional, padrão: `app`)*
- `LIGHTSAIL_IMAGE_LABEL` *(opcional, padrão: `app`)*
- `APP_PORT` *(opcional, padrão: `5000`)*

**Repository Secrets**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `SECRET_KEY`
- `DATABASE_URL` *(opcional, se não usar as variáveis separadas)*
- `DB_DRIVER` *(opcional, padrão: `mysql+pymysql`)*
- `DB_HOST` *(opcional se `DATABASE_URL` estiver definida; caso contrário, obrigatório)*
- `DB_PORT` *(opcional, padrão: `3306`)*
- `DB_NAME` *(opcional se `DATABASE_URL` estiver definida; caso contrário, obrigatório)*
- `DB_USER` *(opcional se `DATABASE_URL` estiver definida; caso contrário, obrigatório)*
- `DB_PASSWORD` *(opcional se `DATABASE_URL` estiver definida; caso contrário, obrigatório)*
- `IMAGE_S3_PATH` *(opcional)*
- `APP_AWS_REGION` *(opcional)*
- `APP_AWS_ACCESS_KEY_ID` *(opcional, credencial exclusiva do app para acessar S3)*
- `APP_AWS_SECRET_ACCESS_KEY` *(opcional)*
- `APP_AWS_SESSION_TOKEN` *(opcional)*
- `AWS_S3_ENDPOINT_URL` *(opcional)*

> As credenciais do workflow (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) continuam sendo usadas apenas para o deploy. O container da aplicação usa `APP_AWS_*` para acessar o S3.

> O serviço de container no Lightsail precisa existir previamente; o workflow cuida do envio da imagem e da atualização da deployment.

## Usuário Inicial

Após executar `python init_db.py`, será criado um usuário professor padrão:
- **Usuário**: `admin`
- **Senha**: `admin123`

⚠️ Altere a senha após o primeiro login!
