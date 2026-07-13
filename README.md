# 🎓 Student Management System (SMS)

A complete, production-ready Student Management System built with **Flask**, **MySQL**, and **Vanilla JavaScript**.

---

## ✨ Features

| Module | Description |
|--------|-------------|
| **Authentication** | Secure session-based login for Admin, Teacher, and Student roles |
| **Admin Dashboard** | Manage students, teachers, classes, exams, results, leaves |
| **Teacher Dashboard** | Mark attendance (only current day), enter results, manage leave requests, send WhatsApp |
| **Student Dashboard** | View profile, attendance, results, report card, apply for leave |
| **Attendance System** | Daily attendance marking, monthly reports, automatic WhatsApp alerts for absent students |
| **Results Management** | Create exams, enter marks, auto-grade calculation |
| **Report Card** | Printable report card with subject-wise performance |
| **Leave Management** | Apply for leave, approve/reject workflow |
| **WhatsApp Integration** | Send messages to parents/students via WhatsApp bridge (single QR scan) |
| **Notifications** | In-app notifications for absences, results, leave updates |
| **Dark Mode** | User preference saved in localStorage |
| **Responsive Design** | Works on desktop, tablet, and mobile |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.10+, Flask 2.3.3, Flask-SQLAlchemy, Flask-Login |
| **Database** | MySQL 8.0+ (via PyMySQL) |
| **Frontend** | HTML5, CSS3, Vanilla JavaScript, Chart.js |
| **Security** | bcrypt password hashing, role-based access control, session-based auth |
| **WhatsApp** | Baileys (Node.js bridge) - Single QR scan, persistent session |

---

## 📁 Project Structure
C:\StudentManagementSystem\sms
│
├── app.py # Flask application (all routes + models)
├── whatsapp_bridge.js # WhatsApp bridge (Node.js)
├── requirements.txt # Python dependencies
├── package.json # Node.js dependencies
├── package-lock.json # Locked Node.js dependencies
├── .env # Environment variables (create from below)
│
├── templates/
│ ├── login.html # Login page
│ ├── admin.html # Admin dashboard
│ ├── teacher.html # Teacher dashboard
│ └── student.html # Student dashboard
│
├── static/
│ ├── css/
│ │ └── dashboard.css # Shared dashboard styles
│ └── js/
│ └── dashboard.js # Shared JavaScript utilities
│
├── database/
│ └── schema.sql # MySQL database schema
│
└── whatsapp_auth/ # WhatsApp authentication folder (auto-created)