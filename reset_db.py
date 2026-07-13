from app import app, db, User, Teacher, Student, Class
import bcrypt
from datetime import datetime

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode()

with app.app_context():
    # Clear existing data
    db.session.query(User).delete()
    db.session.query(Teacher).delete()
    db.session.query(Student).delete()
    db.session.query(Class).delete()
    
    # Create Admin
    admin = User(
        email='admin@school.edu',
        password=hash_password('Admin@123'),
        role='admin',
        is_active=True
    )
    db.session.add(admin)
    
    # Create Teacher
    teacher_user = User(
        email='teacher@school.edu',
        password=hash_password('Teacher@123'),
        role='teacher',
        is_active=True
    )
    db.session.add(teacher_user)
    db.session.flush()
    
    # Create Student
    student_user = User(
        email='student@school.edu',
        password=hash_password('Student@123'),
        role='student',
        is_active=True
    )
    db.session.add(student_user)
    db.session.flush()
    
    # Create Class
    class_obj = Class(name='10', section='A')
    db.session.add(class_obj)
    db.session.flush()
    
    # Create Teacher Profile
    teacher = Teacher(
        user_id=teacher_user.id,
        name='Sample Teacher',
        email='teacher@school.edu',
        phone='9876543210',
        subject='Mathematics',
        class_id=class_obj.id
    )
    db.session.add(teacher)
    
    # Create Student Profile
    student = Student(
        student_id='STU-2026-0001',
        user_id=student_user.id,
        name='Sample Student',
        email='student@school.edu',
        phone='9876543211',
        parent_name='Sample Parent',
        parent_phone='9876543212',
        class_id=class_obj.id,
        start_year=2026,
        status='active'
    )
    db.session.add(student)
    
    db.session.commit()
    
    print("=" * 50)
    print("✅ DATABASE RESET COMPLETE!")
    print("=" * 50)
    print("Admin Login:   admin@school.edu / Admin@123")
    print("Teacher Login: teacher@school.edu / Teacher@123")
    print("Student Login: student@school.edu / Student@123")
    print("=" * 50)