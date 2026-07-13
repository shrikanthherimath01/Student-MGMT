"""
STUDENT MANAGEMENT SYSTEM - COMPLETE FIXED BACKEND (PRODUCTION READY)
All endpoints working, dropdowns fixed, attendance working, fast loading
"""
import re
import requests
import logging
import os
import csv
import io
import re
import secrets
import logging
import threading
from functools import wraps
from datetime import datetime, timedelta
import subprocess
import threading
import time
from flask import Flask, request, jsonify, render_template, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
import bcrypt
from dotenv import load_dotenv
from sqlalchemy import func, or_

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

load_dotenv()


# ============================================================
# APP CONFIGURATION
# ============================================================

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = os.getenv('SECRET_KEY', secrets.token_hex(32))

app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
    MAX_CONTENT_LENGTH=16 * 1024 * 1024
)

CORS(app, supports_credentials=True)

# WhatsApp Bridge Configuration
WHATSAPP_BRIDGE_URL = os.getenv('WHATSAPP_BRIDGE_URL', 'http://localhost:3001')
WHATSAPP_ENABLED = os.getenv('WHATSAPP_ENABLED', 'true').lower() == 'true'

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', '')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_NAME = os.getenv('DB_NAME', 'sms_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# ============================================================
# LOGIN MANAGER
# ============================================================

login_manager = LoginManager(app)
login_manager.login_view = 'login_page'

@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception as e:
        logger.error(f"Error loading user {user_id}: {str(e)}")
        return None

# ============================================================
# DATABASE MODELS
# ============================================================

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin', 'teacher', 'student'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Teacher(db.Model):
    __tablename__ = 'teachers'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    subject = db.Column(db.String(80))
    whatsapp_number = db.Column(db.String(20))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    parent_name = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    roll_number = db.Column(db.String(20))
    current_year = db.Column(db.Enum('1st', '2nd', '3rd', 'Completed'), default='1st')
    start_year = db.Column(db.Integer, nullable=False)
    end_year = db.Column(db.Integer)
    status = db.Column(db.Enum('active', 'archived', 'completed'), default='active')
    dob = db.Column(db.Date)
    address = db.Column(db.Text)
    sms_opt_out = db.Column(db.Boolean, default=False)
    whatsapp_opt_out = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('present', 'absent', 'late'), default='present')
    marked_by = db.Column(db.Integer)
    marked_by_type = db.Column(db.Enum('teacher', 'system'), default='teacher')
    remarks = db.Column(db.Text)
    whatsapp_sent = db.Column(db.Boolean, default=False)
    whatsapp_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Exam(db.Model):
    __tablename__ = 'exams'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    exam_date = db.Column(db.Date)
    max_marks = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id'), nullable=False)
    marks = db.Column(db.Numeric(5, 2), nullable=False)
    max_marks = db.Column(db.Numeric(5, 2), default=100)
    percentage = db.Column(db.Numeric(5, 2))
    grade = db.Column(db.String(5))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Leave(db.Model):
    __tablename__ = 'leaves'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.Enum('pending', 'approved', 'rejected'), default='pending')
    reviewed_by = db.Column(db.Integer)
    review_remarks = db.Column(db.Text)
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.Enum('absence', 'leave_update', 'result', 'general', 'whatsapp'), default='general')
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    related_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    __tablename__ = 'settings'
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class WhatsAppMessage(db.Model):
    __tablename__ = 'whatsapp_messages'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'))
    recipient_type = db.Column(db.Enum('student', 'parent', 'teacher'), default='parent')
    recipient_number = db.Column(db.String(20), nullable=False)
    recipient_name = db.Column(db.String(100))
    message = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.Enum('attendance', 'progress', 'general', 'bulk', 'absence_alert'), default='general')
    status = db.Column(db.Enum('pending', 'sent', 'failed', 'delivered'), default='pending')
    error_message = db.Column(db.Text)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============================================================
# WHATSAPP HELPER FUNCTIONS
# ============================================================

