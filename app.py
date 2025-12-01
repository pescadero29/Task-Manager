import os
import random
import string
from datetime import datetime, timedelta

from flask import (Flask, flash, g, jsonify, redirect, render_template, request,
                   session, url_for)
from werkzeug.utils import secure_filename
import os
from flask_sqlalchemy import SQLAlchemy
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer
from smtplib import SMTP
from email.message import EmailMessage

# Load config
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///taskmanager.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Mail config
MAIL_SERVER = os.getenv('MAIL_SERVER')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

# Upload config
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Serializer for tokens (if needed)
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# --- Database models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False)
    name = db.Column(db.String(150))
    password_hash = db.Column(db.String(200), nullable=True)  # optional if OTP-only
    is_facilitator = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(10), nullable=True)
    otp_expiry = db.Column(db.DateTime, nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_picture = db.Column(db.String(200), nullable=True)  # filename of uploaded profile picture
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    assignee = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    priority = db.Column(db.String(20), default='Medium')  # Low/Medium/High
    tags = db.Column(db.String(200), default='')
    due_date = db.Column(db.DateTime, nullable=True)
    estimate_hours = db.Column(db.Float, default=1.0)
    completed = db.Column(db.Boolean, default=False)
    recurrence = db.Column(db.String(20), nullable=True)  # 'daily','weekly','monthly' or None
    reminder_sent = db.Column(db.Boolean, default=False)  # Legacy field
    reminder_sent_1day = db.Column(db.Boolean, default=False)
    reminder_sent_1hr = db.Column(db.Boolean, default=False)
    reminder_sent_30min = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    created_by_user = db.relationship('User', foreign_keys=[created_by], backref='created_tasks')
    assignee_user = db.relationship('User', foreign_keys=[assignee], backref='assigned_tasks')

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_email = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    auto_responded = db.Column(db.Boolean, default=False)
    facilitator_reply = db.Column(db.Text, nullable=True)
    facilitator_reply_at = db.Column(db.DateTime, nullable=True)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # admin or user performing action
    action = db.Column(db.String(200), nullable=False)  # e.g., 'user_login', 'task_created', 'admin_edit_user'
    details = db.Column(db.Text, nullable=True)  # additional info
    ip_address = db.Column(db.String(45), nullable=True)  # IPv4/IPv6
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- Helpers ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def send_email(to_email, subject, body):
    """Simple SMTP email sender; replace with robust lib in production."""
    if not MAIL_SERVER or not MAIL_USERNAME or not MAIL_PASSWORD:
        app.logger.warning("Email not sent: SMTP is not configured.")
        return False
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = MAIL_DEFAULT_SENDER
    msg['To'] = to_email
    msg.set_content(body)
    try:
        with SMTP(MAIL_SERVER, MAIL_PORT) as smtp:
            if MAIL_USE_TLS:
                smtp.starttls()
            smtp.login(MAIL_USERNAME, MAIL_PASSWORD)
            smtp.send_message(msg)
        app.logger.info(f"Email sent to {to_email} subject={subject}")
        return True
    except Exception as e:
        app.logger.exception("Failed sending email")
        return False

def generate_otp(n=6):
    return ''.join(random.choices(string.digits, k=n))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def log_action(user_id, action, details=None, ip_address=None):
    """Log an action to the database."""
    log = Log(user_id=user_id, action=action, details=details, ip_address=ip_address or request.remote_addr)
    db.session.add(log)
    db.session.commit()

# --- Routes ---
@app.before_request
def attach_user_metrics():
    g.metrics = {}
    if current_user.is_authenticated:
        # Get user's tasks
        tasks = Task.query.filter((Task.created_by == current_user.id) | (Task.assignee == current_user.id)).all()

        # Basic metrics
        total = len(tasks)
        completed = sum(1 for t in tasks if t.completed)
        pending = total - completed
        overdue = sum(1 for t in tasks if t.due_date and t.due_date.date() < datetime.utcnow().date() and not t.completed)
        due_today = sum(1 for t in tasks if t.due_date and t.due_date.date() == datetime.utcnow().date() and not t.completed)
        due_this_week = sum(1 for t in tasks if t.due_date and t.due_date.date() <= (datetime.utcnow() + timedelta(days=7)).date() and t.due_date.date() >= datetime.utcnow().date() and not t.completed)

        # Priority breakdown
        high_priority = sum(1 for t in tasks if t.priority == 'High')
        medium_priority = sum(1 for t in tasks if t.priority == 'Medium')
        low_priority = sum(1 for t in tasks if t.priority == 'Low')

        # Category breakdown (from tags)
        categories = {}
        for task in tasks:
            if task.tags:
                for tag in task.tags.split(','):
                    tag = tag.strip().lower()
                    categories[tag] = categories.get(tag, 0) + 1

        # Weekly progress (last 7 days)
        weekly_data = []
        for i in range(6, -1, -1):
            date = datetime.utcnow().date() - timedelta(days=i)
            completed_on_date = sum(1 for t in tasks if t.completed and t.created_at.date() <= date)
            weekly_data.append(completed_on_date)

        # Completion rate over time
        completion_rate = (completed/total*100) if total else 0

        # Estimated hours
        total_est_hours = sum(t.estimate_hours or 0 for t in tasks)
        completed_est_hours = sum(t.estimate_hours or 0 for t in tasks if t.completed)

        g.metrics = {
            'total_tasks': total,
            'completed_tasks': completed,
            'pending_tasks': pending,
            'overdue_tasks': overdue,
            'due_today': due_today,
            'due_this_week': due_this_week,
            'completion_rate': completion_rate,
            'high_priority': high_priority,
            'medium_priority': medium_priority,
            'low_priority': low_priority,
            'categories': categories,
            'weekly_progress': weekly_data,
            'total_est_hours': total_est_hours,
            'completed_est_hours': completed_est_hours
        }

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

# Registration (simple)
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        name = request.form.get('name','').strip()
        if not email or '@' not in email:
            flash("Provide a valid email", 'danger')
            return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash("Email already registered", 'warning')
            return redirect(url_for('register'))
        user = User(email=email, name=name)
        db.session.add(user)
        db.session.commit()
        flash("Registered. Please login using OTP sent to your email.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

# Login: send OTP to email
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email','').strip().lower()
        if not email or '@' not in email:
            flash("Please provide a valid email.", 'danger')
            return redirect(url_for('login'))
        user = User.query.filter_by(email=email).first()
        if not user:
            flash("Email not registered. Please register first.", 'warning')
            return redirect(url_for('register'))
        otp = generate_otp()
        user.otp = otp
        user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
        db.session.commit()
        # send OTP email
        send_email(user.email, "Your TaskManager OTP", f"Hello {user.name or 'User'},\n\nYour OTP is: {otp}\nIt expires in 10 minutes.")
        session['pending_user'] = user.id
        flash("OTP sent to your email. Enter it below.", 'info')
        return redirect(url_for('verify_otp'))
    return render_template('login.html')

@app.route('/verify-otp', methods=['GET','POST'])
def verify_otp():
    user_id = session.get('pending_user')
    if not user_id:
        flash("No OTP request found. Start login again.", 'warning')
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if request.method == 'POST':
        otp = request.form.get('otp','').strip()
        if not user or not user.otp:
            flash("OTP invalid. Try again.", 'danger')
            return redirect(url_for('login'))
        if datetime.utcnow() > (user.otp_expiry or datetime.utcnow()):
            flash("OTP expired. Request a new one.", 'danger')
            return redirect(url_for('login'))
        if otp != user.otp:
            flash("Incorrect OTP.", 'danger')
            return redirect(url_for('verify_otp'))
        # success
        user.otp = None
        user.otp_expiry = None
        user.last_login = datetime.utcnow()
        db.session.commit()
        login_user(user)
        session.pop('pending_user', None)
        log_action(user.id, 'user_login', f'User {user.email} logged in')
        flash("Logged in!", 'success')
        return redirect(url_for('dashboard'))
    return render_template('verify_otp.html', email=user.email)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out.", 'info')
    return redirect(url_for('index'))

# Dashboard with computations
@app.route('/dashboard')
@login_required
def dashboard():
    # show user's tasks and metrics
    tasks = Task.query.filter((Task.created_by == current_user.id) | (Task.assignee == current_user.id)).order_by(Task.due_date.asc().nulls_last()).all()
    return render_template('dashboard.html', tasks=tasks, metrics=g.metrics)

# Create task
@app.route('/task/new', methods=['GET','POST'])
@login_required
def create_task():
    if request.method == 'POST':
        # server-side validation
        title = request.form.get('title','').strip()
        if not title or len(title) < 3:
            flash("Title must be at least 3 characters.", 'danger')
            return redirect(url_for('create_task'))
        description = request.form.get('description','').strip()
        priority = request.form.get('priority','Medium')
        tags = request.form.get('tags','').strip()
        due_date_raw = request.form.get('due_date','').strip()
        estimate = request.form.get('estimate_hours','1')
        recurrence = request.form.get('recurrence') or None

        due_date = None
        if due_date_raw:
            try:
                due_date = datetime.fromisoformat(due_date_raw)
                # Validate due_date is not in the past (allow current or future)
                if due_date < datetime.utcnow():
                    flash("Due date cannot be in the past.", "danger")
                    return redirect(url_for('create_task'))
            except ValueError:
                flash("Invalid due date format.", 'danger')
                return redirect(url_for('create_task'))
        try:
            estimate_f = float(estimate)
            if estimate_f <= 0:
                raise ValueError()
        except ValueError:
            flash("Estimate hours must be a positive number.", "danger")
            return redirect(url_for('create_task'))

        task = Task(title=title, description=description, created_by=current_user.id,
                    priority=priority, tags=tags, due_date=due_date, estimate_hours=estimate_f,
                    recurrence=recurrence)
        db.session.add(task)
        db.session.commit()
        flash("Task created.", "success")
        return redirect(url_for('dashboard'))
    # GET
    users = User.query.all()
    return render_template('create_task.html', users=users)

# Edit task
@app.route('/task/<int:task_id>/edit', methods=['GET','POST'])
@login_required
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    # only creator or facilitator can edit
    if task.created_by != current_user.id and not current_user.is_facilitator:
        flash("No permission to edit this task.", 'danger')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title','').strip()
        if not title:
            flash("Title required.", 'danger')
            return redirect(url_for('edit_task', task_id=task.id))
        task.title = title
        task.description = request.form.get('description','').strip()
        task.priority = request.form.get('priority','Medium')
        task.tags = request.form.get('tags','').strip()
        due = request.form.get('due_date','').strip()
        task.due_date = datetime.fromisoformat(due) if due else None
        try:
            task.estimate_hours = float(request.form.get('estimate_hours',1.0))
        except:
            task.estimate_hours = 1.0
        task.recurrence = request.form.get('recurrence') or None
        task.completed = (request.form.get('completed') == 'on')
        assignee = request.form.get('assignee')
        task.assignee = int(assignee) if assignee else None
        db.session.commit()
        flash("Task updated.", "success")
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('edit_task.html', task=task, users=users)

# Delete
@app.route('/task/<int:task_id>/delete', methods=['POST'])
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.created_by != current_user.id and not current_user.is_facilitator:
        flash("No permission to delete.", 'danger')
        return redirect(url_for('dashboard'))
    db.session.delete(task)
    db.session.commit()
    flash("Task deleted.", "info")
    return redirect(url_for('dashboard'))

# Quick toggle complete (AJAX)
@app.route('/task/<int:task_id>/toggle_complete', methods=['POST'])
@login_required
def toggle_complete(task_id):
    task = Task.query.get_or_404(task_id)

    if task.created_by != current_user.id and task.assignee != current_user.id and not current_user.is_facilitator:
        flash("No permission to modify this task.", "danger")
        return redirect(url_for('dashboard'))

    # Toggle completion
    task.completed = not task.completed
    db.session.commit()

    # Proper flash messages
    if task.completed:
        flash("Task marked as completed!", "success")
    else:
        flash("Task marked as incomplete.", "info")

    # Redirect back so no JSON appears
    return redirect(url_for('dashboard'))


# Inquiry (customer) - public endpoint to send inquiry (with validation & auto-response)
@app.route('/inquiry/new', methods=['GET','POST'])
def new_inquiry():
    if request.method == 'POST':
        sender = request.form.get('email','').strip()
        subject = request.form.get('subject','').strip()
        message = request.form.get('message','').strip()
        if not sender or '@' not in sender:
            flash("Enter a valid email.", 'danger')
            return redirect(url_for('new_inquiry'))
        if not message or len(message) < 5:
            flash("Message must be at least 5 characters.", 'danger')
            return redirect(url_for('new_inquiry'))
        inquiry = Inquiry(sender_email=sender, subject=subject, message=message)
        db.session.add(inquiry)
        db.session.commit()

        # Send inquiry email to the fixed admin email
        send_email("zurielpescadero123@gmail.com", subject or "No Subject", message)

        confirm_body = f"Hi,\n\nThanks for your inquiry about '{subject or 'general'}'.\nOur team will look into it and respond soon.\n\n-- TaskManager Bot"

        if current_user.is_authenticated and current_user.email != "zurielpescadero123@gmail.com":
            if current_user.email.lower() == sender.lower():
                # If sender email matches logged-in user, send one confirmation email only
                send_email(sender, "Inquiry Confirmation", confirm_body)
            else:
                # Send confirmation to logged-in user
                send_email(current_user.email, "Inquiry Confirmation", confirm_body)
                # Auto-response to sender
                send_email(sender, f"Re: {subject or 'Your inquiry'}", confirm_body)
        else:
            # Not logged in - send auto-response only to sender
            send_email(sender, f"Re: {subject or 'Your inquiry'}", confirm_body)

        inquiry.auto_responded = True
        db.session.commit()
        flash("Inquiry received — an auto-response was sent.", "success")
        return redirect(url_for('index'))

    return render_template('new_inquiry.html')

# Facilitator inbox (view inquiries) + reply
@app.route('/inbox')
@login_required
def inbox():
    if not current_user.is_facilitator:
        flash("Inbox accessible to facilitators only.", 'danger')
        return redirect(url_for('dashboard'))
    inquiries = Inquiry.query.order_by(Inquiry.created_at.desc()).all()
    return render_template('inbox.html', inquiries=inquiries)

@app.route('/inquiry/<int:id>/reply', methods=['POST'])
@login_required
def reply_inquiry(id):
    if not current_user.is_facilitator:
        return redirect(url_for('dashboard'))
    inquiry = Inquiry.query.get_or_404(id)
    reply = request.form.get('reply','').strip()
    if not reply:
        flash("Reply cannot be empty.", 'danger')
        return redirect(url_for('inbox'))
    send_email(inquiry.sender_email, f"RE: {inquiry.subject or 'Your inquiry'}", reply)
    inquiry.facilitator_reply = reply
    inquiry.facilitator_reply_at = datetime.utcnow()
    db.session.commit()
    flash("Reply sent to the customer.", "success")
    return redirect(url_for('inbox'))

# API: simple tasks JSON for mobile apps
@app.route('/api/tasks')
@login_required
def api_tasks():
    tasks = Task.query.filter((Task.created_by == current_user.id) | (Task.assignee == current_user.id)).all()
    data = []
    for t in tasks:
        data.append({
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'due_date': t.due_date.isoformat() if t.due_date else None,
            'priority': t.priority,
            'estimate_hours': t.estimate_hours,
            'completed': t.completed
        })
    return jsonify(data)

# API: notifications
@app.route('/api/notifications')
@login_required
def api_notifications():
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).all()
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat()
        })
    return jsonify(data)

