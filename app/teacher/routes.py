import os
import io
import random
import uuid
import yaml
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort, current_app, Response
from flask_login import login_required, current_user
from app import db
from app.teacher import bp
from app.teacher.forms import SubjectForm, QuestionForm, ExamForm, AssignExamForm, ImportQuestionsForm
from app.models import (Subject, Question, AnswerOption, Exam, ExamQuestion,
                        ExamQuestionOption, StudentExam, ExamAttempt, AttemptAnswer, User)


def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_teacher():
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def save_image(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, filename))
    return filename


# ─── Dashboard ────────────────────────────────────────────────────────────────

@bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    subjects_count = Subject.query.filter_by(created_by=current_user.id).count()
    questions_count = Question.query.filter_by(created_by=current_user.id).count()
    exams_count = Exam.query.filter_by(created_by=current_user.id).count()
    recent_exams = Exam.query.filter_by(created_by=current_user.id)\
        .order_by(Exam.created_at.desc()).limit(5).all()
    return render_template('teacher/dashboard.html',
                           title='Painel do Professor',
                           subjects_count=subjects_count,
                           questions_count=questions_count,
                           exams_count=exams_count,
                           recent_exams=recent_exams)


# ─── Subjects ─────────────────────────────────────────────────────────────────

@bp.route('/materias')
@login_required
@teacher_required
def subjects():
    subjects_list = Subject.query.filter_by(created_by=current_user.id)\
        .order_by(Subject.name).all()
    return render_template('teacher/subjects.html', title='Matérias', subjects=subjects_list)


