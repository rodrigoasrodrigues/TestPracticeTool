import os
import io
import random
import uuid
import zipfile
import yaml
from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort, current_app, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.storage import delete_image, read_image_bytes, save_image, save_image_bytes
from app.teacher import bp
from app.teacher.forms import SubjectForm, SubjectGroupForm, QuestionForm, ExamForm, AssignExamForm, ImportQuestionsForm
from app.models import (Subject, SubjectGroup, Question, AnswerOption, Exam, ExamQuestion,
                        ExamQuestionOption, StudentExam, ExamAttempt, AttemptAnswer, User)


def teacher_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (not current_user.is_authenticated
                or not current_user.is_teacher()
                or not current_user.is_active):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _question_image_export_name(question, original_filename, kind='enunciado'):
    """Create a deterministic, human-readable image filename for exports."""
    _, ext = os.path.splitext(os.path.basename(original_filename or ''))
    ext = ext.lower() or '.img'
    text_stub = secure_filename((question.text or '')[:40]).strip('._-')
    if not text_stub:
        text_stub = 'questao'
    kind_stub = secure_filename(kind or 'imagem').strip('._-')
    if not kind_stub:
        kind_stub = 'imagem'
    return f'q{question.id:05d}_{kind_stub}_{text_stub}{ext}'


def _subject_yaml_filename(subject):
    base = secure_filename(subject.name or f'materia_{subject.id}')
    if not base:
        base = f'materia_{subject.id}'
    return f'{base}_questoes.yaml'


def _subject_package_zip_filename(subject):
    base = secure_filename(subject.name or f'materia_{subject.id}')
    if not base:
        base = f'materia_{subject.id}'
    return f'{base}_pacote_questoes.zip'


_OPTION_IMAGE_FIELD_NAMES = [
    'option_1_image',
    'option_2_image',
    'option_3_image',
    'option_4_image',
    'option_5_image',
]


def _save_uploaded_image_field(file_storage, current_path=None):
    """Save an uploaded image if one was provided, otherwise keep the current path."""
    if not file_storage or not getattr(file_storage, 'filename', ''):
        return current_path

    if not allowed_file(file_storage.filename):
        raise ValueError('Tipo de arquivo não permitido.')

    return save_image(file_storage)


def _delete_images(image_paths):
    for image_path in {path for path in image_paths if path}:
        try:
            delete_image(image_path)
        except RuntimeError as exc:
            current_app.logger.warning('Falha ao remover imagem %s: %s', image_path, exc)


def _build_subject_questions_payload(subject, questions):
    payload = {
        'subject': {
            'id': subject.id,
            'name': subject.name,
            'description': subject.description or '',
        },
        'questions': [],
    }

    for question in questions:
        options = question.answer_options.order_by(AnswerOption.id.asc()).all()
        correct_idx = 1
        options_payload = []

        for idx, opt in enumerate(options, start=1):
            if opt.is_correct:
                correct_idx = idx

            option_item = {'text': opt.text}
            if opt.image_path:
                option_item['image_file'] = _question_image_export_name(
                    question,
                    opt.image_path,
                    kind=f'opcao_{idx}',
                )
            options_payload.append(option_item)

        item = {
            'id': question.id,
            'text': question.text,
            'reference': question.reference_text or '',
            'explanation': question.explanation or '',
            'correct': correct_idx,
            'options': options_payload,
        }

        if question.image_path:
            item['image_file'] = _question_image_export_name(question, question.image_path)
        if question.explanation_image_path:
            item['explanation_image_file'] = _question_image_export_name(
                question,
                question.explanation_image_path,
                kind='explicacao',
            )

        payload['questions'].append(item)

    return payload


# ─── Dashboard ────────────────────────────────────────────────────────────────

