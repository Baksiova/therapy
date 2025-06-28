# database.py - Databázová vrstva pre AsisTeRapie
import sqlite3
import json
import os
import time
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class TherapyDatabase:
    """
    SQLite databáza pre Terapeutický Asistent
    Automaticky sa vytvorí pri prvom spustení
    """
    
    def __init__(self, db_path: str = "asisterapie_data.db"):
        self.db_path = db_path
        self.init_database()
        print(f"✅ AsisTeRapie databáza ready: {os.path.abspath(db_path)}")
    
    def init_database(self):
        """Vytvorí databázové tabuľky ak neexistujú"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Sessions tabuľka
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_messages INTEGER DEFAULT 0,
                    user_ip TEXT,
                    user_agent TEXT,
                    crisis_count INTEGER DEFAULT 0
                )
            ''')
            
            # Messages tabuľka  
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    crisis_detected BOOLEAN DEFAULT FALSE,
                    sentiment_score REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            ''')
            
            # Crisis events tabuľka
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crisis_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    message_id INTEGER,
                    crisis_keywords TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    handled BOOLEAN DEFAULT TRUE,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id),
                    FOREIGN KEY (message_id) REFERENCES messages (id)
                )
            ''')
            
            conn.commit()
            print("📊 Databázové tabuľky inicializované")
    
    def create_session(self, user_ip: str = None, user_agent: str = None) -> str:
        """Vytvorí novú session"""
        session_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (session_id, user_ip, user_agent)
                VALUES (?, ?, ?)
            ''', (session_id, user_ip, user_agent))
            conn.commit()
        
        print(f"🆕 Nová session: {session_id[:8]}...")
        return session_id
    
    def add_message(self, session_id: str, role: str, content: str, 
                   crisis_detected: bool = False, sentiment_score: float = None) -> int:
        """Pridá správu do konverzácie"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO messages (session_id, role, content, crisis_detected, sentiment_score)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, role, content, crisis_detected, sentiment_score))
            
            message_id = cursor.lastrowid
            
            # Aktualizuj session
            cursor.execute('''
                UPDATE sessions 
                SET last_activity = CURRENT_TIMESTAMP,
                    total_messages = total_messages + 1,
                    crisis_count = crisis_count + ?
                WHERE session_id = ?
            ''', (1 if crisis_detected else 0, session_id))
            
            conn.commit()
            
        print(f"💬 Message saved: {role} | Crisis: {crisis_detected}")
        return message_id
    
    def log_crisis_event(self, session_id: str, message_id: int, keywords: List[str]):
        """Zaloguje krízovú udalosť"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO crisis_events (session_id, message_id, crisis_keywords)
                VALUES (?, ?, ?)
            ''', (session_id, message_id, json.dumps(keywords)))
            conn.commit()
        
        print(f"🚨 Crisis logged: {keywords}")
    
    def get_conversation_history(self, session_id: str, limit: int = 50) -> List[Dict]:
        """Získa históriu konverzácie"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT role, content, timestamp, crisis_detected, sentiment_score
                FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (session_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                messages.append({
                    'role': row[0],
                    'content': row[1],
                    'timestamp': row[2],
                    'crisis_detected': bool(row[3]),
                    'sentiment_score': row[4]
                })
            
            return list(reversed(messages))
    
    def get_admin_dashboard_data(self) -> Dict:
        """Dáta pre admin dashboard"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Základné štatistiky
            cursor.execute('SELECT COUNT(*) FROM sessions')
            total_sessions = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM messages')
            total_messages = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM crisis_events')
            total_crisis = cursor.fetchone()[0]
            
            # Dnešné štatistiky
            today = datetime.now().date()
            cursor.execute('''
                SELECT COUNT(*) FROM sessions 
                WHERE DATE(created_at) = ?
            ''', (today,))
            today_sessions = cursor.fetchone()[0]
            
            cursor.execute('''
                SELECT COUNT(*) FROM messages 
                WHERE DATE(timestamp) = ?
            ''', (today,))
            today_messages = cursor.fetchone()[0]
            
            # Posledné session
            cursor.execute('''
                SELECT session_id, created_at, total_messages, crisis_count
                FROM sessions 
                ORDER BY created_at DESC 
                LIMIT 10
            ''')
            recent_sessions = cursor.fetchall()
            
            # Krízové udalosti
            cursor.execute('''
                SELECT ce.timestamp, ce.crisis_keywords, s.session_id
                FROM crisis_events ce
                JOIN sessions s ON ce.session_id = s.session_id
                ORDER BY ce.timestamp DESC
                LIMIT 5
            ''')
            recent_crisis = cursor.fetchall()
            
            return {
                'overview': {
                    'total_sessions': total_sessions,
                    'total_messages': total_messages,
                    'total_crisis_events': total_crisis,
                    'today_sessions': today_sessions,
                    'today_messages': today_messages,
                    'database_file': os.path.abspath(self.db_path),
                    'database_size_mb': round(os.path.getsize(self.db_path) / 1024 / 1024, 2) if os.path.exists(self.db_path) else 0
                },
                'recent_sessions': [
                    {
                        'session_id': row[0][:8] + '...',
                        'created_at': row[1],
                        'total_messages': row[2],
                        'crisis_count': row[3]
                    } for row in recent_sessions
                ],
                'recent_crisis_events': [
                    {
                        'timestamp': row[0],
                        'keywords': json.loads(row[1]) if row[1] else [],
                        'session_id': row[2][:8] + '...'
                    } for row in recent_crisis
                ]
            }

    def export_all_data(self) -> Dict:
        """Exportuje všetky dáta"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM sessions')
            sessions = [dict(zip([col[0] for col in cursor.description], row)) 
                       for row in cursor.fetchall()]
            
            cursor.execute('SELECT * FROM messages')
            messages = [dict(zip([col[0] for col in cursor.description], row)) 
                       for row in cursor.fetchall()]
            
            cursor.execute('SELECT * FROM crisis_events')
            crisis_events = [dict(zip([col[0] for col in cursor.description], row)) 
                           for row in cursor.fetchall()]
            
            return {
                'export_timestamp': datetime.now().isoformat(),
                'database_file': self.db_path,
                'sessions': sessions,
                'messages': messages,
                'crisis_events': crisis_events,
                'total_records': len(sessions) + len(messages) + len(crisis_events)
            }

# Admin Dashboard HTML Template
ADMIN_DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="sk">
<head>
    <title>AsisTeRapie Admin Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #6D5BBA 0%, #8D58BF 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 24px; }
        .header p { margin: 5px 0 0 0; opacity: 0.9; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: white; padding: 20px; border-radius: 8px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-number { font-size: 32px; font-weight: bold; color: #6D5BBA; }
        .stat-label { color: #666; font-size: 14px; margin-top: 5px; }
        .section { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .section h3 { margin-top: 0; color: #333; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; font-weight: 600; }
        .crisis-badge { background: #e74c3c; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; }
        .btn { background: #6D5BBA; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; margin-right: 10px; }
        .btn:hover { background: #5a4a9a; }
        .file-info { background: #e8f4fd; padding: 15px; border-radius: 5px; margin: 10px 0; font-family: monospace; }
        .no-data { text-align: center; color: #666; padding: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌱 AsisTeRapie Admin Dashboard</h1>
            <p>Real-time monitoring databázy a používateľov</p>
            <button class="btn" onclick="location.reload()">🔄 Refresh</button>
            <button class="btn" onclick="exportData()">📥 Export Data</button>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.total_sessions }}</div>
                <div class="stat-label">Celkom Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.total_messages }}</div>
                <div class="stat-label">Celkom Správ</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.total_crisis_events }}</div>
                <div class="stat-label">Krízové Udalosti</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.today_sessions }}</div>
                <div class="stat-label">Dnes Sessions</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.today_messages }}</div>
                <div class="stat-label">Dnes Správ</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ data.overview.database_size_mb }} MB</div>
                <div class="stat-label">Veľkosť DB</div>
            </div>
        </div>

        <div class="file-info">
            <strong>📁 Databáza na Azure serveri:</strong><br>
            <code>{{ data.overview.database_file }}</code><br>
            <small>Prístup cez Azure Portal > App Service > SSH</small>
        </div>

        <div class="section">
            <h3>📈 Posledné Sessions</h3>
            {% if data.recent_sessions %}
            <table>
                <thead>
                    <tr><th>Session ID</th><th>Vytvorené</th><th>Správy</th><th>Krízy</th></tr>
                </thead>
                <tbody>
                    {% for session in data.recent_sessions %}
                    <tr>
                        <td><code>{{ session.session_id }}</code></td>
                        <td>{{ session.created_at }}</td>
                        <td>{{ session.total_messages }}</td>
                        <td>
                            {% if session.crisis_count > 0 %}
                                <span class="crisis-badge">{{ session.crisis_count }}</span>
                            {% else %}-{% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% else %}
            <div class="no-data">Zatiaľ žiadne session</div>
            {% endif %}
        </div>

        {% if data.recent_crisis_events %}
        <div class="section">
            <h3>🚨 Posledné Krízové Udalosti</h3>
            <table>
                <thead>
                    <tr><th>Čas</th><th>Session</th><th>Keywords</th></tr>
                </thead>
                <tbody>
                    {% for crisis in data.recent_crisis_events %}
                    <tr>
                        <td>{{ crisis.timestamp }}</td>
                        <td><code>{{ crisis.session_id }}</code></td>
                        <td>{{ crisis.keywords|join(', ') }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% else %}
        <div class="section">
            <h3>🚨 Krízové Udalosti</h3>
            <div class="no-data">✅ Žiadne krízové udalosti</div>
        </div>
        {% endif %}
    </div>

    <script>
        function exportData() {
            window.open('/admin/export', '_blank');
        }
        // Auto refresh každých 30 sekúnd
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>
'''

def create_admin_routes(app, db):
    """Vytvorí admin routes pre Flask app"""
    
    @app.route('/admin')
    @app.route('/admin/dashboard')
    def admin_dashboard():
        """Admin dashboard"""
        try:
            from flask import render_template_string
            data = db.get_admin_dashboard_data()
            return render_template_string(ADMIN_DASHBOARD_HTML, data=data)
        except Exception as e:
            return f"<h1>Database Error</h1><p>{e}</p><p>Databáza sa vytvorí pri prvom použití chatu.</p>", 500
    
    @app.route('/admin/export')
    def export_data():
        """Export všetkých dát"""
        try:
            from flask import jsonify
            data = db.export_all_data()
            response = jsonify(data)
            response.headers['Content-Disposition'] = f'attachment; filename=asisterapie_export_{int(time.time())}.json'
            return response
        except Exception as e:
            return jsonify({'error': str(e)}), 500
