from datetime import datetime, timezone
from flask import render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from app import db
from app.student import bp
from app.models import StudentExam, ExamAttempt, AttemptAnswer, ExamQuestion, AnswerOption


def student_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if (not current_user.is_authenticated
                or not current_user.is_student()
                or not current_user.is_active):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/dashboard')
@login_required
@student_required
def dashboard():
    assignments = StudentExam.query.filter_by(student_id=current_user.id).all()
    return render_template('student/dashboard.html', title='Minhas Provas',
                           assignments=assignments)


@bp.route('/prova/<int:assignment_id>/iniciar', methods=['GET', 'POST'])
@login_required
@student_required
def start_exam(assignment_id):
    assignment = StudentExam.query.get_or_404(assignment_id)
    if assignment.student_id != current_user.id:
        abort(403)

    can, message = assignment.can_attempt()
    if not can:
        flash(message, 'danger')
        return redirect(url_for('student.dashboard'))

    # Check for an in-progress attempt
    in_progress = ExamAttempt.query.filter_by(student_exam_id=assignment.id,
                                              completed_at=None).first()
    if in_progress:
        return redirect(url_for('student.take_exam', attempt_id=in_progress.id))

    if request.method == 'POST':
        attempt = ExamAttempt(student_exam_id=assignment.id)
        db.session.add(attempt)
        db.session.commit()
        return redirect(url_for('student.take_exam', attempt_id=attempt.id))

    return render_template('student/start_exam.html', title='Iniciar Prova',
                           assignment=assignment)


@bp.route('/tentativa/<int:attempt_id>')
@login_required
@student_required
def take_exam(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    assignment = attempt.student_exam
    if assignment.student_id != current_user.id:
        abort(403)
    if attempt.completed_at is not None:
        return redirect(url_for('student.exam_result', attempt_id=attempt_id))

    exam = assignment.exam
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()

    # Existing answers map
    existing_answers = {a.exam_question_id: a.selected_option_id
                        for a in attempt.answers.all()}

    return render_template('student/take_exam.html', title=exam.title,
                           attempt=attempt, exam=exam, questions=questions_list,
                           existing_answers=existing_answers,
                           time_limit=assignment.time_limit_minutes)


@bp.route('/tentativa/<int:attempt_id>/submeter', methods=['POST'])
@login_required
@student_required
def submit_exam(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    assignment = attempt.student_exam
    if assignment.student_id != current_user.id:
        abort(403)
    if attempt.completed_at is not None:
        return redirect(url_for('student.exam_result', attempt_id=attempt_id))

    exam = assignment.exam
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()

    # Save/update answers
    existing_answers = {a.exam_question_id: a for a in attempt.answers.all()}

    for eq in questions_list:
        field_name = f'question_{eq.id}'
        selected_id = request.form.get(field_name, type=int)

        if eq.id in existing_answers:
            existing_answers[eq.id].selected_option_id = selected_id
        else:
            answer = AttemptAnswer(
                attempt_id=attempt.id,
                exam_question_id=eq.id,
                selected_option_id=selected_id
            )
            db.session.add(answer)

    attempt.completed_at = datetime.now(timezone.utc)
    attempt.score = _calculate_score(attempt, questions_list)
    db.session.commit()

    flash('Prova concluída!', 'success')
    return redirect(url_for('student.exam_result', attempt_id=attempt.id))


def _calculate_score(attempt, questions_list):
    total = len(questions_list)
    if total == 0:
        return 0.0
    correct = 0
    answers_map = {a.exam_question_id: a for a in attempt.answers.all()}
    for eq in questions_list:
        answer = answers_map.get(eq.id)
        if answer and answer.selected_option_id:
            opt = db.session.get(AnswerOption, answer.selected_option_id)
            if opt and opt.is_correct:
                correct += 1
    return round((correct / total) * 100, 2)


@bp.route('/tentativa/<int:attempt_id>/resultado')
@login_required
@student_required
def exam_result(attempt_id):
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    assignment = attempt.student_exam
    if assignment.student_id != current_user.id:
        abort(403)
    if attempt.completed_at is None:
        return redirect(url_for('student.take_exam', attempt_id=attempt_id))

    exam = assignment.exam
    questions_list = exam.exam_questions.order_by(ExamQuestion.order_number).all()
    answers_map = {a.exam_question_id: a for a in attempt.answers.all()}

    return render_template('student/exam_result.html', title='Resultado',
                           attempt=attempt, exam=exam,
                           questions=questions_list, answers_map=answers_map)
