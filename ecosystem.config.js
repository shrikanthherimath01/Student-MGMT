module.exports = {
  apps: [{
    name: 'flask-app',
    script: 'venv/Scripts/python.exe',
    args: 'app.py',
    cwd: 'C:\\StudentManagementSystem\\sms',
    env: {
      PYTHONIOENCODING: 'utf-8',
      PYTHONUTF8: '1'
    }
  }, {
    name: 'whatsapp-bridge',
    script: 'server.js',
    cwd: 'C:\\StudentManagementSystem\\sms'
  }]
};
