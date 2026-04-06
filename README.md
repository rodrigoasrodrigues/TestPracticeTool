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

# Inicialize o banco de dados
python init_db.py

# Execute a aplicação
python run.py
```

### Variáveis de Ambiente

```env
SECRET_KEY=sua-chave-secreta-aqui
DATABASE_URL=mysql+pymysql://usuario:senha@localhost/testpracticetool
FLASK_RUN_HOST=0.0.0.0
FLASK_RUN_PORT=5000
IMAGE_S3_PATH=s3://seu-bucket/testpracticetool/uploads
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

> Se o banco estiver fora do container, use no `DATABASE_URL` o hostname/IP acessível a partir do Lightsail.

## Usuário Inicial

Após executar `python init_db.py`, será criado um usuário professor padrão:
- **Usuário**: `admin`
- **Senha**: `admin123`

⚠️ Altere a senha após o primeiro login!
