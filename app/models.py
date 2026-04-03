from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='student')  # 'teacher' or 'student'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)

    # Relationships
    subjects = db.relationship('Subject', backref='creator', lazy='dynamic',
                               foreign_keys='Subject.created_by')
    questions = db.relationship('Question', backref='creator', lazy='dynamic',
                                foreign_keys='Question.created_by')
    exams_created = db.relationship('Exam', backref='creator', lazy='dynamic',
                                    foreign_keys='Exam.created_by')
    student_exams = db.relationship('StudentExam', backref='student', lazy='dynamic',
                                    foreign_keys='StudentExam.student_id')
    exams_assigned = db.relationship('StudentExam', backref='assigner', lazy='dynamic',
                                     foreign_keys='StudentExam.assigned_by')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_teacher(self):
        return self.role == 'teacher'

    def is_student(self):
        return self.role == 'student'

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    from app import db
    return db.session.get(User, int(user_id))


class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    questions = db.relationship('Question', backref='subject', lazy='dynamic',
                                cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Subject {self.name}>'


class Question(db.Model):
    __tablename__ = 'questions'

    id = db.Column(db.Integer, primary_key=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.String(256))
    explanation = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    answer_options = db.relationship('AnswerOption', backref='question', lazy='dynamic',
                                     cascade='all, delete-orphan')

    def get_correct_option(self):
        return AnswerOption.query.filter_by(question_id=self.id, is_correct=True).first()

    def __repr__(self):
        return f'<Question {self.id}>'


class AnswerOption(db.Model):
    __tablename__ = 'answer_options'

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<AnswerOption {self.id}>'


class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    exam_questions = db.relationship('ExamQuestion', backref='exam', lazy='dynamic',
                                     cascade='all, delete-orphan',
                                     order_by='ExamQuestion.order_number')
    student_exams = db.relationship('StudentExam', backref='exam', lazy='dynamic',
                                    cascade='all, delete-orphan')

    def total_questions(self):
        return self.exam_questions.count()

    def __repr__(self):
        return f'<Exam {self.title}>'


class ExamQuestion(db.Model):
    """Stores a specific question in an exam with its randomized answer order."""
    __tablename__ = 'exam_questions'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    order_number = db.Column(db.Integer, nullable=False)

    question = db.relationship('Question')
    options = db.relationship('ExamQuestionOption', backref='exam_question', lazy='dynamic',
                               cascade='all, delete-orphan',
                               order_by='ExamQuestionOption.display_order')
    attempt_answers = db.relationship('AttemptAnswer', backref='exam_question', lazy='dynamic')

    def __repr__(self):
        return f'<ExamQuestion exam={self.exam_id} q={self.question_id}>'


class ExamQuestionOption(db.Model):
    """Stores the randomized display order of answer options for a specific exam question."""
    __tablename__ = 'exam_question_options'

    id = db.Column(db.Integer, primary_key=True)
    exam_question_id = db.Column(db.Integer, db.ForeignKey('exam_questions.id'), nullable=False)
    answer_option_id = db.Column(db.Integer, db.ForeignKey('answer_options.id'), nullable=False)
    display_order = db.Column(db.Integer, nullable=False)

    answer_option = db.relationship('AnswerOption')

    def __repr__(self):
        return f'<ExamQuestionOption {self.id}>'


class StudentExam(db.Model):
    """Assignment of an exam to a student with constraints."""
    __tablename__ = 'student_exams'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    max_attempts = db.Column(db.Integer, default=1, nullable=False)
    time_limit_minutes = db.Column(db.Integer)  # None means no time limit
    available_from = db.Column(db.DateTime)
    available_until = db.Column(db.DateTime)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    attempts = db.relationship('ExamAttempt', backref='student_exam', lazy='dynamic',
                               cascade='all, delete-orphan',
                               order_by='ExamAttempt.started_at.desc()')

    def attempt_count(self):
        return self.attempts.count()

    def can_attempt(self):
        now = datetime.now(timezone.utc)
        if self.available_from and now < self.available_from.replace(tzinfo=timezone.utc):
            return False, 'A prova ainda não está disponível.'
        if self.available_until and now > self.available_until.replace(tzinfo=timezone.utc):
            return False, 'O prazo para realizar a prova expirou.'
        completed = self.attempts.filter(ExamAttempt.completed_at.isnot(None)).count()
        if completed >= self.max_attempts:
            return False, f'Você atingiu o número máximo de tentativas ({self.max_attempts}).'
        return True, ''

    def best_score(self):
        completed = self.attempts.filter(ExamAttempt.completed_at.isnot(None)).all()
        if not completed:
            return None
        return max(a.score for a in completed if a.score is not None)

    def get_last_completed_attempt(self):
        return self.attempts.filter(
            ExamAttempt.completed_at.isnot(None)
        ).order_by(ExamAttempt.started_at.desc()).first()

    def __repr__(self):
        return f'<StudentExam student={self.student_id} exam={self.exam_id}>'


class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'

    id = db.Column(db.Integer, primary_key=True)
    student_exam_id = db.Column(db.Integer, db.ForeignKey('student_exams.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)
    score = db.Column(db.Float)  # percentage 0-100

    answers = db.relationship('AttemptAnswer', backref='attempt', lazy='dynamic',
                              cascade='all, delete-orphan')

    def calculate_score(self):
        total = self.answers.count()
        if total == 0:
            return 0.0
        correct = sum(1 for a in self.answers.all() if a.is_correct())
        return round((correct / total) * 100, 2)

    def __repr__(self):
        return f'<ExamAttempt {self.id}>'


class AttemptAnswer(db.Model):
    __tablename__ = 'attempt_answers'

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id'), nullable=False)
    exam_question_id = db.Column(db.Integer, db.ForeignKey('exam_questions.id'), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey('answer_options.id'))

    selected_option = db.relationship('AnswerOption')

    def is_correct(self):
        if self.selected_option is None:
            return False
        return self.selected_option.is_correct

    def __repr__(self):
        return f'<AttemptAnswer attempt={self.attempt_id} eq={self.exam_question_id}>'
