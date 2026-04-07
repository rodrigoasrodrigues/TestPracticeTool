from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError
from app.models import User


class LoginForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember_me = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')


class RegistrationForm(FlaskForm):
    username = StringField('Usuário', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('E-mail', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirmar Senha',
                              validators=[DataRequired(), EqualTo('password',
                                          message='As senhas devem ser iguais.')])
    role = SelectField('Perfil', choices=[('student', 'Aluno'), ('teacher', 'Professor')])
    submit = SubmitField('Registrar')

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError('Nome de usuário já em uso.')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data).first():
            raise ValidationError('E-mail já cadastrado.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Senha atual', validators=[DataRequired()])
    new_password = PasswordField('Nova senha', validators=[DataRequired(), Length(min=6)])
    new_password2 = PasswordField('Confirmar nova senha',
                                  validators=[DataRequired(), EqualTo('new_password',
                                              message='As senhas devem ser iguais.')])
    submit = SubmitField('Alterar senha')