@bp.route('/dashboard')
@login_required
@teacher_required
def dashboard():
    subjects_count = Subject.query.filter_by(created_by=current_user.id).count()
    questions_count = Question.query.filter_by(created_by=current_user.id).count()
    exams_count = Exam.query.filter_by(created_by=current_user.id).count()
    pending_users_count = User.query.filter_by(is_active=False).count()
    recent_exams = Exam.query.filter_by(created_by=current_user.id)\
        .order_by(Exam.created_at.desc()).limit(5).all()
    return render_template('teacher/dashboard.html',
                           title='Painel do Professor',
                           subjects_count=subjects_count,
                           questions_count=questions_count,
                           exams_count=exams_count,
                           pending_users_count=pending_users_count,
                           recent_exams=recent_exams)


@bp.route('/usuarios/pendentes')
@login_required
@teacher_required
def pending_users():
    users = User.query.filter_by(is_active=False).order_by(User.created_at.asc()).all()
    return render_template('teacher/pending_users.html',
                           title='Aprovar Cadastros', users=users)


@bp.route('/usuarios/<int:user_id>/aprovar', methods=['POST'])
@login_required
@teacher_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)

    if user.is_active:
        flash('Este usuário já está aprovado.', 'info')
        return redirect(url_for('teacher.pending_users'))

    user.is_active = True
    db.session.commit()
    flash(f'Usuário "{user.username}" aprovado com sucesso.', 'success')
    return redirect(url_for('teacher.pending_users'))


# ─── Subject Groups ───────────────────────────────────────────────────────────

@bp.route('/grupos')
@login_required
@teacher_required
def subject_groups():
    groups = SubjectGroup.query.filter_by(created_by=current_user.id)\
        .order_by(SubjectGroup.name).all()
    return render_template('teacher/subject_groups.html', title='Grupos de Matérias', groups=groups)


