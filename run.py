from app import create_app, db
from app.models import User, Subject, Question, AnswerOption, Exam, ExamQuestion, \
    ExamQuestionOption, StudentExam, ExamAttempt, AttemptAnswer

app = create_app()


@app.shell_context_processor
def make_shell_context():
    return {
        'db': db,
        'User': User,
        'Subject': Subject,
        'Question': Question,
        'AnswerOption': AnswerOption,
        'Exam': Exam,
        'ExamQuestion': ExamQuestion,
        'ExamQuestionOption': ExamQuestionOption,
        'StudentExam': StudentExam,
        'ExamAttempt': ExamAttempt,
        'AttemptAnswer': AttemptAnswer,
    }


if __name__ == '__main__':
    import os
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    app.run(host=host, port=port, debug=debug)
