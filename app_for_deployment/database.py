# privacy_modes.py - Systém pre rôzne privacy módy

from flask import Flask, request, jsonify, session
import os
import uuid
import time
from enum import Enum
from typing import Dict, List, Optional
import json

class PrivacyMode(Enum):
    EPHEMERAL = "ephemeral"      # Žiadne ukladanie - všetko v pamäti
    TEMPORARY = "temporary"      # Ukladanie na 24h, potom auto-delete
    PERSISTENT = "persistent"    # Ukladanie až kým používateľ nezmaže
    ENCRYPTED = "encrypted"      # Ukladanie so silným šifrovaním

class PrivacyManager:
    """
    Manažér pre rôzne privacy módy používateľa
    """
    
    def __init__(self):
        # In-memory storage pre ephemeral módy
        self.ephemeral_sessions = {}
        
        # Temporary storage s expiration timestamps
        self.temporary_sessions = {}
        
        # User privacy preferences
        self.user_privacy_choices = {}
        
    def get_privacy_options(self) -> Dict:
        """Vráti dostupné privacy options pre frontend"""
        return {
            "modes": [
                {
                    "id": "ephemeral",
                    "name": "🔥 Ultra Privátny",
                    "description": "Nič sa neukladá. Konverzácia existuje len počas session.",
                    "features": [
                        "✅ Zero storage - žiadne stopy",
                        "✅ Perfektné pre citlivé témy", 
                        "✅ GDPR compliant by design",
                        "❌ Žiadna história medzi session"
                    ],
                    "retention": "0 hodín",
                    "recommended": True
                },
                {
                    "id": "temporary", 
                    "name": "⏰ Dočasný",
                    "description": "Konverzácia sa automaticky zmaže po 24 hodinách.",
                    "features": [
                        "✅ Kontextová história v rámci dňa",
                        "✅ Automatické mazanie po 24h",
                        "✅ Dobrý kompromis medzi funkčnosťou a privacy",
                        "⚠️ Dáta na serveri max 24h"
                    ],
                    "retention": "24 hodín",
                    "recommended": False
                },
                {
                    "id": "persistent",
                    "name": "📚 Trvalý",
                    "description": "História sa ukladá až kým ju sami nezmažete.",
                    "features": [
                        "✅ Dlhodobá história konverzácií",
                        "✅ Tracking pokroku a trendov",
                        "✅ Personalizované AI odpovede",
                        "✅ Kedykoľvek možnosť zmazať všetko",
                        "⚠️ Dáta na serveri až do zmazania"
                    ],
                    "retention": "Až do zmazania používateľom",
                    "recommended": False
                },
                {
                    "id": "encrypted",
                    "name": "🔐 Šifrovaný",
                    "description": "Historia sa ukladá s end-to-end šifrovaním.",
                    "features": [
                        "✅ Všetky výhody trvalého módu",
                        "✅ End-to-end šifrovanie",
                        "✅ Ani admin servera nemôže čítať správy",
                        "✅ Váš kľúč = vaša kontrola",
                        "❌ Stratený kľúč = stratené dáta"
                    ],
                    "retention": "Šifrované až do zmazania",
                    "recommended": False
                }
            ],
            "gdpr_info": {
                "right_to_delete": "Máte právo kedykoľvek zmazať všetky svoje dáta",
                "right_to_export": "Môžete exportovať svoje dáta v JSON formáte", 
                "right_to_portability": "Vaše dáta sú exportovateľné",
                "contact": "privacy@klidbot.com"
            }
        }
    
    def set_user_privacy_choice(self, session_id: str, mode: str, user_consent: Dict) -> bool:
        """Nastaví privacy voľbu používateľa"""
        try:
            privacy_mode = PrivacyMode(mode)
            self.user_privacy_choices[session_id] = {
                'mode': privacy_mode,
                'timestamp': time.time(),
                'consent': user_consent,
                'ip_hash': user_consent.get('ip_hash'),
                'user_agent_hash': user_consent.get('user_agent_hash')
            }
            return True
        except ValueError:
            return False
    
    def get_user_privacy_mode(self, session_id: str) -> Optional[PrivacyMode]:
        """Získa privacy mód pre session"""
        choice = self.user_privacy_choices.get(session_id)
        return choice['mode'] if choice else None
    
    def store_message(self, session_id: str, role: str, content: str, 
                     crisis_detected: bool = False) -> bool:
        """Uloží správu podľa zvoleného privacy módu"""
        privacy_mode = self.get_user_privacy_mode(session_id)
        
        if not privacy_mode:
            # Default to ephemeral if no choice made
            privacy_mode = PrivacyMode.EPHEMERAL
        
        message_data = {
            'role': role,
            'content': content,
            'timestamp': time.time(),
            'crisis_detected': crisis_detected
        }
        
        if privacy_mode == PrivacyMode.EPHEMERAL:
            return self._store_ephemeral(session_id, message_data)
        elif privacy_mode == PrivacyMode.TEMPORARY:
            return self._store_temporary(session_id, message_data)
        elif privacy_mode == PrivacyMode.PERSISTENT:
            return self._store_persistent(session_id, message_data)
        elif privacy_mode == PrivacyMode.ENCRYPTED:
            return self._store_encrypted(session_id, message_data)
        
        return False
    
    def _store_ephemeral(self, session_id: str, message_data: Dict) -> bool:
        """Uloží do pamäte - zmaže sa pri reštarte servera"""
        if session_id not in self.ephemeral_sessions:
            self.ephemeral_sessions[session_id] = []
        
        # Udržuj max 20 správ v pamäti
        if len(self.ephemeral_sessions[session_id]) >= 20:
            self.ephemeral_sessions[session_id].pop(0)
        
        self.ephemeral_sessions[session_id].append(message_data)
        return True
    
    def _store_temporary(self, session_id: str, message_data: Dict) -> bool:
        """Uloží s 24h expiration"""
        # Tu by si použil databázu s TTL (Time To Live)
        expiration = time.time() + (24 * 60 * 60)  # 24 hodín
        
        if session_id not in self.temporary_sessions:
            self.temporary_sessions[session_id] = {
                'messages': [],
                'expires_at': expiration
            }
        
        self.temporary_sessions[session_id]['messages'].append(message_data)
        return True
    
    def _store_persistent(self, session_id: str, message_data: Dict) -> bool:
        """Uloží do databázy natrvalo"""
        # Tu by si použil tvoju databázovú vrstvu
        print(f"Storing persistent message for {session_id}")
        return True
    
    def _store_encrypted(self, session_id: str, message_data: Dict) -> bool:
        """Uloží šifrované s používateľovým kľúčom"""
        # Tu by bolo end-to-end šifrovanie
        print(f"Storing encrypted message for {session_id}")
        return True
    
    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Získa históriu podľa privacy módu"""
        privacy_mode = self.get_user_privacy_mode(session_id)
        
        if privacy_mode == PrivacyMode.EPHEMERAL:
            return self.ephemeral_sessions.get(session_id, [])[-limit:]
        elif privacy_mode == PrivacyMode.TEMPORARY:
            session_data = self.temporary_sessions.get(session_id)
            if session_data and time.time() < session_data['expires_at']:
                return session_data['messages'][-limit:]
            else:
                # Expired, clean up
                if session_id in self.temporary_sessions:
                    del self.temporary_sessions[session_id]
                return []
        elif privacy_mode in [PrivacyMode.PERSISTENT, PrivacyMode.ENCRYPTED]:
            # Tu by si načítal z databázy
            return []
        
        return []
    
    def delete_user_data(self, session_id: str, delete_scope: str = "session") -> Dict:
        """
        Zmaže dáta používateľa podľa rozsahu
        delete_scope: "session" | "all" | "everything"
        """
        result = {
            'deleted_sessions': 0,
            'deleted_messages': 0,
            'deleted_from': [],
            'permanent': True
        }
        
        privacy_mode = self.get_user_privacy_mode(session_id)
        
        if delete_scope == "session":
            # Zmaž len aktuálnu session
            if privacy_mode == PrivacyMode.EPHEMERAL:
                if session_id in self.ephemeral_sessions:
                    result['deleted_messages'] = len(self.ephemeral_sessions[session_id])
                    del self.ephemeral_sessions[session_id]
                    result['deleted_from'].append('memory')
            
            elif privacy_mode == PrivacyMode.TEMPORARY:
                if session_id in self.temporary_sessions:
                    result['deleted_messages'] = len(self.temporary_sessions[session_id]['messages'])
                    del self.temporary_sessions[session_id]
                    result['deleted_from'].append('temporary_storage')
            
            elif privacy_mode in [PrivacyMode.PERSISTENT, PrivacyMode.ENCRYPTED]:
                # Tu by si zmazal z databázy
                result['deleted_from'].append('database')
                result['deleted_messages'] = self._delete_from_database(session_id)
            
            result['deleted_sessions'] = 1
        
        elif delete_scope == "everything":
            # Zmaž všetko vrátane z Microsoft Azure, logov, backupov
            result['deleted_from'] = [
                'memory', 'temporary_storage', 'database', 
                'azure_logs', 'backups', 'analytics'
            ]
            result['deleted_sessions'] = self._delete_everything(session_id)
        
        # Zmaž aj privacy choice
        if session_id in self.user_privacy_choices:
            del self.user_privacy_choices[session_id]
        
        return result
    
    def _delete_from_database(self, session_id: str) -> int:
        """Zmaže z databázy a všetkých súvisiacich tabuliek"""
        # Tu by bola implementácia mazania z databázy
        print(f"Deleting from database: {session_id}")
        return 0
    
    def _delete_everything(self, session_id: str) -> int:
        """Kompletné vymazanie zo všetkých systémov"""
        print(f"Complete deletion requested for: {session_id}")
        # Tu by bolo:
        # 1. Zmazanie z databázy
        # 2. Zmazanie z Azure logs
        # 3. Zmazanie z backup systémov
        # 4. Zmazanie z analytics
        # 5. Notifikácia všetkých systémov
        return 1
    
    def export_user_data(self, session_id: str) -> Dict:
        """Exportuje všetky dáta používateľa pre GDPR compliance"""
        privacy_mode = self.get_user_privacy_mode(session_id)
        
        export_data = {
            'export_timestamp': time.time(),
            'export_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'session_id': session_id[:8] + "...",  # Partial pre anonymitu
            'privacy_mode': privacy_mode.value if privacy_mode else 'ephemeral',
            'conversation_history': self.get_conversation_history(session_id),
            'privacy_choices': self.user_privacy_choices.get(session_id, {}),
            'gdpr_rights': {
                'right_to_delete': 'You can delete all your data anytime',
                'right_to_rectification': 'You can correct inaccurate data',
                'right_to_portability': 'This export fulfills your portability rights'
            }
        }
        
        return export_data
    
    def cleanup_expired_data(self):
        """Vyčistí expired temporary sessions"""
        current_time = time.time()
        expired_sessions = []
        
        for session_id, data in self.temporary_sessions.items():
            if current_time > data['expires_at']:
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del self.temporary_sessions[session_id]
            print(f"Auto-deleted expired session: {session_id}")
        
        return len(expired_sessions)

# ========================================
# FLASK ROUTES PRE PRIVACY CONTROL
# ========================================

app = Flask(__name__)
privacy_manager = PrivacyManager()

@app.route('/privacy/options', methods=['GET'])
def get_privacy_options():
    """Vráti dostupné privacy možnosti"""
    return jsonify(privacy_manager.get_privacy_options())

@app.route('/privacy/choose', methods=['POST'])
def choose_privacy_mode():
    """Používateľ si vyberie privacy mód"""
    data = request.get_json()
    session_id = session.get('session_id', str(uuid.uuid4()))
    
    privacy_mode = data.get('mode')
    user_consent = {
        'explicit_consent': data.get('consent', False),
        'timestamp': time.time(),
        'ip_hash': hash(request.remote_addr) if request.remote_addr else None,
        'user_agent_hash': hash(request.headers.get('User-Agent', ''))
    }
    
    if privacy_manager.set_user_privacy_choice(session_id, privacy_mode, user_consent):
        session['session_id'] = session_id
        return jsonify({
            'success': True,
            'session_id': session_id[:8] + "...",
            'mode': privacy_mode,
            'message': f'Privacy mód "{privacy_mode}" bol nastavený.',
            'data_retention': privacy_manager.get_privacy_options()['modes'][0]['retention']
        })
    else:
        return jsonify({'success': False, 'error': 'Invalid privacy mode'}), 400

@app.route('/privacy/delete', methods=['POST'])
def delete_user_data():
    """Zmaže dáta používateľa"""
    data = request.get_json()
    session_id = session.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    delete_scope = data.get('scope', 'session')  # session | all | everything
    confirmation = data.get('confirmation', False)
    
    if not confirmation:
        return jsonify({'error': 'Confirmation required'}), 400
    
    result = privacy_manager.delete_user_data(session_id, delete_scope)
    
    # Clear session after deletion
    session.clear()
    
    return jsonify({
        'success': True,
        'deletion_result': result,
        'message': 'Vaše dáta boli úspešne zmazané.',
        'permanent': True,
        'confirmation_id': str(uuid.uuid4())[:8]
    })

@app.route('/privacy/export', methods=['GET'])
def export_user_data():
    """Exportuje dáta používateľa"""
    session_id = session.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'No active session'}), 400
    
    export_data = privacy_manager.export_user_data(session_id)
    
    return jsonify({
        'success': True,
        'export_data': export_data,
        'download_filename': f'klidbot_export_{int(time.time())}.json'
    })

@app.route('/privacy/status', methods=['GET'])
def get_privacy_status():
    """Získa aktuálny privacy status"""
    session_id = session.get('session_id')
    
    if not session_id:
        return jsonify({
            'has_session': False,
            'mode': 'ephemeral',
            'message': 'No active session - defaulting to ephemeral mode'
        })
    
    privacy_mode = privacy_manager.get_user_privacy_mode(session_id)
    history_count = len(privacy_manager.get_conversation_history(session_id))
    
    return jsonify({
        'has_session': True,
        'session_id': session_id[:8] + "...",
        'mode': privacy_mode.value if privacy_mode else 'ephemeral',
        'messages_stored': history_count,
        'can_delete': True,
        'can_export': history_count > 0
    })

# Background cleanup job
import threading
def background_cleanup():
    while True:
        time.sleep(3600)  # Každú hodinu
        privacy_manager.cleanup_expired_data()

cleanup_thread = threading.Thread(target=background_cleanup, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    app.run(debug=True)
