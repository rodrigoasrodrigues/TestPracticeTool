import os
from datetime import datetime, timezone
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from markupsafe import Markup, escape
from sqlalchemy import inspect, text
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
csrf = CSRFProtect()


def _ensure_legacy_schema_updates(app):
    """Add new optional question/media columns for older databases without requiring a manual migration."""
    with app.app_context():
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        statements = []

        if 'questions' in table_names:
            question_columns = {column['name'] for column in inspector.get_columns('questions')}
            if 'reference_text' not in question_columns:
                statements.append(
                    text('ALTER TABLE questions ADD COLUMN reference_text TEXT')
                )
            if 'explanation_image_path' not in question_columns:
                statements.append(
                    text('ALTER TABLE questions ADD COLUMN explanation_image_path VARCHAR(256)')
                )

        if 'answer_options' in table_names:
            option_columns = {column['name'] for column in inspector.get_columns('answer_options')}
            if 'image_path' not in option_columns:
                statements.append(
                    text('ALTER TABLE answer_options ADD COLUMN image_path VARCHAR(256)')
                )

        if statements:
            with db.engine.begin() as connection:
                for statement in statements:
                    connection.execute(statement)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'warning'

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')

    from app.teacher import bp as teacher_bp
    app.register_blueprint(teacher_bp, url_prefix='/professor')

    from app.student import bp as student_bp
    app.register_blueprint(student_bp, url_prefix='/aluno')

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    @app.context_processor
    def inject_now():
        from app.storage import get_image_url
        return {
            'now': datetime.now(timezone.utc),
            'image_url': get_image_url,
        }

    @app.template_filter('format_math_text')
    def format_math_text(value):
        if value is None:
            return ''
        escaped = escape(str(value))
        return Markup('<br>\n').join(escaped.splitlines())

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('404.html'), 404

    _ensure_legacy_schema_updates(app)

    return app


from app import models
