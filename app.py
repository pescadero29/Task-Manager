# app.py - Full Task Tracker application
import os
import io
import random
import string
from datetime import datetime, timedelta, date
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for, flash,
    session, send_file, jsonify, make_response
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from apscheduler.schedulers.background import BackgroundScheduler

# Optional exports
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# -------------------------
# Configuration
# -------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Database (SQLite default)
default_db = 'sqlite:///tasks.db'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', default_db)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail configuration (optional - set in environment or .env)
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', '')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587) or 587)
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', '')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', '')
app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_DEFAULT_SENDER'] = os.environ.get('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])

# Uploads / archive
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
ARCHIVE_FOLDER = os.path.join(os.getcwd(), 'archive')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'pdf', 'docx', 'txt'}

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)
scheduler = BackgroundScheduler()
scheduler.start()

# -------------------------
# Models
# -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(300), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tasks = db.relationship('Task', backref='user', lazy=True)
    inquiries = db.relationship('Inquiry', backref='user', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'

class OTP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(12), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(80), nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # Low/Medium/High
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='Pending')  # Pending/Completed
    attachment = db.Column(db.String(300), nullable=True)
    deleted = db.Column(db.Boolean, default=False)
    archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text)
    reply = db.Column(db.Text, nullable=True)
    replied = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default='Notification')
    message = db.Column(db.String(500))
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor = db.Column(db.String(200))
    action = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# -------------------------
# Helpers
# -------------------------
def add_log(actor, action):
    db.session.add(ActivityLog(actor=actor, action=action))
    db.session.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def random_otp(n=6):
    return ''.join(random.choices(string.digits, k=n))

def send_email(subject, recipients, body_text):
    """
    Send plain text email. recipients can be a string or list.
    If mail server not configured, this function will print and return silently.
    """
    if not app.config.get('MAIL_SERVER') or not app.config.get('MAIL_USERNAME'):
        print('Mail not configured — skipping email:', subject, recipients)
        return
    try:
        msg = Message(subject, recipients=[recipients] if isinstance(recipients, str) else recipients)
        msg.body = body_text
        mail.send(msg)
    except Exception as e:
        print('Error sending mail:', e)