@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

# Calendar view
@app.route('/calendar')
@login_required
def calendar():
    return render_template('calendar.html')

# Profile view
@app.route('/profile')
@login_required
def profile():
    # Get user's tasks and metrics for profile display
    tasks = Task.query.filter((Task.created_by == current_user.id) | (Task.assignee == current_user.id)).order_by(Task.due_date.asc().nulls_last()).all()
    return render_template('profile.html', tasks=tasks, metrics=g.metrics)

# Profile picture upload
@app.route('/profile/upload', methods=['POST'])
@login_required
def upload_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('profile'))
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file', 'danger')
        return redirect(url_for('profile'))
    if file and allowed_file(file.filename):
        filename = secure_filename(f"{current_user.id}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(file_path)
        current_user.profile_picture = filename
        db.session.commit()
        flash('Profile picture updated successfully!', 'success')
    else:
        flash('Invalid file type. Please upload PNG, JPG, JPEG, or GIF.', 'danger')
    return redirect(url_for('profile'))

# --- Admin Routes ---
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        flash("Admin access required.", 'danger')
        return redirect(url_for('dashboard'))
    # Get overall system metrics
    total_users = User.query.count()
    total_tasks = Task.query.count()
    total_inquiries = Inquiry.query.count()
    recent_logs = Log.query.order_by(Log.created_at.desc()).limit(10).all()
    return render_template('admin_dashboard.html', total_users=total_users, total_tasks=total_tasks, total_inquiries=total_inquiries, recent_logs=recent_logs)

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        flash("Admin access required.", 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/tasks')
@login_required
def admin_tasks():
    if not current_user.is_admin:
        flash("Admin access required.", 'danger')
        return redirect(url_for('dashboard'))
    tasks = Task.query.options(db.joinedload(Task.created_by_user), db.joinedload(Task.assignee_user)).all()
    return render_template('admin_tasks.html', tasks=tasks)

@app.route('/admin/logs')
@login_required
def admin_logs():
    if not current_user.is_admin:
        flash("Admin access required.", 'danger')
        return redirect(url_for('dashboard'))
    logs = Log.query.order_by(Log.created_at.desc()).all()
    return render_template('admin_logs.html', logs=logs)

@app.route('/admin/manage_user/<int:user_id>', methods=['GET','POST'])
@login_required
def manage_user(user_id):
    if not current_user.is_admin:
        flash("Admin access required.", 'danger')
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.name = request.form.get('name', user.name)
        user.email = request.form.get('email', user.email)
        user.is_facilitator = (request.form.get('is_facilitator') == 'on')
        user.is_admin = (request.form.get('is_admin') == 'on')
        db.session.commit()
        log_action(current_user.id, 'admin_edit_user', f'Edited user {user.email}')
        flash("User updated.", "success")
        return redirect(url_for('admin_users'))
    return render_template('admin_manage_user.html', user=user)

# --- Background jobs (automations) ---
def send_due_reminders():
    """Send reminders at multiple intervals: 1 day, 1 hour, 30 minutes before due date."""
    now = datetime.utcnow()

    # 1 day reminder
    tomorrow = now.date() + timedelta(days=1)
    tasks_1day = Task.query.filter(Task.due_date != None, Task.reminder_sent_1day == False).all()
    for t in tasks_1day:
        if t.due_date and t.due_date.date() == tomorrow and not t.completed:
            send_reminder(t, "1 day", now)

    # 1 hour reminder
    one_hour_later = now + timedelta(hours=1)
    tasks_1hr = Task.query.filter(Task.due_date != None, Task.reminder_sent_1hr == False).all()
    for t in tasks_1hr:
        if t.due_date and t.due_date <= one_hour_later and t.due_date > now and not t.completed:
            send_reminder(t, "1 hour", now)

    # 30 minutes reminder
    thirty_min_later = now + timedelta(minutes=30)
    tasks_30min = Task.query.filter(Task.due_date != None, Task.reminder_sent_30min == False).all()
    for t in tasks_30min:
        if t.due_date and t.due_date <= thirty_min_later and t.due_date > now and not t.completed:
            send_reminder(t, "30 minutes", now)

def send_reminder(task, time_frame, now):
    """Helper function to send reminder and create notification."""
    # Get recipients
    recipients = []
    if task.assignee:
        u = User.query.get(task.assignee)
        if u: recipients.append(u.email)
    creator = User.query.get(task.created_by)
    if creator and creator.email not in recipients:
        recipients.append(creator.email)

    # Send email
    body = f"Reminder: Task '{task.title}' is due in {time_frame}.\n\nDue: {task.due_date.strftime('%Y-%m-%d %H:%M')}\nDescription: {task.description or '-'}\nPriority: {task.priority}"
    subject = f"Task Reminder: {task.title} due in {time_frame}"

    for r in recipients:
        send_email(r, subject, body)

    # Create in-app notification
    for user_id in [task.assignee, task.created_by]:
        if user_id:
            notification = Notification(
                user_id=user_id,
                message=f"Task '{task.title}' is due in {time_frame} ({task.due_date.strftime('%b %d, %Y %H:%M')})"
            )
            db.session.add(notification)

    # Mark reminder as sent
    if time_frame == "1 day":
        task.reminder_sent_1day = True
    elif time_frame == "1 hour":
        task.reminder_sent_1hr = True
    elif time_frame == "30 minutes":
        task.reminder_sent_30min = True

    db.session.commit()

def daily_digest():
    """Send digest to facilitators summarizing tasks due today and inquiries."""
    facilitators = User.query.filter_by(is_facilitator=True).all()
    if not facilitators:
        return
    today = datetime.utcnow().date()
    tasks = Task.query.filter(Task.due_date != None).all()
    due_today = [t for t in tasks if t.due_date.date() == today]
    inquiries = Inquiry.query.filter(Inquiry.created_at >= datetime.utcnow() - timedelta(days=1)).all()
    if not due_today and not inquiries:
        return
    body = "Daily digest:\n\n"
    body += "Tasks due today:\n"
    for t in due_today:
        body += f"- {t.title} (due {t.due_date.isoformat()})\n"
    body += "\nRecent inquiries:\n"
    for iq in inquiries:
        body += f"- {iq.sender_email}: {iq.subject or '-'} at {iq.created_at.isoformat()}\n"
    for f in facilitators:
        send_email(f.email, "Daily Digest - TaskManager", body)

scheduler = BackgroundScheduler()
scheduler.add_job(func=send_due_reminders, trigger='interval', hours=6, id='reminders')
scheduler.add_job(func=daily_digest, trigger='cron', hour=0, id='digest')  # midnight UTC
scheduler.start()

# --- Command to init DB ---
@app.cli.command('initdb')
def initdb():
    db.create_all()
    print("DB created.")

if __name__ == '__main__':
    # Ensure DB exists
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