def send_whatsapp_message(phone_number, message, recipient_name="", recipient_type="parent", student_id=None, message_type="general"):
    """Send WhatsApp message via bridge and return (success, message_id)"""
    if not WHATSAPP_ENABLED:
        logger.info(f"WhatsApp disabled, would send to {phone_number}")
        return True, "disabled"
    
    if not phone_number:
        logger.error(f"No phone number provided")
        return False, "No phone number"
    
    try:
        # Clean and format phone number
        phone_number = re.sub(r'\D', '', str(phone_number))
        if len(phone_number) == 10:
            phone_number = '91' + phone_number
        elif len(phone_number) == 12 and phone_number.startswith('91'):
            pass
        else:
            logger.error(f"Invalid phone number format: {phone_number}")
            return False, "Invalid phone number"
        
        # Send to WhatsApp bridge
        response = requests.post(
            f"{WHATSAPP_BRIDGE_URL}/send",
            json={'to': phone_number, 'message': message},
            timeout=10
        )
        
        logger.info(f"WhatsApp API response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                message_id = result.get('messageId', str(int(datetime.utcnow().timestamp())))
                
                # Save to database
                whatsapp_msg = WhatsAppMessage(
                    student_id=student_id,
                    recipient_type=recipient_type,
                    recipient_number=phone_number,
                    recipient_name=recipient_name,
                    message=message,
                    message_type=message_type,
                    status='sent',
                    sent_at=datetime.utcnow()
                )
                db.session.add(whatsapp_msg)
                db.session.commit()
                
                logger.info(f"WhatsApp message sent successfully to {phone_number}")
                return True, message_id
            else:
                logger.error(f"WhatsApp bridge error: {result}")
                return False, str(result)
        else:
            logger.error(f"WhatsApp bridge HTTP error: {response.status_code}")
            return False, f"HTTP {response.status_code}"
            
    except requests.exceptions.ConnectionError:
        logger.error(f"Cannot connect to WhatsApp bridge at {WHATSAPP_BRIDGE_URL}")
        return False, "Bridge not reachable"
    except Exception as e:
        logger.error(f"WhatsApp send error: {str(e)}")
        return False, str(e)

def send_absence_alert(student, attendance_record):
    """Send REAL WhatsApp to BOTH student and parent when absent"""
    try:
        absence_date = attendance_record.date.strftime("%d/%m/%Y") if hasattr(attendance_record.date, 'strftime') else str(attendance_record.date)
        
        # Message for PARENT
        parent_msg = f"""📚 *ABSENCE ALERT*

Dear Parent/Guardian of {student.name},

Your ward has been marked ABSENT on {absence_date}.

Student: {student.name} ({student.student_id})
Date: {absence_date}

Please ensure regular attendance for academic success.

- School System"""

        # Message for STUDENT
        student_msg = f"""📚 *ABSENCE ALERT*

Dear {student.name},

You have been marked ABSENT on {absence_date}.

Student ID: {student.student_id}
Date: {absence_date}

Please attend classes regularly.

- School System"""

        sent_count = 0
        
        # Send to PARENT
        if student.parent_phone:
            clean_phone = re.sub(r'\D', '', str(student.parent_phone))
            if len(clean_phone) == 10:
                clean_phone = '91' + clean_phone
            elif len(clean_phone) == 12 and clean_phone.startswith('91'):
                pass
            else:
                print(f"⚠️ Invalid parent phone format for {student.name}: {clean_phone}")
            
            try:
                response = requests.post(
                    f"{WHATSAPP_BRIDGE_URL}/send",
                    json={'to': clean_phone, 'message': parent_msg},
                    timeout=30
                )
                if response.status_code == 200 and response.json().get('success'):
                    sent_count += 1
                    # Save to database
                    whatsapp_msg = WhatsAppMessage(
                        student_id=student.id,
                        recipient_type='parent',
                        recipient_number=clean_phone,
                        recipient_name=f"Parent of {student.name}",
                        message=parent_msg,
                        message_type='absence_alert',
                        status='sent',
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(whatsapp_msg)
                    print(f"✅ Parent WhatsApp sent to {clean_phone} for {student.name}")
                else:
                    print(f"⚠️ Parent send failed for {student.name} - Status: {response.status_code}")
            except Exception as e:
                print(f"❌ Parent send error for {student.name}: {e}")
        
        # Send to STUDENT
        if student.phone:
            clean_phone = re.sub(r'\D', '', str(student.phone))
            if len(clean_phone) == 10:
                clean_phone = '91' + clean_phone
            elif len(clean_phone) == 12 and clean_phone.startswith('91'):
                pass
            else:
                print(f"⚠️ Invalid student phone format for {student.name}: {clean_phone}")
            
            try:
                response = requests.post(
                    f"{WHATSAPP_BRIDGE_URL}/send",
                    json={'to': clean_phone, 'message': student_msg},
                    timeout=30
                )
                if response.status_code == 200 and response.json().get('success'):
                    sent_count += 1
                    # Save to database
                    whatsapp_msg = WhatsAppMessage(
                        student_id=student.id,
                        recipient_type='student',
                        recipient_number=clean_phone,
                        recipient_name=student.name,
                        message=student_msg,
                        message_type='absence_alert',
                        status='sent',
                        sent_at=datetime.utcnow()
                    )
                    db.session.add(whatsapp_msg)
                    print(f"✅ Student WhatsApp sent to {clean_phone} for {student.name}")
                else:
                    print(f"⚠️ Student send failed for {student.name} - Status: {response.status_code}")
            except Exception as e:
                print(f"❌ Student send error for {student.name}: {e}")
        
        db.session.commit()
        
        # Update attendance record
        if sent_count > 0:
            attendance_record.whatsapp_sent = True
            attendance_record.whatsapp_sent_at = datetime.utcnow()
            db.session.commit()
            print(f"📊 Attendance record updated for {student.name} - {sent_count} messages sent")
            return True
        else:
            print(f"⚠️ No WhatsApp sent for {student.name} - no valid phone numbers")
            return False
        
    except Exception as e:
        print(f"❌ Error in send_absence_alert: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_whatsapp_bridge_status():
    """Check if WhatsApp bridge is running - FIXED VERSION"""
    if not WHATSAPP_ENABLED:
        return {'connected': False, 'enabled': False}
    try:
        print(f"🔍 Checking WhatsApp bridge at {WHATSAPP_BRIDGE_URL}/status")
        response = requests.get(f"{WHATSAPP_BRIDGE_URL}/status", timeout=3)
        print(f"📡 Response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Bridge data: connected={data.get('connected')}, has_qr={bool(data.get('qr'))}")
            return data
        return {'connected': False, 'qr': None}
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to WhatsApp bridge at {WHATSAPP_BRIDGE_URL}")
        return {'connected': False, 'qr': None}
    except Exception as e:
        print(f"❌ Error checking bridge: {str(e)}")
        return {'connected': False, 'qr': None}
# ============================================================
# HELPER FUNCTIONS
# ============================================================

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role not in roles:
                return jsonify({'error': 'Unauthorized access'}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# ============================================================
# FIXED: Generate Student ID in format: G-NTTF[CLASS_CODE][YEAR][SEQUENCE]
# Example: CP08 class, 2024 year = G-NTTF0824001
# Example: CP23 class, 2024 year = G-NTTF2324001
# ============================================================

def generate_student_id(class_id=None, start_year=None):
    """
    Generate Student ID: G-NTTF[CLASS_CODE][YEAR][SEQUENCE]
    
    Examples:
    - CP08 class, 2024: G-NTTF0824001, G-NTTF0824002
    - CP23 class, 2024: G-NTTF2324001, G-NTTF2324002
    - CP04 class, 2025: G-NTTF0425001
    """
    import re
    from sqlalchemy import func
    
    # Use start_year from form, or current year as fallback
    if start_year is None:
        start_year = datetime.now().year
    
    # Get year suffix (last 2 digits)
    year_suffix = f"{start_year % 100:02d}"
    
    # Default class code for students without class
    class_code = "00"
    
    # Get class code from class name if class_id is provided
    if class_id:
        class_obj = Class.query.get(class_id)
        if class_obj:
            # Extract numeric code from class name (CP08 -> 08, CP23 -> 23)
            match = re.search(r'CP(\d+)', class_obj.name.upper())
            if match:
                class_code = match.group(1).zfill(2)  # Ensure 2 digits
            else:
                # If no CP pattern, use first 2 chars
                class_code = class_obj.name[:2].zfill(2)
    
    # ============================================================
    # 🔴 THE MISSING PART - YOU NEED TO ADD THIS:
    # ============================================================
    
    # Build pattern for this class and year
    pattern = f"G-NTTF{class_code}{year_suffix}"
    
    # Find the highest sequence number for this pattern
    result = db.session.query(
        func.max(func.substring(Student.student_id, -3))
    ).filter(
        Student.student_id.like(f"{pattern}%")
    ).scalar()
    
    # Calculate next sequence number
    if result and result.isdigit():
        next_seq = int(result) + 1
    else:
        next_seq = 1
    
    # Generate student ID with 3-digit sequence
    student_id = f"{pattern}{next_seq:03d}"
    
    logger.info(f"✅ Generated student ID: {student_id}")
    
    return student_id

def calculate_grade(percentage):
    if percentage >= 90: return 'A+'
    elif percentage >= 80: return 'A'
    elif percentage >= 70: return 'B+'
    elif percentage >= 60: return 'B'
    elif percentage >= 50: return 'C'
    elif percentage >= 40: return 'D'
    else: return 'F'

def create_notification(user_id, notif_type, message, related_id=None):
    try:
        notif = Notification(user_id=user_id, type=notif_type, message=message, related_id=related_id)
        db.session.add(notif)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Notification error: {e}")

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = request.headers.get('Origin', '*')
    response.headers['Access-Control-Allow-Credentials'] = 'true'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response

# ============================================================
# PAGE ROUTES
# ============================================================

@app.route('/api/whatsapp/connection-status', methods=['GET'])
@login_required
@role_required('admin')
def whatsapp_connection_status():
    """Get WhatsApp connection status for admin dashboard"""
    try:
        response = requests.get('http://localhost:3001/status', timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'connected': False})
    except:
        return jsonify({'connected': False})

@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/dashboard/admin')
@login_required
@role_required('admin')
def admin_dashboard():
    return render_template('admin.html')

@app.route('/dashboard/teacher')
@login_required
@role_required('teacher')
def teacher_dashboard():
    return render_template('teacher.html')

@app.route('/dashboard/student')
@login_required
@role_required('student')
def student_dashboard():
    return render_template('student.html')

# ============================================================
# AUTHENTICATION API
# ============================================================

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    try:
        data = request.get_json()
        email = (data.get('email') or '').strip().lower()
        password = (data.get('password') or '').strip()
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        user = User.query.filter_by(email=email).first()
        if not user or not verify_password(password, user.password):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account disabled'}), 403
        
        login_user(user)
        
        response = {'message': 'Login successful', 'role': user.role, 'id': user.id}
        
        if user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=user.id).first()
            if teacher:
                response['name'] = teacher.name
                response['class_id'] = teacher.class_id
                response['subject'] = teacher.subject
                response['whatsapp_number'] = teacher.whatsapp_number
        elif user.role == 'student':
            student = Student.query.filter_by(user_id=user.id).first()
            if student:
                response['name'] = student.name
                response['student_id'] = student.student_id
                response['class_id'] = student.class_id
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def api_logout():
    logout_user()
    return jsonify({'message': 'Logged out'})

@app.route('/api/auth/me')
@login_required
def api_me():
    try:
        user = current_user
        response = {'id': user.id, 'email': user.email, 'role': user.role}
        
        if user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=user.id).first()
            if teacher:
                response.update({
                    'name': teacher.name,
                    'subject': teacher.subject,
                    'class_id': teacher.class_id,
                    'db_id': teacher.id,
                    'whatsapp_number': teacher.whatsapp_number,
                    'phone': teacher.phone
                })
                if teacher.class_id:
                    class_obj = Class.query.get(teacher.class_id)
                    if class_obj:
                        response['class_name'] = f"{class_obj.name}-{class_obj.section}"
        elif user.role == 'student':
            student = Student.query.filter_by(user_id=user.id).first()
            if student:
                class_obj = Class.query.get(student.class_id)
                response.update({
                    'name': student.name,
                    'student_id': student.student_id,
                    'class_id': student.class_id,
                    'db_id': student.id,
                    'sms_opt_out': student.sms_opt_out,
                    'whatsapp_opt_out': student.whatsapp_opt_out,
                    'phone': student.phone,
                    'parent_phone': student.parent_phone,
                    'parent_name': student.parent_name,
                    'current_year': student.current_year,
                    'start_year': student.start_year,
                    'address': student.address,
                    'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else 'Not Assigned',
                    'status': student.status
                })
        elif user.role == 'admin':
            response['name'] = 'Administrator'
            response['db_id'] = user.id
        
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error in /api/auth/me: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# STUDENT API (FAST WITH PAGINATION)
# ============================================================

@app.route('/api/students', methods=['GET'])
@login_required
def get_students():
    try:
        status_filter = request.args.get('status', 'active')
        class_filter = request.args.get('class_id')
        search = request.args.get('search', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = Student.query
        
        # FIX: For teacher role - ONLY show their class students
        if current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if teacher and teacher.class_id:
                # Only show students from teacher's class
                query = query.filter_by(class_id=teacher.class_id)
                logger.info(f"Teacher {teacher.name} filtering by class_id: {teacher.class_id}")
            else:
                # Teacher has no class assigned - show empty
                query = query.filter_by(class_id=-1)
                logger.warning(f"Teacher {current_user.email} has no class assigned")
        
        if status_filter and status_filter != 'all':
            query = query.filter_by(status=status_filter)
        
        if class_filter and class_filter != '' and class_filter != 'null' and class_filter != 'undefined':
            query = query.filter_by(class_id=int(class_filter))
        
        if search:
            query = query.filter(
                or_(
                    Student.name.ilike(f'%{search}%'),
                    Student.student_id.ilike(f'%{search}%'),
                    Student.email.ilike(f'%{search}%')
                )
            )
        
        total = query.count()
        students = query.offset((page - 1) * per_page).limit(per_page).all()
        
        result = []
        for s in students:
            class_obj = Class.query.get(s.class_id)
            result.append({
                'id': s.id,
                'student_id': s.student_id,
                'name': s.name,
                'email': s.email or '',
                'phone': s.phone or '',
                'parent_name': s.parent_name or '',
                'parent_phone': s.parent_phone or '',
                'class_id': s.class_id,
                'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else 'Unassigned',
                'current_year': s.current_year,
                'status': s.status,
                'start_year': s.start_year,
                'end_year': s.end_year,
                'dob': str(s.dob) if s.dob else '',
                'address': s.address or '',
                'sms_opt_out': s.sms_opt_out,
                'whatsapp_opt_out': s.whatsapp_opt_out
            })
        
        return jsonify({'students': result, 'total': total, 'page': page, 'per_page': per_page})
    except Exception as e:
        logger.error(f"Error in get_students: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/students/<int:student_id>', methods=['GET'])
@login_required
def get_student(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        class_obj = Class.query.get(student.class_id)
        
        return jsonify({
            'id': student.id,
            'student_id': student.student_id,
            'name': student.name,
            'email': student.email or '',
            'phone': student.phone or '',
            'parent_name': student.parent_name or '',
            'parent_phone': student.parent_phone or '',
            'class_id': student.class_id,
            'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else '',
            'current_year': student.current_year,
            'status': student.status,
            'start_year': student.start_year,
            'end_year': student.end_year,
            'dob': str(student.dob) if student.dob else '',
            'address': student.address or '',
            'sms_opt_out': student.sms_opt_out,
            'whatsapp_opt_out': student.whatsapp_opt_out
        })
    except Exception as e:
        logger.error(f"Error in get_student: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/class/<int:class_id>', methods=['GET'])
@login_required
def get_students_by_class(class_id):
    try:
        students = Student.query.filter_by(class_id=class_id, status='active').all()
        result = [{
            'id': s.id,
            'student_id': s.student_id,
            'name': s.name,
            'phone': s.phone,
            'parent_phone': s.parent_phone
        } for s in students]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_students_by_class: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students', methods=['POST'])
@login_required
@role_required('admin')
def create_student():
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'error': 'Student name is required'}), 400
        
        # ✅ ADD THIS LINE - DEFINE start_year FIRST
        start_year = data.get('start_year', datetime.now().year)
        
        student_id = generate_student_id(
            class_id=data.get('class_id'),
            start_year=start_year
        )
        
        temp_password = f"Student@{student_id[-4:]}"
        hashed_password = hash_password(temp_password)
        
        user = User(
            email=data.get('email') or f"{student_id}@school.edu",
            password=hashed_password,
            role='student',
            is_active=True
        )
        db.session.add(user)
        db.session.flush()
        
        student = Student(
            student_id=student_id,
            user_id=user.id,
            name=data['name'],
            email=data.get('email'),
            phone=data.get('phone'),
            parent_name=data.get('parent_name'),
            parent_phone=data.get('parent_phone'),
            class_id=data.get('class_id') if data.get('class_id') else None,
            current_year=data.get('current_year', '1st'),
            start_year=start_year,  # ✅ Now this works because start_year is defined
            status='active',
            dob=data.get('dob') or None,
            address=data.get('address'),
            sms_opt_out=data.get('sms_opt_out', False),
            whatsapp_opt_out=data.get('whatsapp_opt_out', False)
        )
        
        db.session.add(student)
        db.session.commit()
        
        logger.info(f"Student created: {student.name} ({student.student_id})")
        return jsonify({
            'message': 'Student created successfully',
            'student_id': student_id,
            'id': student.id,
            'temp_password': temp_password
        }), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_student: {str(e)}")
        return jsonify({'error': str(e)}), 500



@app.route('/api/students/<int:student_id>', methods=['PUT'])
@login_required
def update_student(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        
        if current_user.role != 'admin' and current_user.role != 'student':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        allowed_fields = ['name', 'email', 'phone', 'parent_name', 'parent_phone', 'class_id', 'current_year', 'dob', 'address', 'sms_opt_out', 'whatsapp_opt_out']
        
        for field in allowed_fields:
            if field in data:
                setattr(student, field, data[field])
        
        # FIX: Check if student.user exists before accessing
        if 'email' in data and hasattr(student, 'user') and student.user:
            student.user.email = data['email']
        
        db.session.commit()
        return jsonify({'message': 'Student updated successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_student: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def delete_student(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        Attendance.query.filter_by(student_id=student.id).delete()
        Result.query.filter_by(student_id=student.id).delete()
        Leave.query.filter_by(student_id=student.id).delete()
        WhatsAppMessage.query.filter_by(student_id=student.id).delete()
        if student.user_id:
            User.query.filter_by(id=student.user_id).delete()
        db.session.delete(student)
        db.session.commit()
        return jsonify({'message': 'Student deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_student: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# TEACHER API
# ============================================================

@app.route('/api/teachers', methods=['GET'])
@login_required
def get_teachers():
    try:
        teachers = Teacher.query.all()
        result = []
        for t in teachers:
            class_obj = Class.query.get(t.class_id)
            result.append({
                'id': t.id,
                'name': t.name,
                'email': t.email,
                'phone': t.phone or '',
                'subject': t.subject or '',
                'whatsapp_number': t.whatsapp_number or '',
                'class_id': t.class_id,
                'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else 'Unassigned'
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_teachers: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['GET'])
@login_required
def get_teacher(teacher_id):
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        class_obj = Class.query.get(teacher.class_id)
        return jsonify({
            'id': teacher.id,
            'name': teacher.name,
            'email': teacher.email,
            'phone': teacher.phone or '',
            'subject': teacher.subject or '',
            'whatsapp_number': teacher.whatsapp_number or '',
            'class_id': teacher.class_id,
            'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else 'Unassigned'
        })
    except Exception as e:
        logger.error(f"Error in get_teacher: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers', methods=['POST'])
@login_required
@role_required('admin')
def create_teacher():
    try:
        data = request.get_json()
        if not data.get('name') or not data.get('email'):
            return jsonify({'error': 'Name and email are required'}), 400
        
        temp_password = 'Teacher@123'
        hashed_password = hash_password(temp_password)
        
        user = User(email=data['email'], password=hashed_password, role='teacher', is_active=True)
        db.session.add(user)
        db.session.flush()
        
        teacher = Teacher(
            user_id=user.id,
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            subject=data.get('subject'),
            whatsapp_number=data.get('whatsapp_number'),
            class_id=data.get('class_id') if data.get('class_id') else None
        )
        db.session.add(teacher)
        db.session.commit()
        
        return jsonify({'message': 'Teacher created successfully', 'id': teacher.id, 'temp_password': temp_password}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_teacher: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/teachers/<int:teacher_id>', methods=['PUT'])
@login_required
@role_required('admin')
def update_teacher(teacher_id):
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        data = request.get_json()
        
        allowed_fields = ['name', 'email', 'phone', 'subject', 'whatsapp_number', 'class_id']
        for field in allowed_fields:
            if field in data:
                setattr(teacher, field, data[field])
        
        # FIX: Check if teacher.user exists before accessing
        if 'email' in data and hasattr(teacher, 'user') and teacher.user:
            teacher.user.email = data['email']
        
        db.session.commit()
        return jsonify({'message': 'Teacher updated successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_teacher: {str(e)}")
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def delete_teacher(teacher_id):
    try:
        teacher = Teacher.query.get_or_404(teacher_id)
        if teacher.user:
            db.session.delete(teacher.user)
        db.session.delete(teacher)
        db.session.commit()
        return jsonify({'message': 'Teacher deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_teacher: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# CLASS API
# ============================================================

@app.route('/api/classes', methods=['GET'])
@login_required
def get_classes():
    try:
        classes = Class.query.all()
        result = []
        for c in classes:
            teacher = Teacher.query.get(c.teacher_id)
            student_count = Student.query.filter_by(class_id=c.id, status='active').count()
            result.append({
                'id': c.id,
                'name': c.name,
                'section': c.section,
                'teacher_id': c.teacher_id,
                'teacher_name': teacher.name if teacher else 'Unassigned',
                'student_count': student_count
            })
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_classes: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes', methods=['POST'])
@login_required
@role_required('admin')
def create_class():
    try:
        data = request.get_json()
        if not data.get('name') or not data.get('section'):
            return jsonify({'error': 'Class name and section are required'}), 400
        
        new_class = Class(
            name=data['name'],
            section=data['section'],
            teacher_id=data.get('teacher_id') if data.get('teacher_id') else None
        )
        db.session.add(new_class)
        db.session.commit()
        return jsonify({'message': 'Class created successfully', 'id': new_class.id}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_class: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>', methods=['PUT'])
@login_required
@role_required('admin')
def update_class(class_id):
    try:
        class_obj = Class.query.get_or_404(class_id)
        data = request.get_json()
        
        if 'name' in data:
            class_obj.name = data['name']
        if 'section' in data:
            class_obj.section = data['section']
        if 'teacher_id' in data:
            class_obj.teacher_id = data['teacher_id']
        
        db.session.commit()
        return jsonify({'message': 'Class updated successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_class: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/classes/<int:class_id>', methods=['DELETE'])
@login_required
@role_required('admin')
def delete_class(class_id):
    try:
        class_obj = Class.query.get_or_404(class_id)
        Student.query.filter_by(class_id=class_id).update({'class_id': None})
        db.session.delete(class_obj)
        db.session.commit()
        return jsonify({'message': 'Class deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_class: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ATTENDANCE API (FIXED - Only allows today's attendance)
# ============================================================

@app.route('/api/attendance', methods=['GET'])
@login_required
def get_attendance():
    try:
        student_id = request.args.get('student_id')
        class_id = request.args.get('class_id')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        
        query = Attendance.query
        
        if student_id:
            query = query.filter_by(student_id=int(student_id))
        if class_id:
            query = query.filter_by(class_id=int(class_id))
        if date_from:
            query = query.filter(Attendance.date >= date_from)
        if date_to:
            query = query.filter(Attendance.date <= date_to)
        
        attendance = query.order_by(Attendance.date.desc()).all()
        
        result = []
        for a in attendance:
            student = Student.query.get(a.student_id)
            result.append({
                'id': a.id,
                'student_id': a.student_id,
                'student_name': student.name if student else 'Unknown',
                'class_id': a.class_id,
                'date': str(a.date),
                'status': a.status,
                'marked_by_type': a.marked_by_type,
                'remarks': a.remarks,
                'whatsapp_sent': a.whatsapp_sent
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# ATTENDANCE BULK SAVE API (FIXED - SENDS WHATSAPP FOR ABSENT STUDENTS)
# ============================================================

@app.route('/api/attendance/bulk', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def save_bulk_attendance():
    try:
        data = request.get_json()
        date_str = data.get('date')
        records = data.get('records', [])
        
        if not date_str or not records:
            return jsonify({'error': 'Date and attendance records required'}), 400
        
        attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        today = datetime.now().date()
        
        # Only allow marking attendance for today
        if attendance_date != today:
            return jsonify({'error': 'Attendance can only be marked for today'}), 400
        
        saved_count = 0
        absent_alerts_sent = 0
        
        for record in records:
            student_id = record.get('student_id')
            status = record.get('status')
            remarks = record.get('remarks', '')
            class_id = record.get('class_id')
            
            if not student_id or not status:
                continue
            
            # Get student for class_id if not provided
            if not class_id:
                student = Student.query.get(student_id)
                if student:
                    class_id = student.class_id
            
            # Check if attendance already exists for this date
            existing = Attendance.query.filter_by(
                student_id=student_id,
                date=attendance_date
            ).first()
            
            if existing:
                existing.status = status
                existing.remarks = remarks
                existing.marked_by = current_user.id
                existing.marked_by_type = 'teacher' if current_user.role == 'teacher' else 'system'
                db.session.add(existing)
                
                # If status changed to absent, send alert
                if status == 'absent' and not existing.whatsapp_sent:
                    student = Student.query.get(student_id)
                    if student:
                        print(f"\n🔔 Sending absence alert for: {student.name}")
                        success = send_absence_alert(student, existing)
                        if success:
                            absent_alerts_sent += 1
                            print(f"✅ Absence alert sent for {student.name}")
                        else:
                            print(f"❌ Failed to send absence alert for {student.name}")
            else:
                attendance = Attendance(
                    student_id=student_id,
                    class_id=class_id,
                    date=attendance_date,
                    status=status,
                    remarks=remarks,
                    marked_by=current_user.id,
                    marked_by_type='teacher' if current_user.role == 'teacher' else 'system'
                )
                db.session.add(attendance)
                db.session.flush()
                
                # ========== FIX: SEND WHATSAPP FOR ABSENT STUDENTS ==========
                if status == 'absent':
                    student = Student.query.get(student_id)
                    if student:
                        print(f"\n🔔 Sending absence alert for: {student.name}")
                        success = send_absence_alert(student, attendance)
                        if success:
                            absent_alerts_sent += 1
                            print(f"✅ Absence alert sent for {student.name}")
                        else:
                            print(f"❌ Failed to send absence alert for {student.name}")
            
            saved_count += 1
        
        db.session.commit()
        
        return jsonify({
            'message': f'Attendance saved for {saved_count} students',
            'absent_alerts_sent': absent_alerts_sent
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in save_bulk_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/attendance/report', methods=['GET'])
@login_required
def attendance_report():
    try:
        class_id = request.args.get('class_id')
        month = request.args.get('month')
        year = request.args.get('year')
        
        if not class_id or not month or not year:
            return jsonify({'error': 'Missing parameters'}), 400
        
        month = int(month)
        year = int(year)
        
        students = Student.query.filter_by(class_id=int(class_id), status='active').all()
        
        report = []
        for student in students:
            records = Attendance.query.filter(
                Attendance.student_id == student.id,
                func.month(Attendance.date) == month,
                func.year(Attendance.date) == year
            ).all()
            
            total = len(records)
            present = sum(1 for r in records if r.status == 'present')
            absent = sum(1 for r in records if r.status == 'absent')
            late = sum(1 for r in records if r.status == 'late')
            percentage = round((present / total) * 100, 2) if total > 0 else 0
            
            report.append({
                'student_id': student.student_id,
                'name': student.name,
                'total_days': total,
                'present': present,
                'absent': absent,
                'late': late,
                'percentage': percentage,
                'status': 'Good' if percentage >= 75 else 'Needs Improvement'
            })
        
        return jsonify(report)
    except Exception as e:
        logger.error(f"Error in attendance_report: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/attendance/export', methods=['GET'])
@login_required
def export_attendance():
    try:
        class_id = request.args.get('class_id')
        month = request.args.get('month')
        year = request.args.get('year')
        
        if not class_id or not month or not year:
            return jsonify({'error': 'Missing parameters'}), 400
        
        students = Student.query.filter_by(class_id=int(class_id), status='active').all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Student ID', 'Name', 'Total Days', 'Present', 'Absent', 'Late', 'Percentage', 'Status'])
        
        for student in students:
            records = Attendance.query.filter(
                Attendance.student_id == student.id,
                func.month(Attendance.date) == int(month),
                func.year(Attendance.date) == int(year)
            ).all()
            
            total = len(records)
            present = sum(1 for r in records if r.status == 'present')
            absent = sum(1 for r in records if r.status == 'absent')
            late = sum(1 for r in records if r.status == 'late')
            percentage = round((present / total) * 100, 2) if total > 0 else 100
            
            writer.writerow([student.student_id, student.name, total, present, absent, late, percentage, 'Good' if percentage >= 75 else 'Needs Improvement'])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'attendance_{class_id}_{month}_{year}.csv'
        )
    except Exception as e:
        logger.error(f"Error in export_attendance: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# EXAMS API
# ============================================================

@app.route('/api/exams', methods=['GET'])
@login_required
def get_exams():
    try:
        class_id = request.args.get('class_id')
        query = Exam.query
        if class_id and class_id != 'null' and class_id != '':
            query = query.filter_by(class_id=int(class_id))
        
        exams = query.all()
        result = []
        for e in exams:
            class_obj = Class.query.get(e.class_id)
            result.append({
                'id': e.id,
                'title': e.title,
                'subject': e.subject,
                'class_id': e.class_id,
                'class_name': f"{class_obj.name}-{class_obj.section}" if class_obj else 'All Classes',
                'exam_date': str(e.exam_date) if e.exam_date else None,
                'max_marks': e.max_marks
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_exams: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exams', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def create_exam():
    try:
        data = request.get_json()
        
        if not data.get('title') or not data.get('subject'):
            return jsonify({'error': 'Title and subject are required'}), 400
        
        exam = Exam(
            title=data['title'],
            subject=data['subject'],
            class_id=data.get('class_id') if data.get('class_id') else None,
            exam_date=data.get('exam_date'),
            max_marks=data.get('max_marks', 100)
        )
        
        db.session.add(exam)
        db.session.commit()
        
        return jsonify({'message': 'Exam created successfully', 'id': exam.id}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_exam: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/exams/<int:exam_id>', methods=['DELETE'])
@login_required
@role_required('admin', 'teacher')
def delete_exam(exam_id):
    try:
        exam = Exam.query.get_or_404(exam_id)
        Result.query.filter_by(exam_id=exam_id).delete()
        db.session.delete(exam)
        db.session.commit()
        return jsonify({'message': 'Exam deleted successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_exam: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# RESULTS API
# ============================================================

@app.route('/api/results', methods=['GET'])
@login_required
def get_results():
    try:
        student_id = request.args.get('student_id')
        exam_id = request.args.get('exam_id')
        
        query = Result.query
        if student_id:
            query = query.filter_by(student_id=int(student_id))
        if exam_id:
            query = query.filter_by(exam_id=int(exam_id))
        
        results = query.all()
        
        result = []
        for r in results:
            exam = Exam.query.get(r.exam_id)
            student = Student.query.get(r.student_id)
            result.append({
                'id': r.id,
                'student_id': r.student_id,
                'student_name': student.name if student else 'Unknown',
                'exam_id': r.exam_id,
                'exam_title': exam.title if exam else 'Unknown',
                'subject': exam.subject if exam else 'Unknown',
                'marks': float(r.marks),
                'max_marks': float(r.max_marks),
                'percentage': float(r.percentage) if r.percentage else None,
                'grade': r.grade
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_results: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/results', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def save_results():
    try:
        data = request.get_json()
        results_list = data.get('results', [])
        
        saved = 0
        for r_data in results_list:
            student_id = r_data.get('student_id')
            exam_id = r_data.get('exam_id')
            marks = float(r_data.get('marks', 0))
            max_marks = float(r_data.get('max_marks', 100))
            
            percentage = (marks / max_marks) * 100 if max_marks > 0 else 0
            grade = calculate_grade(percentage)
            
            existing = Result.query.filter_by(student_id=student_id, exam_id=exam_id).first()
            
            if existing:
                existing.marks = marks
                existing.max_marks = max_marks
                existing.percentage = percentage
                existing.grade = grade
            else:
                result = Result(
                    student_id=student_id,
                    exam_id=exam_id,
                    marks=marks,
                    max_marks=max_marks,
                    percentage=percentage,
                    grade=grade
                )
                db.session.add(result)
            
            saved += 1
        
        db.session.commit()
        return jsonify({'message': f'{saved} results saved successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in save_results: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# PROGRESS REPORT API
# ============================================================

@app.route('/api/progress/report/<int:student_id>', methods=['GET'])
@login_required
def get_progress_report(student_id):
    try:
        student = Student.query.get_or_404(student_id)
        
        results = Result.query.filter_by(student_id=student_id).all()
        
        subjects = {}
        for r in results:
            exam = Exam.query.get(r.exam_id)
            if exam:
                if exam.subject not in subjects:
                    subjects[exam.subject] = {'marks': [], 'max_marks': [], 'exams': []}
                subjects[exam.subject]['marks'].append(float(r.marks))
                subjects[exam.subject]['max_marks'].append(float(r.max_marks))
                subjects[exam.subject]['exams'].append(exam.title)
        
        subject_summary = []
        total_percentage = 0
        
        for subject_name, data in subjects.items():
            avg_marks = sum(data['marks']) / len(data['marks'])
            avg_max = sum(data['max_marks']) / len(data['max_marks'])
            percentage = (avg_marks / avg_max) * 100 if avg_max > 0 else 0
            total_percentage += percentage
            
            subject_summary.append({
                'subject': subject_name,
                'average_marks': round(avg_marks, 2),
                'percentage': round(percentage, 2),
                'grade': calculate_grade(percentage),
                'tests_count': len(data['marks'])
            })
        
        overall_percentage = total_percentage / len(subject_summary) if subject_summary else 0
        
        attendance_records = Attendance.query.filter_by(student_id=student_id).all()
        total_days = len(attendance_records)
        present_days = sum(1 for r in attendance_records if r.status == 'present')
        attendance_percentage = (present_days / total_days) * 100 if total_days > 0 else 0
        
        class_obj = Class.query.get(student.class_id)
        
        return jsonify({
            'student': {
                'id': student.id,
                'name': student.name,
                'student_id': student.student_id,
                'class': f"{class_obj.name}-{class_obj.section}" if class_obj else 'N/A'
            },
            'academic_progress': {
                'subjects': subject_summary,
                'overall_percentage': round(overall_percentage, 2),
                'overall_grade': calculate_grade(overall_percentage)
            },
            'attendance_summary': {
                'total_days': total_days,
                'present_days': present_days,
                'attendance_percentage': round(attendance_percentage, 2)
            }
        })
    except Exception as e:
        logger.error(f"Error in get_progress_report: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# LEAVES API
# ============================================================

@app.route('/api/leaves', methods=['GET'])
@login_required
def get_leaves():
    try:
        if current_user.role == 'student':
            student = Student.query.filter_by(user_id=current_user.id).first()
            if student:
                leaves = Leave.query.filter_by(student_id=student.id).order_by(Leave.applied_at.desc()).all()
            else:
                leaves = []
        elif current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if teacher and teacher.class_id:
                students = Student.query.filter_by(class_id=teacher.class_id).all()
                student_ids = [s.id for s in students]
                leaves = Leave.query.filter(Leave.student_id.in_(student_ids)).order_by(Leave.applied_at.desc()).all()
            else:
                leaves = []
        else:
            leaves = Leave.query.order_by(Leave.applied_at.desc()).all()
        
        result = []
        for l in leaves:
            student = Student.query.get(l.student_id)
            result.append({
                'id': l.id,
                'student_id': l.student_id,
                'student_name': student.name if student else 'Unknown',
                'from_date': str(l.from_date),
                'to_date': str(l.to_date),
                'reason': l.reason,
                'status': l.status,
                'review_remarks': l.review_remarks,
                'applied_at': str(l.applied_at)
            })
        
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_leaves: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leaves', methods=['POST'])
@login_required
@role_required('student')
def apply_leave():
    try:
        data = request.get_json()
        
        from_date = data.get('from_date')
        to_date = data.get('to_date')
        reason = data.get('reason')
        
        if not from_date or not to_date:
            return jsonify({'error': 'From date and to date are required'}), 400
        
        student = Student.query.filter_by(user_id=current_user.id).first()
        if not student:
            return jsonify({'error': 'Student profile not found'}), 404
        
        leave = Leave(
            student_id=student.id,
            from_date=from_date,
            to_date=to_date,
            reason=reason,
            status='pending'
        )
        
        db.session.add(leave)
        db.session.commit()
        
        if student.class_id:
            class_obj = Class.query.get(student.class_id)
            if class_obj and class_obj.teacher_id:
                teacher = Teacher.query.get(class_obj.teacher_id)
                if teacher and teacher.user_id:
                    create_notification(
                        teacher.user_id,
                        'leave_update',
                        f"New leave application from {student.name} ({student.student_id})",
                        leave.id
                    )
        
        return jsonify({'message': 'Leave application submitted successfully', 'id': leave.id}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in apply_leave: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/leaves/<int:leave_id>', methods=['PUT'])
@login_required
@role_required('admin', 'teacher')
def review_leave(leave_id):
    try:
        leave = Leave.query.get_or_404(leave_id)
        data = request.get_json()
        
        status = data.get('status')
        review_remarks = data.get('review_remarks')
        
        if status not in ['approved', 'rejected']:
            return jsonify({'error': 'Invalid status'}), 400
        
        leave.status = status
        leave.reviewed_by = current_user.id
        leave.review_remarks = review_remarks
        
        db.session.commit()
        
        student = Student.query.get(leave.student_id)
        if student and student.user_id:
            create_notification(
                student.user_id,
                'leave_update',
                f"Your leave application has been {status}. Remarks: {review_remarks or 'None'}",
                leave.id
            )
        
        return jsonify({'message': f'Leave {status} successfully'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in review_leave: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# NOTIFICATIONS API
# ============================================================

@app.route('/api/notifications', methods=['GET'])
@login_required
def get_notifications():
    try:
        notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(50).all()
        
        result = [{
            'id': n.id,
            'type': n.type,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': str(n.created_at)
        } for n in notifications]
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in get_notifications: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/read', methods=['POST'])
@login_required
def mark_notifications_read():
    try:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
        db.session.commit()
        return jsonify({'message': 'All notifications marked as read'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in mark_notifications_read: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/notifications/unread/count', methods=['GET'])
@login_required
def get_unread_notification_count():
    try:
        count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return jsonify({'count': count})
    except Exception as e:
        logger.error(f"Error in get_unread_notification_count: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# WHATSAPP API (SINGLE CLEAN ROUTE SET)
# ============================================================

@app.route('/api/whatsapp/status', methods=['GET'])
@login_required
def whatsapp_status():
    """Check WhatsApp bridge connection status"""
    status = check_whatsapp_bridge_status()
    return jsonify(status)

@app.route('/api/whatsapp/qr', methods=['GET'])
@login_required
@role_required('admin')
def whatsapp_qr():
    """Get QR code for WhatsApp connection (Admin only)"""
    try:
        response = requests.get(f"{WHATSAPP_BRIDGE_URL}/qr", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json())
        return jsonify({'qr': None, 'connected': False})
    except Exception as e:
        logger.error(f"Error getting QR: {str(e)}")
        return jsonify({'qr': None, 'connected': False, 'error': str(e)})

@app.route('/api/whatsapp/bulk', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def send_bulk_whatsapp():
    try:
        data = request.get_json()
        class_id = data.get('class_id')
        recipient_type = data.get('recipient_type', 'parent')
        message = data.get('message')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        if not class_id:
            return jsonify({'error': 'class_id required'}), 400
        
        students = Student.query.filter_by(class_id=int(class_id), status='active').all()
        
        sent_count = 0
        for student in students:
            phone = student.parent_phone if recipient_type == 'parent' else student.phone
            if phone:
                success, _ = send_whatsapp_message(
                    phone,
                    message,
                    student.name if recipient_type == 'student' else f"Parent of {student.name}",
                    recipient_type,
                    student.id,
                    'bulk'
                )
                if success:
                    sent_count += 1
        
        create_notification(
            current_user.id,
            'whatsapp',
            f"Bulk WhatsApp message sent to {sent_count} students",
            None
        )
        
        return jsonify({
            'success': True,
            'message': f'WhatsApp messages sent to {sent_count} students',
            'sent_count': sent_count
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in send_bulk_whatsapp: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/logs', methods=['GET'])
@login_required
def get_whatsapp_logs():
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        
        query = WhatsAppMessage.query
        
        if current_user.role == 'student':
            student = Student.query.filter_by(user_id=current_user.id).first()
            if student:
                query = query.filter_by(student_id=student.id)
        elif current_user.role == 'teacher':
            teacher = Teacher.query.filter_by(user_id=current_user.id).first()
            if teacher and teacher.class_id:
                students = Student.query.filter_by(class_id=teacher.class_id).all()
                student_ids = [s.id for s in students]
                query = query.filter(WhatsAppMessage.student_id.in_(student_ids))
        
        total = query.count()
        messages = query.order_by(WhatsAppMessage.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
        
        result = []
        for m in messages:
            student = Student.query.get(m.student_id)
            result.append({
                'id': m.id,
                'student_name': student.name if student else 'N/A',
                'recipient_type': m.recipient_type,
                'recipient_number': m.recipient_number,
                'recipient_name': m.recipient_name,
                'message': m.message,
                'message_type': m.message_type,
                'status': m.status,
                'error_message': m.error_message,
                'created_at': str(m.created_at),
                'sent_at': str(m.sent_at) if m.sent_at else None
            })
        
        return jsonify({'messages': result, 'total': total, 'page': page, 'per_page': per_page})
    except Exception as e:
        logger.error(f"Error in get_whatsapp_logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/export', methods=['GET'])
@login_required
def export_whatsapp_logs():
    try:
        messages = WhatsAppMessage.query.order_by(WhatsAppMessage.created_at.desc()).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Date', 'Student', 'Recipient Type', 'Phone Number', 'Message', 'Status'])
        
        for m in messages:
            student = Student.query.get(m.student_id)
            writer.writerow([
                m.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                student.name if student else 'N/A',
                m.recipient_type,
                m.recipient_number,
                m.message,
                m.status
            ])
        
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'whatsapp_logs_{datetime.now().strftime("%Y%m%d")}.csv'
        )
    except Exception as e:
        logger.error(f"Error in export_whatsapp_logs: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/whatsapp/start', methods=['POST'])
@login_required
@role_required('admin')
def start_whatsapp_bridge():
    """Start WhatsApp bridge in a NEW WINDOW (stays alive)"""
    import subprocess
    import platform
    import os
    
    try:
        # Check if already running
        response = requests.get(f"{WHATSAPP_BRIDGE_URL}/status", timeout=2)
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Already running', 'connected': response.json().get('connected', False)})
    except:
        pass
    
    try:
        bridge_path = os.path.join(os.path.dirname(__file__), 'server.js')
        
        if not os.path.exists(bridge_path):
            return jsonify({'success': False, 'error': f'Bridge file not found at {bridge_path}'})
        
        if platform.system() == 'Windows':
            # Opens in NEW VISIBLE WINDOW that stays alive
            subprocess.Popen(['cmd', '/c', 'start', 'cmd', '/k', 'node', bridge_path], shell=True)
        else:
            subprocess.Popen(['node', bridge_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        
        return jsonify({'success': True, 'message': 'WhatsApp bridge started in new window'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})




# ============================================================
# STATISTICS API
# ============================================================

@app.route('/api/stats/admin', methods=['GET'])
@login_required
@role_required('admin')
def admin_stats():
    try:
        total_students = Student.query.count()
        active_students = Student.query.filter_by(status='active').count()
        total_teachers = Teacher.query.count()
        total_classes = Class.query.count()
        pending_leaves = Leave.query.filter_by(status='pending').count()
        
        today = datetime.now().date()
        today_attendance = Attendance.query.filter_by(date=today).count()
        today_present = Attendance.query.filter_by(date=today, status='present').count()
        
        return jsonify({
            'students': {'total': total_students, 'active': active_students},
            'teachers': total_teachers,
            'classes': total_classes,
            'pending_leaves': pending_leaves,
            'attendance_today': {'total': today_attendance, 'present': today_present, 'absent': today_attendance - today_present}
        })
    except Exception as e:
        logger.error(f"Error in admin_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/teacher', methods=['GET'])
@login_required
@role_required('teacher')
def teacher_stats():
    try:
        teacher = Teacher.query.filter_by(user_id=current_user.id).first()
        
        if not teacher or not teacher.class_id:
            return jsonify({
                'total_students': 0, 
                'present_today': 0, 
                'absent_today': 0, 
                'pending_leaves': 0
            })
        
        # FIX: Get ONLY students from teacher's class
        students = Student.query.filter_by(class_id=teacher.class_id, status='active').all()
        total_students = len(students)
        student_ids = [s.id for s in students]
        
        today = datetime.now().date()
        present_today = Attendance.query.filter(
            Attendance.class_id == teacher.class_id, 
            Attendance.date == today, 
            Attendance.status == 'present'
        ).count()
        
        absent_today = Attendance.query.filter(
            Attendance.class_id == teacher.class_id, 
            Attendance.date == today, 
            Attendance.status == 'absent'
        ).count()
        
        # FIX: Only leave requests for teacher's class students
        pending_leaves = Leave.query.filter(
            Leave.student_id.in_(student_ids), 
            Leave.status == 'pending'
        ).count() if student_ids else 0
        
        return jsonify({
            'total_students': total_students,
            'present_today': present_today,
            'absent_today': absent_today,
            'pending_leaves': pending_leaves
        })
    except Exception as e:
        logger.error(f"Error in teacher_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/stats/student', methods=['GET'])
@login_required
@role_required('student')
def student_stats():
    try:
        student = Student.query.filter_by(user_id=current_user.id).first()
        
        if not student:
            return jsonify({'attendance_pct': 0, 'present': 0, 'absent': 0, 'avg_marks': 0, 'pending_leaves': 0})
        
        attendance_records = Attendance.query.filter_by(student_id=student.id).all()
        total_days = len(attendance_records)
        present_days = sum(1 for r in attendance_records if r.status == 'present')
        attendance_pct = round((present_days / total_days) * 100, 2) if total_days > 0 else 0
        
        results = Result.query.filter_by(student_id=student.id).all()
        if results:
            avg_marks = sum(float(r.percentage) for r in results if r.percentage) / len(results)
            avg_marks = round(avg_marks, 2)
        else:
            avg_marks = 0
        
        pending_leaves = Leave.query.filter_by(student_id=student.id, status='pending').count()
        
        return jsonify({
            'attendance_pct': attendance_pct,
            'present': present_days,
            'absent': total_days - present_days,
            'avg_marks': avg_marks,
            'pending_leaves': pending_leaves
        })
    except Exception as e:
        logger.error(f"Error in student_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats/dashboard', methods=['GET'])
@login_required
def dashboard_stats():
    try:
        if current_user.role == 'admin':
            return admin_stats()
        elif current_user.role == 'teacher':
            return teacher_stats()
        elif current_user.role == 'student':
            return student_stats()
        else:
            return jsonify({'error': 'Invalid role'}), 403
    except Exception as e:
        logger.error(f"Error in dashboard_stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# CHARTS API
# ============================================================

@app.route('/api/charts/attendance', methods=['GET'])
@login_required
def attendance_chart():
    try:
        class_id = request.args.get('class_id')
        days = int(request.args.get('days', 7))
        
        labels = []
        present_data = []
        absent_data = []
        
        for i in range(days - 1, -1, -1):
            date = datetime.now().date() - timedelta(days=i)
            labels.append(date.strftime('%a'))
            
            query = Attendance.query.filter_by(date=date)
            if class_id and class_id != 'all':
                query = query.filter_by(class_id=int(class_id))
            
            present = query.filter_by(status='present').count()
            absent = query.filter_by(status='absent').count()
            
            present_data.append(present)
            absent_data.append(absent)
        
        return jsonify({'labels': labels, 'present': present_data, 'absent': absent_data})
    except Exception as e:
        logger.error(f"Error in attendance_chart: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/progress', methods=['GET'])
@login_required
def progress_chart():
    try:
        class_id = request.args.get('class_id')
        
        query = Student.query.filter_by(status='active')
        if class_id and class_id != 'all':
            query = query.filter_by(class_id=int(class_id))
        
        students = query.all()
        
        grade_distribution = {'A+': 0, 'A': 0, 'B+': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0}
        
        for student in students:
            results = Result.query.filter_by(student_id=student.id).all()
            if results:
                total_percentage = sum(float(r.percentage) for r in results if r.percentage) / len(results)
                grade = calculate_grade(total_percentage)
                if grade in grade_distribution:
                    grade_distribution[grade] += 1
        
        return jsonify({'labels': list(grade_distribution.keys()), 'data': list(grade_distribution.values())})
    except Exception as e:
        logger.error(f"Error in progress_chart: {str(e)}")
        return jsonify({'error': str(e)}), 500

# ============================================================
# INITIALIZATION
# ============================================================

def init_database():
    with app.app_context():
        db.create_all()
        
        # Create admin user
        admin = User.query.filter_by(email='admin@school.edu').first()
        if not admin:
            admin_password = hash_password('Admin@123')
            admin = User(email='admin@school.edu', password=admin_password, role='admin', is_active=True)
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin created: admin@school.edu / Admin@123")
        
        # # Create sample class
        # if Class.query.count() == 0:
        #     sample_class = Class(name='10', section='A')
        #     db.session.add(sample_class)
        #     db.session.commit()
        #     print("✅ Sample class created: 10-A")
        
        # # Create sample teacher
        # teacher_user = User.query.filter_by(email='teacher@school.edu').first()
        # if not teacher_user:
        #     teacher_password = hash_password('Teacher@123')
        #     teacher_user = User(email='teacher@school.edu', password=teacher_password, role='teacher', is_active=True)
        #     db.session.add(teacher_user)
        #     db.session.flush()
            
        #     sample_class = Class.query.first()
        #     sample_teacher = Teacher(
        #         user_id=teacher_user.id,
        #         name='Sample Teacher',
        #         email='teacher@school.edu',
        #         phone='9876543210',
        #         subject='Mathematics',
        #         whatsapp_number='9876543210',
        #         class_id=sample_class.id if sample_class else None
        #     )
        #     db.session.add(sample_teacher)
        #     db.session.commit()
        #     print("✅ Sample teacher created: teacher@school.edu / Teacher@123")
        
        # # Create sample student
        # student_user = User.query.filter_by(email='student@school.edu').first()
        # if not student_user:
        #     student_password = hash_password('Student@123')
        #     student_user = User(email='student@school.edu', password=student_password, role='student', is_active=True)
        #     db.session.add(student_user)
        #     db.session.flush()
            
        #     sample_class = Class.query.first()
        #     sample_student = Student(
        #         student_id=generate_student_id(),
        #         user_id=student_user.id,
        #         name='Sample Student',
        #         email='student@school.edu',
        #         phone='9876543211',
        #         parent_name='Sample Parent',
        #         parent_phone='9876543212',
        #         class_id=sample_class.id if sample_class else None,
        #         start_year=datetime.now().year,
        #         status='active',
        #         sms_opt_out=False,
        #         whatsapp_opt_out=False
        #     )
        #     db.session.add(sample_student)
        #     db.session.commit()
        #     print("✅ Sample student created: student@school.edu / Student@123")
        
        print("[OK] Database initialization complete")

# ============================================================
# WHATSAPP SEND ENDPOINT (CLEAN VERSION)
# ============================================================

@app.route('/api/whatsapp/send', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def send_whatsapp():
    """Send REAL WhatsApp message from your scanned account"""
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        message = data.get('message')
        recipient_type = data.get('recipient_type', 'parent')
        
        print(f"📱 WhatsApp Request - Student: {student_id}, Type: {recipient_type}")
        
        if not student_id:
            return jsonify({'success': False, 'error': 'Student ID required'}), 400
        
        if not message:
            return jsonify({'success': False, 'error': 'Message required'}), 400
        
        # Get student from database
        student = Student.query.get(student_id)
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 404
        
        # Get phone number based on who to send to
        if recipient_type == 'parent':
            phone = student.parent_phone
            recipient_name = f"Parent of {student.name}"
        else:
            phone = student.phone
            recipient_name = student.name
        
        if not phone:
            return jsonify({'success': False, 'error': f'No phone number for {student.name}'}), 400
        
        # Clean phone number
        clean_phone = re.sub(r'\D', '', str(phone))
        if len(clean_phone) == 10:
            clean_phone = '91' + clean_phone
        
        print(f"📱 Sending to: {clean_phone} ({recipient_name})")
        print(f"💬 Message: {message[:100]}...")
        
        # Send to WhatsApp bridge (YOUR SCANNED ACCOUNT)
        response = requests.post(
            f"{WHATSAPP_BRIDGE_URL}/send",
            json={'to': clean_phone, 'message': message},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                # Save to database
                whatsapp_msg = WhatsAppMessage(
                    student_id=student.id,
                    recipient_type=recipient_type,
                    recipient_number=clean_phone,
                    recipient_name=recipient_name,
                    message=message,
                    message_type='general',
                    status='sent',
                    sent_at=datetime.utcnow()
                )
                db.session.add(whatsapp_msg)
                db.session.commit()
                
                print(f"✅ WhatsApp sent successfully to {clean_phone}")
                return jsonify({
                    'success': True,
                    'message': 'WhatsApp sent successfully',
                    'to': clean_phone
                })
            else:
                return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500
        else:
            return jsonify({'success': False, 'error': f'Bridge error: {response.status_code}'}), 500
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/whatsapp/send-manual', methods=['POST'])
@login_required
@role_required('admin', 'teacher')
def send_whatsapp_manual():
    """Send manual WhatsApp message (for testing)"""
    try:
        data = request.get_json()
        phone = data.get('phone')
        message = data.get('message')
        recipient_name = data.get('recipient_name', 'User')
        
        if not phone or not message:
            return jsonify({'success': False, 'error': 'Phone and message required'}), 400
        
        # Clean phone number
        clean_phone = re.sub(r'\D', '', str(phone))
        if len(clean_phone) == 10:
            clean_phone = '91' + clean_phone
        
        # Send to WhatsApp bridge
        response = requests.post(
            f"{WHATSAPP_BRIDGE_URL}/send",
            json={'to': clean_phone, 'message': message},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return jsonify({'success': True, 'message': 'WhatsApp sent successfully'})
        
        return jsonify({'success': False, 'error': 'Failed to send'}), 500
        
    except Exception as e:
        logger.error(f"Error in send_whatsapp_manual: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/whatsapp/test-absent', methods=['GET'])
@login_required
@role_required('teacher')
def test_absent_whatsapp():
    """Test absent WhatsApp with a specific student"""
    try:
        # Get first student with parent_phone
        student = Student.query.filter(Student.parent_phone.isnot(None)).first()
        
        if not student:
            return jsonify({'error': 'No student with parent phone found'})
        
        # Create a mock attendance record
        from datetime import date
        mock_attendance = Attendance(
            student_id=student.id,
            date=date.today(),
            status='absent'
        )
        
        print(f"Testing with student: {student.name}, Phone: {student.parent_phone}")
        
        result = send_absence_alert(student, mock_attendance)
        
        return jsonify({
            'student': student.name,
            'phone': student.parent_phone,
            'result': result
        })
    except Exception as e:
        return jsonify({'error': str(e)})
    
    

@app.route('/api/whatsapp/reset', methods=['POST'])
@login_required
@role_required('admin')
def reset_whatsapp_session():
    """Reset WhatsApp session - KILL process first, then delete files"""
    import shutil
    import subprocess
    import time
    import os
    
    try:
        print("=" * 50)
        print("🔄 RESETTING WHATSAPP SESSION")
        print("=" * 50)
        
        # ============================================================
        # STEP 1: Kill the Node.js process FIRST
        # ============================================================
        print("📌 Step 1: Killing WhatsApp bridge process...")
        try:
            # Kill all node.exe processes
            subprocess.run(['taskkill', '/f', '/im', 'node.exe'], 
                         capture_output=True, shell=True)
            print("✅ Node.js processes killed")
        except Exception as e:
            print(f"⚠️ Could not kill process: {e}")
        
        # Wait for process to fully terminate
        time.sleep(3)
        print("✅ Waited 3 seconds for process to close")
        
        # ============================================================
        # STEP 2: Delete all session folders
        # ============================================================
        print("📌 Step 2: Deleting session files...")
        
        project_dir = os.path.dirname(__file__)
        
        session_paths = [
            os.path.join(project_dir, 'whatsapp-session'),
            os.path.join(project_dir, '.wwebjs_auth'),
            os.path.join(project_dir, 'whatsapp-session-old'),
            os.path.join(project_dir, 'session'),
            os.path.join(project_dir, 'LocalStorage'),
            os.path.join(project_dir, 'SessionStorage')
        ]
        
        deleted_count = 0
        
        for path in session_paths:
            if os.path.exists(path):
                try:
                    # Try normal deletion first
                    shutil.rmtree(path)
                    print(f"✅ Deleted folder: {path}")
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️ Normal delete failed for {path}: {e}")
                    # Force delete using rmdir command
                    try:
                        subprocess.run(f'rmdir /s /q "{path}"', shell=True, capture_output=True)
                        print(f"✅ Force deleted folder: {path}")
                        deleted_count += 1
                    except:
                        print(f"❌ Could not delete: {path}")
        
        # ============================================================
        # STEP 3: Delete individual session files
        # ============================================================
        print("📌 Step 3: Deleting session files...")
        
        session_files = [
            'whatsapp-session.json',
            'session.json', 
            'auth_info.json',
            'wwebjs_auth.json',
            'wwebjs_session.json'
        ]
        
        for file in session_files:
            file_path = os.path.join(project_dir, file)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"✅ Deleted file: {file}")
                    deleted_count += 1
                except Exception as e:
                    print(f"⚠️ Could not delete {file}: {e}")
        
        print("=" * 50)
        print(f"📊 TOTAL DELETED: {deleted_count} items")
        print("=" * 50)
        
        if deleted_count > 0:
            return jsonify({
                'success': True, 
                'message': f'Deleted {deleted_count} session item(s). Click "Start WhatsApp Bridge" to scan new QR.'
            })
        else:
            return jsonify({
                'success': True, 
                'message': 'No session found. Click "Start WhatsApp Bridge" to scan new QR.'
            })
            
    except Exception as e:
        logger.error(f"Error resetting WhatsApp session: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
# ============================================================
# AUTO-START WHATSAPP BRIDGE (BACKGROUND)
# ============================================================

def auto_start_whatsapp_bridge():
    """Automatically start WhatsApp bridge in background"""
    import subprocess
    import time
    import os
    
    # Wait for Flask to start
    time.sleep(5)
    
    try:
        # Check if bridge is already running
        response = requests.get('http://localhost:3001/status', timeout=2)
        if response.status_code == 200:
            print("✅ WhatsApp bridge already running")
            return
    except:
        pass
    
    # Start bridge in background
    bridge_path = os.path.join(os.path.dirname(__file__), 'server.js')
    
    if os.path.exists(bridge_path):
        print("🚀 Auto-starting WhatsApp bridge in background...")
        
        if os.name == 'nt':  # Windows
            # Start MINIMIZED (no visible window)
            subprocess.Popen(
                ['start', '/min', 'cmd', '/c', 'node', bridge_path],
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:  # Mac/Linux
            subprocess.Popen(
                ['node', bridge_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
        
        print("✅ WhatsApp bridge started in background")
        print("📱 It will stay connected forever!")
    else:
        print(f"⚠️ server.js not found at {bridge_path}")

# Start WhatsApp bridge in background thread
import threading
threading.Thread(target=auto_start_whatsapp_bridge, daemon=True).start()



# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        init_database()
    
    print("=" * 60)
    print("🚀 STUDENT MANAGEMENT SYSTEM STARTED")
    print("=" * 60)
    print("🌐 Access at: http://localhost:5000")
    print("📧 Admin Login: admin@school.edu / Admin@123")
    print("👨‍🏫 Teacher Login: teacher@school.edu / Teacher@123")
    print("👨‍🎓 Student Login: student@school.edu / Student@123")
    print("=" * 60)
    
    # Production: Use Gunicorn, for development use debug=False
    app.run(debug=False, port=5000, host='0.0.0.0')