@bp.route('/materias/nova', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_subject():
    form = SubjectForm()
    if form.validate_on_submit():
        subject = Subject(
            name=form.name.data,
            description=form.description.data,
            created_by=current_user.id
        )
        db.session.add(subject)
        db.session.commit()
        flash(f'Matéria "{subject.name}" criada com sucesso!', 'success')
        return redirect(url_for('teacher.subjects'))
    return render_template('teacher/subject_form.html', title='Nova Matéria', form=form)


@bp.route('/materias/<int:subject_id>/editar', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.created_by != current_user.id:
        abort(403)
    form = SubjectForm(obj=subject)
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data
        db.session.commit()
        flash(f'Matéria "{subject.name}" atualizada!', 'success')
        return redirect(url_for('teacher.subjects'))
    return render_template('teacher/subject_form.html', title='Editar Matéria', form=form,
                           subject=subject)


@bp.route('/materias/<int:subject_id>/excluir', methods=['POST'])
@login_required
@teacher_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.created_by != current_user.id:
        abort(403)
    db.session.delete(subject)
    db.session.commit()
    flash(f'Matéria "{subject.name}" excluída.', 'success')
    return redirect(url_for('teacher.subjects'))


# ─── Questions ────────────────────────────────────────────────────────────────

@bp.route('/questoes')
@login_required
@teacher_required
def questions():
    subject_id = request.args.get('subject_id', type=int)
    query = Question.query.filter_by(created_by=current_user.id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    questions_list = query.order_by(Question.created_at.desc()).all()
    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    return render_template('teacher/questions.html', title='Questões',
                           questions=questions_list, subjects=subjects_list,
                           selected_subject=subject_id)


@bp.route('/questoes/nova', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_question():
    form = QuestionForm()
    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    form.subject_id.choices = [(s.id, s.name) for s in subjects_list]

    if form.validate_on_submit():
        image_path = None
        if form.image.data and form.image.data.filename:
            if allowed_file(form.image.data.filename):
                image_path = save_image(form.image.data)
            else:
                flash('Tipo de arquivo não permitido.', 'danger')
                return render_template('teacher/question_form.html', title='Nova Questão',
                                       form=form)

        question = Question(
            subject_id=form.subject_id.data,
            text=form.text.data,
            image_path=image_path,
            explanation=form.explanation.data,
            created_by=current_user.id
        )
        db.session.add(question)
        db.session.flush()

        options_texts = [
            form.option_1.data, form.option_2.data, form.option_3.data,
            form.option_4.data, form.option_5.data
        ]
        correct_idx = int(form.correct_option.data) - 1
        for i, text in enumerate(options_texts):
            opt = AnswerOption(
                question_id=question.id,
                text=text,
                is_correct=(i == correct_idx)
            )
            db.session.add(opt)

        db.session.commit()
        flash('Questão criada com sucesso!', 'success')
        return redirect(url_for('teacher.questions'))

    return render_template('teacher/question_form.html', title='Nova Questão', form=form)


@bp.route('/questoes/<int:question_id>/editar', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.created_by != current_user.id:
        abort(403)

    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    options = question.answer_options.all()

    form = QuestionForm()
    form.subject_id.choices = [(s.id, s.name) for s in subjects_list]

    if request.method == 'GET':
        form.subject_id.data = question.subject_id
        form.text.data = question.text
        form.explanation.data = question.explanation
        if len(options) >= 5:
            form.option_1.data = options[0].text
            form.option_2.data = options[1].text
            form.option_3.data = options[2].text
            form.option_4.data = options[3].text
            form.option_5.data = options[4].text
            for i, opt in enumerate(options[:5]):
                if opt.is_correct:
                    form.correct_option.data = str(i + 1)
                    break

    if form.validate_on_submit():
        image_path = question.image_path
        if form.image.data and form.image.data.filename:
            if allowed_file(form.image.data.filename):
                # Delete old image
                if question.image_path:
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'],
                                            question.image_path)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                image_path = save_image(form.image.data)
            else:
                flash('Tipo de arquivo não permitido.', 'danger')

        question.subject_id = form.subject_id.data
        question.text = form.text.data
        question.image_path = image_path
        question.explanation = form.explanation.data

        options_texts = [
            form.option_1.data, form.option_2.data, form.option_3.data,
            form.option_4.data, form.option_5.data
        ]
        correct_idx = int(form.correct_option.data) - 1

        # Update existing options or create new ones
        for i, opt in enumerate(options[:5]):
            opt.text = options_texts[i]
            opt.is_correct = (i == correct_idx)

        db.session.commit()
        flash('Questão atualizada com sucesso!', 'success')
        return redirect(url_for('teacher.questions'))

    return render_template('teacher/question_form.html', title='Editar Questão',
                           form=form, question=question)


@bp.route('/questoes/<int:question_id>/excluir', methods=['POST'])
@login_required
@teacher_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.created_by != current_user.id:
        abort(403)
    if question.image_path:
        old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_path)
        if os.path.exists(old_path):
            os.remove(old_path)
    db.session.delete(question)
    db.session.commit()
    flash('Questão excluída.', 'success')
    return redirect(url_for('teacher.questions'))


# ─── Exams ────────────────────────────────────────────────────────────────────

@bp.route('/provas')
@login_required
@teacher_required
def exams():
    exams_list = Exam.query.filter_by(created_by=current_user.id)\
        .order_by(Exam.created_at.desc()).all()
    return render_template('teacher/exams.html', title='Provas', exams=exams_list)


@bp.route('/provas/nova', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_exam():
    form = ExamForm()
    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()

    if request.method == 'POST' and form.validate_on_submit():
        # Get subject/count pairs from the form
        subject_ids = request.form.getlist('subject_ids[]')
        num_questions_list = request.form.getlist('num_questions[]')

        selections = []
        for sid, nq in zip(subject_ids, num_questions_list):
            try:
                sid = int(sid)
                nq = int(nq)
                if sid > 0 and nq > 0:
                    selections.append((sid, nq))
            except (ValueError, TypeError):
                pass

        if not selections:
            flash('Adicione pelo menos uma matéria com questões para a prova.', 'danger')
            return render_template('teacher/exam_form.html', title='Nova Prova',
                                   form=form, subjects=subjects_list)

        # Validate enough questions exist
        for sid, nq in selections:
            subject = db.session.get(Subject, sid)
            if not subject or subject.created_by != current_user.id:
                flash('Matéria inválida selecionada.', 'danger')
                return render_template('teacher/exam_form.html', title='Nova Prova',
                                       form=form, subjects=subjects_list)
            available = Question.query.filter_by(subject_id=sid,
                                                 created_by=current_user.id).count()
            if available < nq:
                flash(f'A matéria "{subject.name}" tem apenas {available} questões disponíveis, '
                      f'mas você solicitou {nq}.', 'danger')
                return render_template('teacher/exam_form.html', title='Nova Prova',
                                       form=form, subjects=subjects_list)

        exam = Exam(
            title=form.title.data,
            description=form.description.data,
            created_by=current_user.id
        )
        db.session.add(exam)
        db.session.flush()

        order_num = 1
        for sid, nq in selections:
            all_questions = Question.query.filter_by(subject_id=sid,
                                                     created_by=current_user.id).all()
            selected_questions = random.sample(all_questions, nq)

            for q in selected_questions:
                eq = ExamQuestion(
                    exam_id=exam.id,
                    question_id=q.id,
                    order_number=order_num
                )
                db.session.add(eq)
                db.session.flush()

                # Randomize answer options order
                options = q.answer_options.all()
                random.shuffle(options)
                for display_order, opt in enumerate(options, start=1):
                    eqo = ExamQuestionOption(
                        exam_question_id=eq.id,
                        answer_option_id=opt.id,
                        display_order=display_order
                    )
                    db.session.add(eqo)

                order_num += 1

        db.session.commit()
        flash(f'Prova "{exam.title}" criada com sucesso!', 'success')
        return redirect(url_for('teacher.exams'))

    return render_template('teacher/exam_form.html', title='Nova Prova',
                           form=form, subjects=subjects_list)


@bp.route('/provas/<int:exam_id>')
@login_required
@teacher_required
def view_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()
    return render_template('teacher/view_exam.html', title=exam.title,
                           exam=exam, questions=questions_list)


@bp.route('/provas/<int:exam_id>/gabarito')
@login_required
@teacher_required
def exam_answer_key(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()
    return render_template('teacher/answer_key.html', title=f'Gabarito - {exam.title}',
                           exam=exam, questions=questions_list)


@bp.route('/provas/<int:exam_id>/excluir', methods=['POST'])
@login_required
@teacher_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)
    db.session.delete(exam)
    db.session.commit()
    flash(f'Prova "{exam.title}" excluída.', 'success')
    return redirect(url_for('teacher.exams'))


# ─── Assign Exam ──────────────────────────────────────────────────────────────

@bp.route('/provas/<int:exam_id>/atribuir', methods=['GET', 'POST'])
@login_required
@teacher_required
def assign_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)

    form = AssignExamForm()
    students = User.query.filter_by(role='student', is_active=True).order_by(User.username).all()
    form.student_id.choices = [(s.id, f'{s.username} ({s.email})') for s in students]

    if form.validate_on_submit():
        time_limit = form.time_limit_minutes.data
        if time_limit == 0:
            time_limit = None

        assignment = StudentExam(
            exam_id=exam.id,
            student_id=form.student_id.data,
            assigned_by=current_user.id,
            max_attempts=form.max_attempts.data,
            time_limit_minutes=time_limit,
            available_from=form.available_from.data,
            available_until=form.available_until.data
        )
        db.session.add(assignment)
        db.session.commit()
        student = db.session.get(User, form.student_id.data)
        flash(f'Prova atribuída a {student.username} com sucesso!', 'success')
        return redirect(url_for('teacher.exam_students', exam_id=exam.id))

    return render_template('teacher/assign_exam.html', title='Atribuir Prova',
                           exam=exam, form=form)


@bp.route('/provas/<int:exam_id>/alunos')
@login_required
@teacher_required
def exam_students(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)
    assignments = StudentExam.query.filter_by(exam_id=exam.id).all()
    return render_template('teacher/exam_students.html', title=f'Alunos - {exam.title}',
                           exam=exam, assignments=assignments)


@bp.route('/provas/<int:exam_id>/alunos/<int:student_id>/tentativas')
@login_required
@teacher_required
def student_attempts(exam_id, student_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.created_by != current_user.id:
        abort(403)
    student = User.query.get_or_404(student_id)
    assignment = StudentExam.query.filter_by(exam_id=exam_id, student_id=student_id).first_or_404()
    attempts = assignment.attempts.filter(ExamAttempt.completed_at.isnot(None))\
        .order_by(ExamAttempt.started_at.desc()).all()
    return render_template('teacher/student_attempts.html',
                           title=f'Tentativas de {student.username}',
                           exam=exam, student=student, attempts=attempts,
                           assignment=assignment)


@bp.route('/tentativas/<int:attempt_id>/detalhes')
@login_required
@teacher_required
def attempt_details(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    assignment = attempt.student_exam
    exam = assignment.exam
    if exam.created_by != current_user.id:
        abort(403)
    answers = attempt.answers.all()
    eq_map = {a.exam_question_id: a for a in answers}
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()
    return render_template('teacher/attempt_details.html',
                           title='Detalhes da Tentativa',
                           attempt=attempt, exam=exam,
                           questions=questions_list, eq_map=eq_map)


# ─── YAML Import ──────────────────────────────────────────────────────────────

_YAML_REQUIRED_OPTIONS = 5


def _parse_yaml_questions(raw_bytes):
    """Parse and validate YAML bytes; return list of validated question dicts.

    Expected format::

        questions:
          - text: "Enunciado da questão"
            explanation: "Explicação opcional"   # optional
            correct: 1                           # 1-indexed (1–5)
            options:
              - "Opção A"
              - "Opção B"
              - "Opção C"
              - "Opção D"
              - "Opção E"

    Raises ValueError with a human-readable message on any structural problem.
    """
    try:
        data = yaml.safe_load(raw_bytes)
    except yaml.YAMLError as exc:
        raise ValueError(f'Arquivo YAML inválido: {exc}') from exc

    if not isinstance(data, dict) or 'questions' not in data:
        raise ValueError("O arquivo deve conter uma chave raiz 'questions'.")

    raw_questions = data['questions']
    if not isinstance(raw_questions, list) or len(raw_questions) == 0:
        raise ValueError("'questions' deve ser uma lista não vazia.")

    parsed = []
    for idx, item in enumerate(raw_questions, start=1):
        prefix = f'Questão {idx}'
        if not isinstance(item, dict):
            raise ValueError(f'{prefix}: cada entrada deve ser um mapeamento YAML.')

        # text
        text = item.get('text', '').strip()
        if not text:
            raise ValueError(f'{prefix}: campo "text" é obrigatório e não pode ser vazio.')

        # options
        options = item.get('options')
        if not isinstance(options, list) or len(options) != _YAML_REQUIRED_OPTIONS:
            raise ValueError(
                f'{prefix}: "options" deve ser uma lista com exatamente '
                f'{_YAML_REQUIRED_OPTIONS} itens.'
            )
        options = [str(opt).strip() for opt in options]
        if any(opt == '' for opt in options):
            raise ValueError(f'{prefix}: nenhuma opção pode ser vazia.')

        # correct
        correct_raw = item.get('correct')
        try:
            correct_idx = int(correct_raw)
        except (TypeError, ValueError):
            raise ValueError(
                f'{prefix}: "correct" deve ser um número inteiro de 1 a {_YAML_REQUIRED_OPTIONS}.'
            )
        if correct_idx < 1 or correct_idx > _YAML_REQUIRED_OPTIONS:
            raise ValueError(
                f'{prefix}: "correct" deve estar entre 1 e {_YAML_REQUIRED_OPTIONS} '
                f'(recebido: {correct_idx}).'
            )

        explanation = str(item.get('explanation', '') or '').strip()

        parsed.append({
            'text': text,
            'explanation': explanation,
            'options': options,
            'correct_idx': correct_idx - 1,  # convert to 0-based
        })

    return parsed


@bp.route('/questoes/importar', methods=['GET', 'POST'])
@login_required
@teacher_required
def import_questions():
    form = ImportQuestionsForm()
    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    form.subject_id.choices = [(s.id, s.name) for s in subjects_list]

    if not subjects_list:
        flash('Crie ao menos uma matéria antes de importar questões.', 'warning')
        return redirect(url_for('teacher.create_subject'))

    if form.validate_on_submit():
        subject = db.session.get(Subject, form.subject_id.data)
        if not subject or subject.created_by != current_user.id:
            abort(403)

        raw_bytes = form.yaml_file.data.read()
        try:
            parsed = _parse_yaml_questions(raw_bytes)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('teacher/import_questions.html',
                                   title='Importar Questões', form=form)

        imported = 0
        for q_data in parsed:
            question = Question(
                subject_id=subject.id,
                text=q_data['text'],
                explanation=q_data['explanation'] or None,
                created_by=current_user.id,
            )
            db.session.add(question)
            db.session.flush()

            for i, opt_text in enumerate(q_data['options']):
                opt = AnswerOption(
                    question_id=question.id,
                    text=opt_text,
                    is_correct=(i == q_data['correct_idx']),
                )
                db.session.add(opt)

            imported += 1

        db.session.commit()
        flash(
            f'{imported} questão(ões) importada(s) com sucesso para "{subject.name}"!',
            'success',
        )
        return redirect(url_for('teacher.questions', subject_id=subject.id))

    # Pre-select subject from query string (e.g. when coming from a subject card)
    subject_id_qs = request.args.get('subject_id', type=int)
    if subject_id_qs:
        form.subject_id.data = subject_id_qs

    return render_template('teacher/import_questions.html',
                           title='Importar Questões', form=form)


@bp.route('/questoes/importar/modelo')
@login_required
@teacher_required
def yaml_template():
    """Return a sample YAML file so teachers know the expected format."""
    sample = (
        "# Modelo de importação de questões - TestPracticeTool\n"
        "#\n"
        "# Regras:\n"
        "#   - Cada questão deve ter exatamente 5 opções.\n"
        "#   - O campo 'correct' indica o número da opção correta (1 a 5).\n"
        "#   - O campo 'explanation' é opcional (aparece apenas no gabarito).\n"
        "\n"
        "questions:\n"
        "  - text: \"Qual é o resultado de 2 + 2?\"\n"
        "    explanation: \"A soma de 2 com 2 é igual a 4.\"\n"
        "    correct: 3\n"
        "    options:\n"
        "      - \"2\"\n"
        "      - \"3\"\n"
        "      - \"4\"\n"
        "      - \"5\"\n"
        "      - \"6\"\n"
        "\n"
        "  - text: \"Qual planeta é conhecido como Planeta Vermelho?\"\n"
        "    correct: 2\n"
        "    options:\n"
        "      - \"Vênus\"\n"
        "      - \"Marte\"\n"
        "      - \"Júpiter\"\n"
        "      - \"Saturno\"\n"
        "      - \"Mercúrio\"\n"
    )
    return Response(
        sample,
        mimetype='text/yaml',
        headers={'Content-Disposition': 'attachment; filename="modelo_questoes.yaml"'},
    )
