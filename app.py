from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, Boolean, Date, Time, Text, ForeignKey, DateTime, desc
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date, time, timedelta
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os 
from typing import Optional
from collections import defaultdict
import math
from datetime import datetime, time as time_type


app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///studentojt.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


db = SQLAlchemy(app)


class Admin(db.Model):
    __tablename__ = 'admin'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="Admin")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    announcements: Mapped[list["Announcement"]] = relationship(back_populates="admin")
    remarks: Mapped[list["AttendanceRemark"]] = relationship(back_populates="reviewer")

    def __repr__(self):
        return f"<Admin {self.name} ({self.role})>"



class Student(db.Model):
    __tablename__ = 'student'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    usn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    contact_number: Mapped[str] = mapped_column(String(20))
    program: Mapped[str] = mapped_column(String(100))
    required_hours: Mapped[int] = mapped_column(Integer)
    total_rendered_hours: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="Ongoing")
    password: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="Student")
    
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    target_end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    attendance_logs: Mapped[list["AttendanceLog"]] = relationship(
        "AttendanceLog",
        back_populates="student",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Student {self.name} ({self.role})>"

    def remaining_hours(self) -> int:
        return max(self.required_hours - self.total_rendered_hours, 0)

    def completion_percentage(self) -> float:
        if not self.required_hours:
            return 0.0
        return round((self.total_rendered_hours / self.required_hours) * 100, 2)

    def days_attended(self) -> int:
        return len(set(log.log_date for log in self.attendance_logs))

    def full_name(self) -> str:
        return self.name.title()



class AttendanceLog(db.Model):
    __tablename__ = 'attendance_log'
    id: Mapped[int] = mapped_column(primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey('student.id', ondelete='CASCADE'), nullable=False)
    log_date: Mapped[date] = mapped_column(Date)
    time_in: Mapped[time] = mapped_column(Time)
    time_out: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    duration_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hours_worked: Mapped[Optional[float]] = mapped_column(Float, nullable=True) 
    time_in_photo: Mapped[str] = mapped_column(String(200))
    time_out_photo: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)

    student: Mapped["Student"] = relationship(back_populates="attendance_logs")
    feedback: Mapped[list["AttendanceRemark"]] = relationship(back_populates="attendance_log")

    def __repr__(self):
        return f"<AttendanceLog StudentID={self.student_id} Date={self.log_date}>"

    def formatted_duration(self) -> str:
        if self.duration_hours is None:
            return "-"
        hours = int(self.duration_hours)
        minutes = int(round((self.duration_hours - hours) * 60))
        return f"{hours} hr{'s' if hours != 1 else ''} {minutes} min{'s' if minutes != 1 else ''}"

    def formatted_time_in(self) -> str:
        return self.time_in.strftime("%I:%M %p") if self.time_in else "-"

    def formatted_time_out(self) -> str:
        return self.time_out.strftime("%I:%M %p") if self.time_out else "-"



class AttendanceRemark(db.Model):
    __tablename__ = 'attendance_remark'
    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_log_id: Mapped[int] = mapped_column(ForeignKey('attendance_log.id'))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('admin.id'))
    comment: Mapped[str] = mapped_column(Text)
    date_commented: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    attendance_log: Mapped["AttendanceLog"] = relationship(back_populates="feedback")
    reviewer: Mapped["Admin"] = relationship(back_populates="remarks")

    def __repr__(self):
        return f"<Remark AdminID={self.reviewer_id} on LogID={self.attendance_log_id}>"


class Announcement(db.Model):
    __tablename__ = 'announcement'
    id: Mapped[int] = mapped_column(primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey('admin.id'))
    title: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    date_posted: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    admin: Mapped["Admin"] = relationship(back_populates="announcements")

    def __repr__(self):
        return f"<Announcement '{self.title}' by AdminID={self.admin_id}>"




@app.context_processor
def inject_now():
    return {'current_year': datetime.now().year}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select-signup')
