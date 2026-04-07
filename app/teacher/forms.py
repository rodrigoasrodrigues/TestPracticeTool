from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, TextAreaField, SelectField, IntegerField,
                     BooleanField, FieldList, FormField, SubmitField, DateTimeLocalField)
from wtforms.validators import DataRequired, Length, Optional, NumberRange, ValidationError


_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp']


def _optional_image_field(label):
    return FileField(
        label,
        validators=[
            Optional(),
            FileAllowed(_IMAGE_EXTENSIONS, 'Apenas imagens são permitidas.'),
        ],
    )


class SubjectForm(FlaskForm):
    name = StringField('Nome da Matéria', validators=[DataRequired(), Length(max=128)])
    description = TextAreaField('Descrição', validators=[Optional()])
    submit = SubmitField('Salvar')


class AnswerOptionForm(FlaskForm):
    class Meta:
        csrf = False

    text = TextAreaField('Texto da Opção', validators=[DataRequired()])
    is_correct = BooleanField('Correta')


class QuestionForm(FlaskForm):
    subject_id = SelectField('Matéria', coerce=int, validators=[DataRequired()])
    text = TextAreaField('Enunciado da Questão', validators=[DataRequired()])
    image = _optional_image_field('Imagem da Questão (opcional)')
    explanation = TextAreaField('Explicação da Resposta (para gabarito)', validators=[Optional()])
    explanation_image = _optional_image_field('Imagem da Explicação (opcional)')
    option_1 = TextAreaField('Opção A', validators=[DataRequired()])
    option_1_image = _optional_image_field('Imagem da Opção A (opcional)')
    option_2 = TextAreaField('Opção B', validators=[DataRequired()])
    option_2_image = _optional_image_field('Imagem da Opção B (opcional)')
    option_3 = TextAreaField('Opção C', validators=[DataRequired()])
    option_3_image = _optional_image_field('Imagem da Opção C (opcional)')
    option_4 = TextAreaField('Opção D', validators=[DataRequired()])
    option_4_image = _optional_image_field('Imagem da Opção D (opcional)')
    option_5 = TextAreaField('Opção E', validators=[DataRequired()])
    option_5_image = _optional_image_field('Imagem da Opção E (opcional)')
    correct_option = SelectField('Opção Correta',
                                 choices=[('1', 'A'), ('2', 'B'), ('3', 'C'),
                                          ('4', 'D'), ('5', 'E')],
                                 validators=[DataRequired()])
    submit = SubmitField('Salvar Questão')
    save_and_new = SubmitField('Salvar e Inserir Nova')


class ExamSubjectForm(FlaskForm):
    class Meta:
        csrf = False

    subject_id = SelectField('Matéria', coerce=int)
    num_questions = IntegerField('Nº de Questões', validators=[NumberRange(min=1)], default=1)


class ExamForm(FlaskForm):
    title = StringField('Título da Prova', validators=[DataRequired(), Length(max=200)])
    description = TextAreaField('Descrição', validators=[Optional()])
    submit = SubmitField('Criar Prova')


class AssignExamForm(FlaskForm):
    student_id = SelectField('Aluno', coerce=int, validators=[DataRequired()])
    max_attempts = IntegerField('Número Máximo de Tentativas',
                                validators=[DataRequired(), NumberRange(min=1)], default=1)
    time_limit_minutes = IntegerField('Tempo Limite (minutos, 0 = sem limite)',
                                      validators=[Optional(), NumberRange(min=0)], default=0)
    available_from = DateTimeLocalField('Disponível a partir de',
                                        format='%Y-%m-%dT%H:%M',
                                        validators=[Optional()])
    available_until = DateTimeLocalField('Disponível até',
                                         format='%Y-%m-%dT%H:%M',
                                         validators=[Optional()])
    submit = SubmitField('Atribuir Prova')


class ImportQuestionsForm(FlaskForm):
    subject_id = SelectField('Matéria de destino', coerce=int, validators=[DataRequired()])
    package_file = FileField('Pacote ZIP',
                             validators=[DataRequired(),
                                         FileAllowed(['zip'],
                                                     'Apenas arquivos ZIP (.zip) são permitidos.')])
    submit = SubmitField('Importar Questões')
