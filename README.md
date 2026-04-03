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
```

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

## Usuário Inicial

Após executar `python init_db.py`, será criado um usuário professor padrão:
- **Usuário**: `admin`
- **Senha**: `admin123`

⚠️ Altere a senha após o primeiro login!