# Decorators
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Login required.', 'warning')
            return redirect(url_for('login'))
        u = User.query.get(session['user_id'])
        if not u or not u.is_admin:
            flash('Admin access required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper

# Jinja globals
app.jinja_env.globals['User'] = User

# Context processor for now()
@app.context_processor
def inject_now():
    return {'now': datetime}

# -------------------------
# App startup
# -------------------------
@app.before_request
def setup():
    db.create_all()
    # create a default admin user if none exists
    if not User.query.filter_by(is_admin=True).first():
        admin = User(fullname='Admin', email='admin@example.com',
                     password_hash=generate_password_hash('admin123'), is_admin=True)
        db.session.add(admin)
        db.session.commit()
        add_log('system', 'Created default admin')

# -------------------------
# AUTH & OTP routes
# -------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        fullname = request.form.get('fullname') or request.form.get('username') or ''
        email = request.form.get('email') or request.form.get('username') or ''
        password = request.form.get('password', '')
        # basic validation
        if not fullname or not email or not password:
            flash('All fields required', 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'danger')
            return redirect(url_for('register'))

        user = User(fullname=fullname.strip(), email=email.strip(),
                    password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        # generate OTP and email
        code = random_otp(6)
        otp = OTP(code=code, expires_at=datetime.utcnow() + timedelta(minutes=10), user_id=user.id)
        db.session.add(otp)
        db.session.commit()

        send_email('Task Tracker — Verify your email', user.email,
                   f'Hello {user.fullname}, your verification OTP is {code}. It expires in 10 minutes.')

        add_log(user.email, 'Registered (OTP sent)')
        flash('Registered. OTP sent to your email — please verify.', 'success')
        return redirect(url_for('verify', user_id=user.id))
    return render_template('auth_register.html')

@app.route('/verify/<int:user_id>', methods=['GET', 'POST'])
def verify(user_id):
    user = User.query.get_or_404(user_id)
    otp = OTP.query.filter_by(user_id=user.id, used=False).order_by(OTP.expires_at.desc()).first()
    if request.method == 'POST':
        code = request.form.get('otp', '').strip()
        if not otp or otp.expires_at < datetime.utcnow():
            flash('OTP expired — resend.', 'danger')
            return redirect(url_for('resend_otp', user_id=user.id))
        if code == otp.code:
            otp.used = True
            db.session.commit()
            flash('Email verified — you can now log in.', 'success')
            add_log(user.email, 'Email verified')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP', 'danger')
    return render_template('verify.html', user=user)

@app.route('/resend_otp/<int:user_id>')
def resend_otp(user_id):
    user = User.query.get_or_404(user_id)
    # delete old OTPs
    OTP.query.filter_by(user_id=user.id).delete()
    db.session.commit()
    code = random_otp(6)
    otp = OTP(code=code, expires_at=datetime.utcnow() + timedelta(minutes=10), user_id=user.id)
    db.session.add(otp)
    db.session.commit()
    send_email('Task Tracker — Your new OTP', user.email, f'Your new OTP is {code}')
    add_log(user.email, 'OTP resent')
    flash('OTP resent to your email', 'info')
    return redirect(url_for('verify', user_id=user.id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid credentials', 'danger')
            return redirect(url_for('login'))

        # send a one-time OTP for login confirmation
        # keep temp id in session
        session['temp_user'] = user.id
        # delete previous OTPs for this user
        OTP.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        code = random_otp(6)
        otp = OTP(code=code, expires_at=datetime.utcnow() + timedelta(minutes=5), user_id=user.id)
        db.session.add(otp)
        db.session.commit()
        send_email('Task Tracker — Login OTP', user.email, f'Your login OTP is {code} (5 min)')
        add_log(user.email, 'Login OTP sent')
        flash('OTP sent to your email. Enter it to complete login.', 'info')
        return redirect(url_for('login_verify'))
    return render_template('auth_login.html')

@app.route('/login_verify', methods=['GET', 'POST'])
def login_verify():
    temp_id = session.get('temp_user')
    if not temp_id:
        flash('No login in progress', 'warning')
        return redirect(url_for('login'))
    user = User.query.get_or_404(temp_id)
    otp = OTP.query.filter_by(user_id=user.id, used=False).order_by(OTP.expires_at.desc()).first()
    if request.method == 'POST':
        code = request.form.get('otp', '').strip()
        if not otp or otp.expires_at < datetime.utcnow():
            flash('OTP expired', 'danger')
            return redirect(url_for('login'))
        if code == otp.code:
            otp.used = True
            db.session.commit()
            # set session
            session.clear()
            session['user_id'] = user.id
            session['username'] = user.fullname
            add_log(user.email, 'Logged in')
            flash('Logged in successfully', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid OTP', 'danger')
    return render_template('login_verify.html')

@app.route('/logout')
def logout():
    if session.get('username'):
        add_log(session.get('username'), 'Logged out')
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('login'))

# -------------------------
# TASK CRUD, attachments, priority, categories
# -------------------------
@app.route('/')
@login_required
def index():
    user_id = session['user_id']
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '')
    priority = request.args.get('priority', '')
    page = request.args.get('page', 1, type=int)

    query = Task.query.filter_by(user_id=user_id, deleted=False, archived=False)
    if q:
        qlike = f'%{q}%'
        query = query.filter((Task.title.ilike(qlike)) | (Task.description.ilike(qlike)))
    if category:
        query = query.filter_by(category=category)
    if priority:
        query = query.filter_by(priority=priority)

    pagination = query.order_by(Task.due_date.asc().nullslast(), Task.created_at.desc()).paginate(page=page, per_page=10, error_out=False)
    tasks = pagination.items

    # stats
    total = Task.query.filter_by(user_id=user_id, deleted=False).count()
    completed = Task.query.filter_by(user_id=user_id, status='Completed', deleted=False).count()
    completion_pct = int((completed / total) * 100) if total else 0

    categories = [c[0] for c in db.session.query(Task.category).filter(Task.user_id == user_id, Task.deleted==False).distinct().all() if c[0]]

    return render_template('index.html', tasks=tasks, pagination=pagination, q=q, categories=categories, completion_pct=completion_pct)

@app.route('/task/new', methods=['GET', 'POST'])
@login_required
def create_task():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category = request.form.get('category', '').strip() or None
        priority = request.form.get('priority', 'Medium')
        due_date_raw = request.form.get('due_date', '').strip()
        due_date = None
        if due_date_raw:
            try:
                due_date = datetime.strptime(due_date_raw, '%Y-%m-%d').date()
            except Exception:
                flash('Invalid due date', 'danger')
                return redirect(url_for('create_task'))

        # handle file
        file = request.files.get('attachment')
        filename = None
        if file and file.filename:
            if allowed_file(file.filename):
                fn = secure_filename(file.filename)
                fn = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{fn}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                filename = fn
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('create_task'))

        t = Task(title=title, description=description or None, category=category,
                 priority=priority, due_date=due_date, attachment=filename, user_id=session['user_id'])
        db.session.add(t)
        db.session.commit()

        # notification + email
        n = Notification(title='Task created', message=f'Task "{t.title}" created.', user_id=session['user_id'])
        db.session.add(n)
        db.session.commit()
        user = User.query.get(session['user_id'])
        send_email('Task created', user.email, f'Your task "{t.title}" was created. Due: {t.due_date or "N/A"}')

        add_log(user.email, f'Created task "{t.title}"')
        flash('Task created', 'success')
        return redirect(url_for('index'))

    return render_template('create_edit.html', task=None, form_action=url_for('create_task'))

@app.route('/task/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_task(id):
    t = Task.query.filter_by(id=id, user_id=session['user_id'], deleted=False).first_or_404()
    if request.method == 'POST':
        t.title = request.form.get('title', t.title).strip()
        t.description = request.form.get('description', t.description).strip()
        t.category = request.form.get('category', t.category) or None
        t.priority = request.form.get('priority', t.priority)
        t.status = request.form.get('status', t.status)
        dd = request.form.get('due_date', '')
        t.due_date = datetime.strptime(dd, '%Y-%m-%d').date() if dd else None

        # attachment
        file = request.files.get('attachment')
        if file and file.filename:
            if allowed_file(file.filename):
                fn = secure_filename(file.filename)
                fn = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{fn}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
                t.attachment = fn
            else:
                flash('File type not allowed', 'danger')
                return redirect(url_for('edit_task', id=id))

        db.session.commit()
        add_log(User.query.get(session['user_id']).email, f'Edited task "{t.title}"')
        flash('Task updated', 'success')
        return redirect(url_for('index'))

    return render_template('create_edit.html', task=t, form_action=url_for('edit_task', id=id))

@app.route('/task/<int:id>/delete', methods=['POST'])
@login_required
def delete_task(id):
    t = Task.query.filter_by(id=id, user_id=session['user_id'], deleted=False).first_or_404()
    t.deleted = True
    db.session.commit()
    add_log(User.query.get(session['user_id']).email, f'Deleted task "{t.title}"')
    flash('Task deleted', 'warning')
    return redirect(url_for('index'))

@app.route('/attachment/<filename>')
@login_required
def attachment(filename):
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if os.path.exists(path):
        return send_file(path)
    flash('Attachment not found', 'danger')
    return redirect(url_for('index'))

# -------------------------
# Inquiries (customer messages)
# -------------------------
@app.route('/inquiry', methods=['GET', 'POST'])
@login_required
def inquiry():
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        message = request.form.get('message', '').strip()
        if not subject or not message:
            flash('Subject and message are required', 'danger')
            return redirect(url_for('inquiry'))
        iq = Inquiry(subject=subject, message=message, user_id=session['user_id'])
        db.session.add(iq)
        db.session.commit()
        add_log(User.query.get(session['user_id']).email, 'Sent inquiry')
        send_email('Inquiry received', User.query.get(session['user_id']).email,
                   'Thank you — we received your inquiry and will respond soon.')
        flash('Inquiry sent', 'success')
        return redirect(url_for('index'))

    my_inquiries = Inquiry.query.filter_by(user_id=session['user_id']).order_by(Inquiry.created_at.desc()).all()
    return render_template('inquiry.html', inquiries=my_inquiries)

# -------------------------
# Admin: list & reply inquiries
# -------------------------
@app.route('/admin/inquiries', methods=['GET', 'POST'])
@admin_required
def admin_inquiries():
    if request.method == 'POST':
        inquiry_id = request.form.get('inquiry_id')
        reply_text = request.form.get('reply', '').strip()
        iq = Inquiry.query.get_or_404(inquiry_id)
        iq.reply = reply_text
        iq.replied = True
        db.session.commit()
        # send reply email
        if iq.user and iq.user.email:
            send_email('Reply to your inquiry', iq.user.email, reply_text)
        add_log(User.query.get(session['user_id']).email, f'Replied to inquiry {iq.id}')
        flash('Reply sent', 'success')
        return redirect(url_for('admin_inquiries'))

    inquiries = Inquiry.query.order_by(Inquiry.created_at.desc()).all()
    return render_template('admin_inquiries.html', inquiries=inquiries)

# -------------------------
# Notifications
# -------------------------
@app.route('/notifications')
@login_required
def notifications():
    items = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=items)

@app.route('/notifications/mark_read/<int:id>', methods=['POST'])
@login_required
def mark_read(id):
    n = Notification.query.get_or_404(id)
    if n.user_id != session['user_id']:
        flash('Forbidden', 'danger')
        return redirect(url_for('notifications'))
    n.read = True
    db.session.commit()
    return redirect(url_for('notifications'))

# -------------------------
# Export to Excel and PDF
# -------------------------
@app.route('/export/excel')
@login_required
def export_excel():
    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id, deleted=False).all()
    rows = []
    for t in tasks:
        rows.append({
            'Title': t.title,
            'Description': t.description or '',
            'Category': t.category or '',
            'Priority': t.priority,
            'Status': t.status,
            'Due Date': t.due_date.isoformat() if t.due_date else ''
        })
    df = pd.DataFrame(rows)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Tasks')
    output.seek(0)
    add_log(User.query.get(session['user_id']).email, 'Exported tasks to Excel')
    return send_file(output, download_name='tasks.xlsx', as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/export/pdf')
@login_required
def export_pdf():
    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id, deleted=False).all()
    buf = io.BytesIO()
    p = canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - 50
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, f"Tasks for {User.query.get(user_id).fullname}")
    y -= 30
    p.setFont("Helvetica", 10)
    for t in tasks:
        line = f"- {t.title} | {t.priority} | {t.status} | Due: {t.due_date or 'N/A'}"
        p.drawString(50, y, line)
        y -= 14
        if y < 50:
            p.showPage()
            y = height - 50
    p.save()
    buf.seek(0)
    add_log(User.query.get(session['user_id']).email, 'Exported tasks to PDF')
    return send_file(buf, download_name='tasks.pdf', as_attachment=True, mimetype='application/pdf')