def select_signup():
    return render_template('select_signup.html')

@app.route('/select-login')
def select_login():
    return render_template('select_login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    role = request.args.get('role') if request.method == 'GET' else request.form.get('role')
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']

        try:
            if role == 'student':
                usn = request.form['usn']
                contact_number = request.form['contact_number']
                program = request.form['program']
                required_hours = request.form['required_hours']

                new_student = Student(
                    usn=usn,
                    name=name,
                    email=email,
                    contact_number=contact_number,
                    program=program,
                    required_hours=int(required_hours),
                    password=generate_password_hash(password)
                )
                db.session.add(new_student)

            elif role == 'admin':
                new_admin = Admin(
                    name=name,
                    email=email,
                    password=generate_password_hash(password),
                    role='Admin'
                )
                db.session.add(new_admin)

            db.session.commit()
            flash(f'{role.capitalize()} registered successfully!', 'success')
            return redirect(url_for('index'))

        except IntegrityError:
            db.session.rollback()
            flash("Email or ID already exists.", "danger")

    return render_template('register.html', role=role)


@app.route('/login', methods=['GET', 'POST'])
def login():
    role = request.args.get('role') if request.method == 'GET' else request.form.get('role')

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if role == 'student':
            student = Student.query.filter_by(email=email).first()
            if student and check_password_hash(student.password, password):
                session['user_id'] = student.id
                session['role'] = 'student'
                session['name'] = student.name
                flash("Logged in as student", "success")
                return redirect(url_for('student_dashboard'))

        elif role == 'admin':
            admin = Admin.query.filter_by(email=email).first()
            if admin and check_password_hash(admin.password, password):
                session['user_id'] = admin.id
                session['role'] = 'admin'
                session['name'] = admin.name
                flash("Logged in as admin", "success")
                return redirect(url_for('admin_dashboard'))

        flash("Invalid credentials", "danger")

    return render_template('login.html', role=role)



@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Please log in as admin first.", "warning")
        return redirect(url_for('login', role='admin'))

    total_students = Student.query.count()
    flagged_entries = AttendanceLog.query.filter_by(is_flagged=True).count()
    ongoing_ojt = Student.query.filter_by(status="Ongoing").count()


    students = Student.query.all()
    attendance_logs = AttendanceLog.query.order_by(AttendanceLog.log_date.desc()).limit(50).all()
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).limit(10).all()


    return render_template(
        'admin_dashboard.html',
        name=session.get('name', 'Admin'),
        total_students=total_students,
        flagged_entries=flagged_entries,
        ongoing_ojt=ongoing_ojt,
        students=students,
        attendance_logs=attendance_logs,
        announcements=announcements,
    )



@app.route('/manage_students')
def view_students():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access. Please log in as admin.", "danger")
        return redirect(url_for('login', role='admin'))

    students = Student.query.order_by(Student.name.asc()).all()
    return render_template('manage_students.html', students=students)