@bp.route('/grupos/novo', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_subject_group():
    form = SubjectGroupForm()
    if form.validate_on_submit():
        group = SubjectGroup(
            name=form.name.data,
            description=form.description.data,
            created_by=current_user.id
        )
        db.session.add(group)
        db.session.commit()
        flash(f'Grupo "{group.name}" criado com sucesso!', 'success')
        return redirect(url_for('teacher.subject_groups'))
    return render_template('teacher/subject_group_form.html', title='Novo Grupo de Matérias',
                           form=form)


@bp.route('/grupos/<int:group_id>/editar', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_subject_group(group_id):
    group = SubjectGroup.query.get_or_404(group_id)
    if group.created_by != current_user.id:
        abort(403)
    form = SubjectGroupForm(obj=group)
    if form.validate_on_submit():
        group.name = form.name.data
        group.description = form.description.data
        db.session.commit()
        flash(f'Grupo "{group.name}" atualizado!', 'success')
        return redirect(url_for('teacher.subject_groups'))
    return render_template('teacher/subject_group_form.html', title='Editar Grupo',
                           form=form, group=group)


@bp.route('/grupos/<int:group_id>/excluir', methods=['POST'])
@login_required
@teacher_required
def delete_subject_group(group_id):
    group = SubjectGroup.query.get_or_404(group_id)
    if group.created_by != current_user.id:
        abort(403)
    # Detach subjects before deleting the group
    for s in group.subjects.all():
        s.group_id = None
    db.session.delete(group)
    db.session.commit()
    flash(f'Grupo "{group.name}" excluído.', 'success')
    return redirect(url_for('teacher.subject_groups'))


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
    groups = SubjectGroup.query.filter_by(created_by=current_user.id).order_by(SubjectGroup.name).all()
    form.group_id.choices = [(0, '— Sem grupo —')] + [(g.id, g.name) for g in groups]
    if form.validate_on_submit():
        group_id = form.group_id.data if form.group_id.data else None
        subject = Subject(
            name=form.name.data,
            description=form.description.data,
            created_by=current_user.id,
            group_id=group_id if group_id else None
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
    groups = SubjectGroup.query.filter_by(created_by=current_user.id).order_by(SubjectGroup.name).all()
    form.group_id.choices = [(0, '— Sem grupo —')] + [(g.id, g.name) for g in groups]
    if form.validate_on_submit():
        subject.name = form.name.data
        subject.description = form.description.data
        subject.group_id = form.group_id.data if form.group_id.data else None
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


@bp.route('/materias/<int:subject_id>/exportar/pacote')
@login_required
@teacher_required
def export_subject_package(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    if subject.created_by != current_user.id:
        abort(403)

    questions = Question.query.filter_by(subject_id=subject.id, created_by=current_user.id)\
        .order_by(Question.id.asc()).all()

    payload = _build_subject_questions_payload(subject, questions)
    yaml_filename = _subject_yaml_filename(subject)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            yaml_filename,
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        )

        for question in questions:
            images_to_export = []
            if question.image_path:
                images_to_export.append(
                    (_question_image_export_name(question, question.image_path), question.image_path)
                )
            if question.explanation_image_path:
                images_to_export.append((
                    _question_image_export_name(
                        question,
                        question.explanation_image_path,
                        kind='explicacao',
                    ),
                    question.explanation_image_path,
                ))

            for idx, option in enumerate(
                question.answer_options.order_by(AnswerOption.id.asc()).all(),
                start=1,
            ):
                if option.image_path:
                    images_to_export.append((
                        _question_image_export_name(
                            question,
                            option.image_path,
                            kind=f'opcao_{idx}',
                        ),
                        option.image_path,
                    ))

            for export_name, image_path in images_to_export:
                image_bytes = read_image_bytes(image_path)
                if image_bytes:
                    zf.writestr(f'images/{export_name}', image_bytes)

    memory_file.seek(0)
    zip_filename = _subject_package_zip_filename(subject)
    return Response(
        memory_file.getvalue(),
        mimetype='application/zip',
        headers={'Content-Disposition': f'attachment; filename="{zip_filename}"'},
    )


@bp.route('/materias/<int:subject_id>/exportar/yaml')
@login_required
@teacher_required
def export_subject_yaml(subject_id):
    return redirect(url_for('teacher.export_subject_package', subject_id=subject_id))


@bp.route('/materias/<int:subject_id>/exportar/imagens')
@login_required
@teacher_required
def export_subject_images(subject_id):
    return redirect(url_for('teacher.export_subject_package', subject_id=subject_id))


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


@bp.route('/questoes/mover', methods=['POST'])
@login_required
@teacher_required
def move_questions():
    selected_ids = [
        int(question_id)
        for question_id in request.form.getlist('question_ids')
        if str(question_id).isdigit()
    ]
    target_subject_id = request.form.get('target_subject_id', type=int)
    return_subject_id = request.form.get('return_subject_id', type=int)

    redirect_kwargs = {'subject_id': return_subject_id} if return_subject_id else {}

    if not selected_ids:
        flash('Selecione ao menos uma questão para mover.', 'warning')
        return redirect(url_for('teacher.questions', **redirect_kwargs))

    target_subject = db.session.get(Subject, target_subject_id)
    if not target_subject or target_subject.created_by != current_user.id:
        flash('Selecione uma matéria de destino válida.', 'warning')
        return redirect(url_for('teacher.questions', **redirect_kwargs))

    questions_to_move = Question.query.filter(
        Question.id.in_(selected_ids),
        Question.created_by == current_user.id,
    ).all()

    if not questions_to_move:
        flash('Nenhuma questão válida foi encontrada para mover.', 'warning')
        return redirect(url_for('teacher.questions', **redirect_kwargs))

    moved_count = 0
    for question in questions_to_move:
        if question.subject_id != target_subject.id:
            question.subject_id = target_subject.id
            moved_count += 1

    if moved_count == 0:
        flash('As questões selecionadas já estão na matéria de destino.', 'info')
        return redirect(url_for('teacher.questions', **redirect_kwargs))

    db.session.commit()
    flash(f'{moved_count} questão(ões) movida(s) para "{target_subject.name}".', 'success')
    return redirect(url_for('teacher.questions', **redirect_kwargs))


@bp.route('/questoes/nova', methods=['GET', 'POST'])
@login_required
@teacher_required
def create_question():
    form = QuestionForm()
    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    form.subject_id.choices = [(s.id, s.name) for s in subjects_list]

    if request.method == 'GET':
        subject_id_qs = request.args.get('subject_id', type=int)
        valid_subject_ids = {subject.id for subject in subjects_list}
        if subject_id_qs in valid_subject_ids:
            form.subject_id.data = subject_id_qs

    if form.validate_on_submit():
        saved_images = []
        try:
            image_path = _save_uploaded_image_field(form.image.data)
            if image_path:
                saved_images.append(image_path)

            explanation_image_path = _save_uploaded_image_field(form.explanation_image.data)
            if explanation_image_path:
                saved_images.append(explanation_image_path)

            option_image_paths = []
            for field_name in _OPTION_IMAGE_FIELD_NAMES:
                option_image_path = _save_uploaded_image_field(getattr(form, field_name).data)
                option_image_paths.append(option_image_path)
                if option_image_path:
                    saved_images.append(option_image_path)

            question = Question(
                subject_id=form.subject_id.data,
                text=form.text.data,
                reference_text=form.reference.data,
                image_path=image_path,
                explanation=form.explanation.data,
                explanation_image_path=explanation_image_path,
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
                    image_path=option_image_paths[i],
                    is_correct=(i == correct_idx)
                )
                db.session.add(opt)

            db.session.commit()
        except (ValueError, RuntimeError) as exc:
            db.session.rollback()
            _delete_images(saved_images)
            flash(str(exc), 'danger')
            return render_template('teacher/question_form.html', title='Nova Questão',
                                   form=form, existing_options=[])
        except Exception:
            db.session.rollback()
            _delete_images(saved_images)
            raise

        if form.save_and_new.data:
            flash('Questão criada com sucesso! Pode cadastrar a próxima.', 'success')
            return redirect(url_for('teacher.create_question', subject_id=form.subject_id.data))

        flash('Questão criada com sucesso!', 'success')
        return redirect(url_for('teacher.questions', subject_id=form.subject_id.data))

    return render_template('teacher/question_form.html', title='Nova Questão', form=form,
                           existing_options=[])


@bp.route('/questoes/<int:question_id>/editar', methods=['GET', 'POST'])
@login_required
@teacher_required
def edit_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.created_by != current_user.id:
        abort(403)

    subjects_list = Subject.query.filter_by(created_by=current_user.id).order_by(Subject.name).all()
    options = question.answer_options.order_by(AnswerOption.id.asc()).all()

    form = QuestionForm()
    form.subject_id.choices = [(s.id, s.name) for s in subjects_list]

    if request.method == 'GET':
        form.subject_id.data = question.subject_id
        form.reference.data = question.reference_text
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
        previous_option_paths = [opt.image_path for opt in options]
        new_uploaded_images = []

        try:
            image_path = _save_uploaded_image_field(form.image.data, current_path=question.image_path)
            if image_path != question.image_path and image_path:
                new_uploaded_images.append(image_path)

            explanation_image_path = _save_uploaded_image_field(
                form.explanation_image.data,
                current_path=question.explanation_image_path,
            )
            if (explanation_image_path != question.explanation_image_path
                    and explanation_image_path):
                new_uploaded_images.append(explanation_image_path)

            option_image_paths = []
            for index, field_name in enumerate(_OPTION_IMAGE_FIELD_NAMES):
                current_option_path = previous_option_paths[index] if index < len(previous_option_paths) else None
                option_image_path = _save_uploaded_image_field(
                    getattr(form, field_name).data,
                    current_path=current_option_path,
                )
                option_image_paths.append(option_image_path)
                if option_image_path != current_option_path and option_image_path:
                    new_uploaded_images.append(option_image_path)
        except (ValueError, RuntimeError) as exc:
            _delete_images(new_uploaded_images)
            flash(str(exc), 'danger')
            return render_template('teacher/question_form.html', title='Editar Questão',
                                   form=form, question=question, existing_options=options)

        old_images_to_delete = []
        if image_path != question.image_path and question.image_path:
            old_images_to_delete.append(question.image_path)
        if (explanation_image_path != question.explanation_image_path
                and question.explanation_image_path):
            old_images_to_delete.append(question.explanation_image_path)
        for index, previous_option_path in enumerate(previous_option_paths):
            if index < len(option_image_paths) and option_image_paths[index] != previous_option_path and previous_option_path:
                old_images_to_delete.append(previous_option_path)

        question.subject_id = form.subject_id.data
        question.reference_text = form.reference.data
        question.text = form.text.data
        question.image_path = image_path
        question.explanation = form.explanation.data
        question.explanation_image_path = explanation_image_path

        options_texts = [
            form.option_1.data, form.option_2.data, form.option_3.data,
            form.option_4.data, form.option_5.data
        ]
        correct_idx = int(form.correct_option.data) - 1

        for i, text in enumerate(options_texts):
            if i < len(options):
                opt = options[i]
                opt.text = text
                opt.image_path = option_image_paths[i]
                opt.is_correct = (i == correct_idx)
            else:
                db.session.add(AnswerOption(
                    question_id=question.id,
                    text=text,
                    image_path=option_image_paths[i],
                    is_correct=(i == correct_idx)
                ))

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            _delete_images(new_uploaded_images)
            raise

        _delete_images(old_images_to_delete)
        flash('Questão atualizada com sucesso!', 'success')
        return redirect(url_for('teacher.questions'))

    return render_template('teacher/question_form.html', title='Editar Questão',
                           form=form, question=question, existing_options=options)


@bp.route('/questoes/<int:question_id>/excluir', methods=['POST'])
@login_required
@teacher_required
def delete_question(question_id):
    question = Question.query.get_or_404(question_id)
    if question.created_by != current_user.id:
        abort(403)

    _delete_images([
        question.image_path,
        question.explanation_image_path,
        *[option.image_path for option in question.answer_options.all()],
    ])

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


@bp.route('/alunos')
@login_required
@teacher_required
def students_overview():
    """List all students that have been assigned at least one exam by this teacher."""
    # Get distinct students assigned to exams created by current teacher
    teacher_exam_ids = [e.id for e in Exam.query.filter_by(created_by=current_user.id).all()]
    if not teacher_exam_ids:
        students = []
    else:
        student_ids = db.session.query(StudentExam.student_id)\
            .filter(StudentExam.exam_id.in_(teacher_exam_ids))\
            .distinct().all()
        student_ids = [s[0] for s in student_ids]
        students = User.query.filter(User.id.in_(student_ids))\
            .order_by(User.username).all()
    return render_template('teacher/students_overview.html',
                           title='Visão por Aluno',
                           students=students)


@bp.route('/alunos/<int:student_id>')
@login_required
@teacher_required
def student_report(student_id):
    """Show per-student overview: exams taken + best scores + most missed questions."""
    student = User.query.get_or_404(student_id)

    # Only exams created by this teacher assigned to this student
    teacher_exam_ids = [e.id for e in Exam.query.filter_by(created_by=current_user.id).all()]
    assignments = StudentExam.query.filter(
        StudentExam.student_id == student_id,
        StudentExam.exam_id.in_(teacher_exam_ids)
    ).all()

    if not assignments:
        abort(404)

    # Per-exam summary
    exam_summaries = []
    for assignment in assignments:
        completed_attempts = assignment.attempts.filter(
            ExamAttempt.completed_at.isnot(None)
        ).all()
        best = None
        if completed_attempts:
            scores = [a.score for a in completed_attempts if a.score is not None]
            best = max(scores) if scores else None
        exam_summaries.append({
            'exam': assignment.exam,
            'assignment': assignment,
            'attempt_count': len(completed_attempts),
            'best_score': best,
        })

    # Most missed questions across all completed attempts
    from collections import Counter
    question_errors = Counter()
    question_map = {}

    for assignment in assignments:
        completed_attempts = assignment.attempts.filter(
            ExamAttempt.completed_at.isnot(None)
        ).all()
        for attempt in completed_attempts:
            for answer in attempt.answers.all():
                if not answer.is_correct():
                    eq = answer.exam_question
                    q = eq.question
                    question_errors[q.id] += 1
                    if q.id not in question_map:
                        question_map[q.id] = q

    most_missed = [
        {'question': question_map[qid], 'error_count': count}
        for qid, count in question_errors.most_common(20)
    ]

    return render_template('teacher/student_report.html',
                           title=f'Relatório de {student.username}',
                           student=student,
                           exam_summaries=exam_summaries,
                           most_missed=most_missed)


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


def _extract_package_yaml_and_images(raw_zip_bytes):
    """Read a ZIP package and return (yaml_bytes, images_map)."""
    try:
        memory = io.BytesIO(raw_zip_bytes)
        zf = zipfile.ZipFile(memory)
    except zipfile.BadZipFile as exc:
        raise ValueError('Pacote ZIP inválido ou corrompido.') from exc

    with zf:
        names = [n for n in zf.namelist() if not n.endswith('/')]
        yaml_candidates = [n for n in names if n.lower().endswith(('.yaml', '.yml'))]
        if not yaml_candidates:
            raise ValueError('O pacote ZIP deve conter um arquivo YAML com as questões.')

        preferred = sorted(
            yaml_candidates,
            key=lambda n: (0 if 'quest' in os.path.basename(n).lower() else 1, len(n)),
        )[0]

        yaml_bytes = zf.read(preferred)
        images = {}
        for name in names:
            base = os.path.basename(name)
            if not base:
                continue
            ext = os.path.splitext(base)[1].lower().lstrip('.')
            if ext not in current_app.config.get('ALLOWED_EXTENSIONS',
                                                 {'png', 'jpg', 'jpeg', 'gif', 'webp'}):
                continue
            images[base.lower()] = zf.read(name)

        return yaml_bytes, images


def _save_imported_image_bytes(original_name, content_bytes):
    """Persist imported image bytes in S3 or local storage with a unique filename."""
    return save_image_bytes(original_name, content_bytes)


def _import_optional_package_image(image_file_name, package_images, image_stats):
    image_file_name = os.path.basename(str(image_file_name or '')).strip()
    if not image_file_name:
        return None

    image_bytes = package_images.get(image_file_name.lower())
    if image_bytes is None:
        image_stats['missing'] += 1
        return None

    try:
        image_path = _save_imported_image_bytes(image_file_name, image_bytes)
        image_stats['imported'] += 1
        return image_path
    except (ValueError, RuntimeError):
        image_stats['invalid'] += 1
        return None


def _parse_yaml_questions(raw_bytes):
    """Parse and validate YAML bytes; return list of validated question dicts.

    Expected format::

        questions:
          - text: "Enunciado da questão"
            image_file: "q00001_enunciado.png"              # optional
            explanation: "Explicação opcional"              # optional
            explanation_image_file: "q00001_explicacao.png" # optional
            correct: 1                                       # 1-indexed (1–5)
            options:
              - text: "Opção A"
                image_file: "q00001_opcao_1.png"           # optional
              - text: "Opção B"
              - text: "Opção C"
              - text: "Opção D"
              - text: "Opção E"

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
        options_raw = item.get('options')
        if not isinstance(options_raw, list) or len(options_raw) != _YAML_REQUIRED_OPTIONS:
            raise ValueError(
                f'{prefix}: "options" deve ser uma lista com exatamente '
                f'{_YAML_REQUIRED_OPTIONS} itens.'
            )

        options = []
        for option_idx, opt in enumerate(options_raw, start=1):
            if isinstance(opt, dict):
                opt_text = str(opt.get('text', '') or '').strip()
                opt_image_file = os.path.basename(str(opt.get('image_file', '') or '').strip())
            else:
                opt_text = str(opt).strip()
                opt_image_file = ''

            if not opt_text:
                raise ValueError(f'{prefix}: a opção {option_idx} não pode ser vazia.')

            options.append({
                'text': opt_text,
                'image_file': opt_image_file,
            })

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

        reference = str(item.get('reference', '') or '').strip()
        explanation = str(item.get('explanation', '') or '').strip()
        image_file = os.path.basename(str(item.get('image_file', '') or '').strip())
        explanation_image_file = os.path.basename(
            str(item.get('explanation_image_file', '') or '').strip()
        )

        parsed.append({
            'text': text,
            'reference': reference,
            'explanation': explanation,
            'image_file': image_file,
            'explanation_image_file': explanation_image_file,
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

        package_raw = form.package_file.data.read()

        try:
            yaml_bytes, package_images = _extract_package_yaml_and_images(package_raw)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('teacher/import_questions.html',
                                   title='Importar Questões', form=form)

        try:
            parsed = _parse_yaml_questions(yaml_bytes)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('teacher/import_questions.html',
                                   title='Importar Questões', form=form)

        imported = 0
        image_stats = {'imported': 0, 'missing': 0, 'invalid': 0}

        for q_data in parsed:
            image_path = _import_optional_package_image(
                q_data.get('image_file'),
                package_images,
                image_stats,
            )
            explanation_image_path = _import_optional_package_image(
                q_data.get('explanation_image_file'),
                package_images,
                image_stats,
            )

            question = Question(
                subject_id=subject.id,
                text=q_data['text'],
                reference_text=q_data['reference'] or None,
                explanation=q_data['explanation'] or None,
                image_path=image_path,
                explanation_image_path=explanation_image_path,
                created_by=current_user.id,
            )
            db.session.add(question)
            db.session.flush()

            for i, opt_data in enumerate(q_data['options']):
                opt = AnswerOption(
                    question_id=question.id,
                    text=opt_data['text'],
                    image_path=_import_optional_package_image(
                        opt_data.get('image_file'),
                        package_images,
                        image_stats,
                    ),
                    is_correct=(i == q_data['correct_idx']),
                )
                db.session.add(opt)

            imported += 1

        db.session.commit()
        flash(
            f'{imported} questão(ões) importada(s) para "{subject.name}". '
            f'Imagens importadas: {image_stats["imported"]}. '
            f'Não encontradas: {image_stats["missing"]}. '
            f'Inválidas: {image_stats["invalid"]}.',
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
        "# Modelo de questões para pacote ZIP de migração - TestPracticeTool\n"
        "#\n"
        "# Regras:\n"
        "#   - Este YAML deve estar dentro de um arquivo .zip junto das imagens.\n"
        "#   - Cada questão deve ter exatamente 5 opções.\n"
        "#   - O campo 'correct' indica o número da opção correta (1 a 5).\n"
        "#   - O campo 'image_file' é opcional e deve apontar para uma imagem no ZIP.\n"
        "#   - O campo 'reference' é opcional e serve como texto de apoio na prova.\n"
        "#   - O campo 'explanation' é opcional (aparece apenas no gabarito).\n"
        "#   - 'explanation_image_file' e imagens das opções também são opcionais.\n"
        "\n"
        "questions:\n"
        "  - text: \"Qual é o resultado de 2 + 2?\"\n"
        "    reference: \"Lembre que somar dois números positivos aumenta o resultado.\"\n"
        "    image_file: \"q00001_soma.png\"\n"
        "    explanation: \"A soma de 2 com 2 é igual a 4.\"\n"
        "    explanation_image_file: \"q00001_explicacao.png\"\n"
        "    correct: 3\n"
        "    options:\n"
        "      - text: \"2\"\n"
        "      - text: \"3\"\n"
        "      - text: \"4\"\n"
        "        image_file: \"q00001_opcao_3.png\"\n"
        "      - text: \"5\"\n"
        "      - text: \"6\"\n"
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