# -------------------------
# Admin dashboard
# -------------------------
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users = User.query.count()
    total_tasks = Task.query.count()
    pending_inq = Inquiry.query.filter_by(replied=False).count()
    users = User.query.order_by(User.created_at.desc()).all()
    tasks = Task.query.order_by(Task.created_at.desc()).limit(200).all()
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).limit(100).all()
    return render_template('admin_dashboard.html',
                           total_users=total_users, total_tasks=total_tasks, pending_inquiries=pending_inq,
                           users=users, tasks=tasks, logs=logs)

# -------------------------
# Calendar view
# -------------------------
@app.route('/calendar')
@login_required
def calendar_view():
    user_id = session['user_id']
    tasks = Task.query.filter_by(user_id=user_id, deleted=False, archived=False).all()
    events = []
    for t in tasks:
        if t.due_date:
            events.append({
                'id': t.id,
                'title': t.title,
                'start': t.due_date.isoformat(),
                'url': url_for('edit_task', id=t.id),
                'color': '#198754' if t.status == 'Completed' else ('#dc3545' if t.due_date < date.today() else '#0d6efd')
            })
    return render_template('calendar.html', events=events)

# -------------------------
# Scheduler jobs: daily reminders and auto-archive
# -------------------------
def send_daily_reminders():
    today = date.today()
    tasks = Task.query.filter(Task.due_date == today, Task.deleted==False, Task.archived==False).all()
    for t in tasks:
        u = t.user
        if not u:
            continue
        msg = f'Reminder: Your task "{t.title}" is due today.'
        n = Notification(user_id=u.id, title='Task due today', message=msg)
        db.session.add(n)
        send_email('Task due today', u.email, msg)
        add_log('system', f'Sent reminder for task {t.id}')
    db.session.commit()