@app.route('/student/delete/<int:student_id>', methods=['POST'])
def delete_view_student(student_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login', role='admin'))

    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    flash("Student deleted successfully.", "success")
    return redirect(url_for('view_students'))



@app.route('/attendance')
def view_attendance():
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Please log in as admin first.", "warning")
        return redirect(url_for('login', role='admin'))

    logs = AttendanceLog.query.order_by(AttendanceLog.log_date.desc()).all()
    return render_template('attendance_logs.html', logs=logs)


@app.route('/attendance_log/edit/<int:log_id>', methods=['POST'])
def edit_attendance_log(log_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login', role='admin'))

    log = AttendanceLog.query.get_or_404(log_id)
    log.is_flagged = True if request.form.get('is_flagged') == 'on' else False
    log.remarks = request.form.get('remarks') or None

    db.session.commit()
    flash("Attendance log updated.", "success")
    return redirect(url_for('view_attendance'))



@app.route('/announcements')
def announcements():
    announcements = Announcement.query.order_by(Announcement.date_posted.desc()).all()
    return render_template('announcements.html', announcements=announcements)

@app.route('/post-announcement', methods=['GET', 'POST'])
def post_announcement():
    if request.method == 'POST':
        title = request.form['title']
        message = request.form['message']
        new_announcement = Announcement(title=title, message=message, date_posted=datetime.utcnow())
        db.session.add(new_announcement)
        db.session.commit()
        flash('Announcement posted successfully!', 'success')
        return redirect(url_for('announcements'))
    return render_template('post_announcement.html')



@app.route('/announcement/edit/<int:announcement_id>', methods=['GET', 'POST'])
def edit_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    if request.method == 'POST':
        announcement.title = request.form['title']
        announcement.message = request.form['message']
        db.session.commit()
        flash('Announcement updated successfully!', 'success')
        return redirect(url_for('announcements'))
    return render_template('edit_announcement.html', announcement=announcement)



@app.route('/announcement/delete/<int:announcement_id>', methods=['POST'])
def delete_announcement(announcement_id):
    announcement = Announcement.query.get_or_404(announcement_id)
    db.session.delete(announcement)
    db.session.commit()
    flash('Announcement deleted successfully!', 'success')
    return redirect(url_for('announcements'))



@app.route('/student')
def student_dashboard():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Please log in as a student first.", "warning")
        return redirect(url_for('login', role='student'))

    student = db.session.get(Student, session['user_id'])
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('login', role='student'))

    latest_announcements = Announcement.query.order_by(Announcement.date_posted.desc()).limit(2).all()

    today = datetime.utcnow().date()
    attendance = (
        AttendanceLog.query
        .filter_by(student_id=student.id, log_date=today)
        .first()
    )

    def combine_date_time(d: datetime.date, t: time_type | None) -> datetime | None:
        if d and t:
            return datetime.combine(d, t)
        return None

    time_in_dt = combine_date_time(attendance.log_date, attendance.time_in) if attendance else None
    time_out_dt = combine_date_time(attendance.log_date, attendance.time_out) if attendance and attendance.time_out else None

    return render_template(
        'student_dashboard.html',
        student=student,
        latest_announcements=latest_announcements,
        time_in=time_in_dt,
        time_out=time_out_dt
    )


@app.route('/student/edit/<int:student_id>', methods=['POST'])
def edit_student(student_id):
    if 'user_id' not in session or session.get('role') != 'admin':
        flash("Unauthorized access", "danger")
        return redirect(url_for('login', role='admin'))

    student = Student.query.get_or_404(student_id)
    student.name = request.form['name']
    student.email = request.form['email']
    student.program = request.form['program']
    student.status = request.form['status']

    db.session.commit()
    flash("Student record updated.", "success")
    return redirect(url_for('view_students'))




@app.route('/student/profile')
def student_profile():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student = db.session.get(Student, session['user_id'])
    return render_template('student_profile.html', student=student)

@app.route('/student/edit/self', methods=['POST'])
def student_edit_self():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student = db.session.get(Student, session['user_id'])

    student.name = request.form['name']
    student.email = request.form['email']
    student.program = request.form['program']
    student.status = request.form['status']

    db.session.commit()
    flash("Profile updated successfully.", "success")
    return redirect(url_for('student_profile'))




@app.route('/student/attendance')
def student_attendance():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student_id = session['user_id']
    student = Student.query.get(student_id)
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for('login', role='student'))

    attendance_logs = AttendanceLog.query.filter_by(student_id=student_id).order_by(desc(AttendanceLog.log_date)).all()

    return render_template(
        'student_attendance.html',
        student=student,
        attendance_logs=attendance_logs
    )


@app.route('/time_in_form')
def time_in_form():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))
    return render_template('time_in_form.html')



