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
    app.run(debug=True)