def auto_archive_tasks():
    cutoff = datetime.utcnow() - timedelta(days=30)
    tasks = Task.query.filter(Task.status=='Completed', Task.updated_at < cutoff, Task.archived==False).all()
    for t in tasks:
        t.archived = True
        if t.attachment:
            src = os.path.join(app.config['UPLOAD_FOLDER'], t.attachment)
            if os.path.exists(src):
                dst = os.path.join(ARCHIVE_FOLDER, t.attachment)
                try:
                    os.replace(src, dst)
                except Exception:
                    pass
        add_log('system', f'Archived task {t.id}')
    db.session.commit()

# Schedule (if not already scheduled)
try:
    scheduler.add_job(send_daily_reminders, 'cron', hour=8, id='daily_reminders', replace_existing=True)
    scheduler.add_job(auto_archive_tasks, 'interval', days=1, id='auto_archive', replace_existing=True)
except Exception as e:
    print('Scheduler setup error (may be already added):', e)

# -------------------------
# Theme toggle
# -------------------------
@app.route('/toggle_theme')
@login_required
def toggle_theme():
    current = request.cookies.get('theme', 'light')
    new = 'dark' if current == 'light' else 'light'
    resp = make_response(redirect(request.referrer or url_for('index')))
    resp.set_cookie('theme', new, max_age=60*60*24*365)
    return resp

# -------------------------
# Logs (user)
# -------------------------
@app.route('/logs')
@login_required
def logs():
    username = User.query.get(session['user_id']).email
    items = ActivityLog.query.filter(ActivityLog.actor == username).order_by(ActivityLog.timestamp.desc()).limit(200).all()
    return render_template('logs.html', logs=items)

# -------------------------
# Utility: run
# -------------------------
if __name__ == '__main__':
    # ensure upload/archive dirs
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(ARCHIVE_FOLDER, exist_ok=True)
    app.run(debug=True, host='127.0.0.1', port=5000)