@app.route('/submit_time_in', methods=['POST'])
def submit_time_in():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student_id = session['user_id']
    student = Student.query.get(student_id)
    today = date.today()

    file = request.files.get('photo')

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{student_id}_in_{today}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        now = datetime.now().time()

        if not student.start_date:
            student.start_date = today
            estimated_days = math.ceil(student.required_hours / 4) or 1
            student.target_end_date = today + timedelta(days=estimated_days)

        new_log = AttendanceLog(
            student_id=student_id,
            log_date=today,
            time_in=now,
            time_in_photo=filename
        )
        db.session.add(new_log)
        db.session.commit()

        flash("Time In recorded successfully.", "success")
        return redirect(url_for('student_attendance'))

    flash("Invalid file upload. Please upload a valid image file.", "danger")
    return redirect(url_for('time_in_form'))



@app.route('/time_out/<int:log_id>', methods=['GET'])
def time_out_form(log_id):
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    log = AttendanceLog.query.get_or_404(log_id)
    if log.student_id != session['user_id']:
        flash("You can only time out your own logs.", "danger")
        return redirect(url_for('student_attendance'))

    return render_template('time_out_form.html', log=log)


@app.route('/submit_time_out/<int:log_id>', methods=['POST'])
def submit_time_out(log_id):
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))
    log = AttendanceLog.query.get_or_404(log_id)
    
    if log.student_id != session['user_id']:
        flash("You can only time out your own logs.", "danger")
        return redirect(url_for('student_attendance'))
    if log.time_out is not None:
        flash("You have already timed out for this log.", "warning")
        return redirect(url_for('student_attendance'))
    file = request.files.get('photo')
    if file and allowed_file(file.filename):
        today = log.log_date
        student_id = log.student_id
        filename = secure_filename(f"{student_id}_out_{today}.jpg")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        now = datetime.now().time()
        log.time_out = now
        log.time_out_photo = filename

        time_in_dt = datetime.combine(today, log.time_in)
        time_out_dt = datetime.combine(today, now)
        duration = (time_out_dt - time_in_dt).total_seconds() / 3600
        log.duration_hours = round(duration, 2)

        student = Student.query.get(student_id)
        student.total_rendered_hours += log.duration_hours

        db.session.commit()
        flash("Time Out recorded successfully.", "success")
        return redirect(url_for('student_attendance'))

    flash("Invalid file upload. Please upload a valid image file.", "danger")
    return redirect(url_for('time_out_form', log_id=log_id))


@app.route('/attendance_history')
def attendance_history():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student_id = session['user_id']
    attendance_logs = AttendanceLog.query.filter_by(student_id=student_id).order_by(AttendanceLog.log_date.desc()).all()

    return render_template('attendance_history.html', attendance_logs=attendance_logs)

@app.route('/student/announcements')
def student_announcements():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    announcements = Announcement.query.filter(Announcement.admin_id.isnot(None)).order_by(Announcement.date_posted.desc()).all()

    
    return render_template('student_announcements.html', announcements=announcements)



@app.route('/student/progress')
def ojt_progress():
    if 'user_id' not in session or session.get('role') != 'student':
        flash("Access denied.", "danger")
        return redirect(url_for('login', role='student'))

    student = db.session.get(Student, session['user_id'])

    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for('login', role='student'))

    required_hours = float(student.required_hours or 486)
    attendance_logs = student.attendance_logs or []

    total_hours_worked = float(sum(log.duration_hours or 0 for log in attendance_logs))

    remaining_hours = max(0, required_hours - total_hours_worked)

    weekly_hours = defaultdict(float)
    for log in attendance_logs:
        if log.log_date:
            week_start = log.log_date - timedelta(days=log.log_date.weekday())
            weekly_hours[week_start] += log.duration_hours or 0

    weekly_breakdown = sorted(weekly_hours.items(), key=lambda x: x[0], reverse=True)

    return render_template(
        'ojt_progress.html',
        student=student,
        total_hours_worked=total_hours_worked,
        required_hours=required_hours,
        remaining_hours=remaining_hours,
        weekly_breakdown=weekly_breakdown
    )




@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for('index'))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
