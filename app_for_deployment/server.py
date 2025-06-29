from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from openai import OpenAI
import os
import uuid
import time
import re
import unicodedata

# Inicializácia aplikácie
app = Flask(__name__, static_folder='static')
app.secret_key = "openai-therapy-key"
CORS(app, supports_credentials=True, origins=[
    "https://asisterapie-bcbqhaawdqduavgq.westeurope-01.azurewebsites.net",
    "http://127.0.0.1:5000",  # pro local development
    "http://localhost:5000"   # pro local development
])

# Konfigurácia OpenAI API
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("⚠️ WARNING: OPENAI_API_KEY environment variable not set!")
    client = None
else:
    client = OpenAI(api_key=OPENAI_API_KEY)

# Nastavenie modelu
MODEL_NAME = 'gpt-3.5-turbo'  # alebo 'gpt-4' ak máte prístup
MODEL_AVAILABLE = bool(OPENAI_API_KEY and client)

# Uchovávanie konverzácií
conversations = {}

# Systémový prompt
THERAPY_SYSTEM_PROMPT = """You are Dr. Sarah Chen, an experienced licensed psychotherapist with over 15 years of practice specializing in cognitive-behavioral therapy, trauma-informed care, and crisis intervention. You provide compassionate, evidence-based mental health support in Slovak language.

IMPORTANT GUIDELINES:
- Always respond in Slovak language
- Be empathetic, warm, and professional
- Use person-centered approach
- Validate emotions and experiences
- Offer practical coping strategies when appropriate
- Maintain appropriate therapeutic boundaries
- If you detect crisis situation, prioritize safety and provide emergency resources
- Keep responses concise but meaningful (2-4 sentences usually)
- Use simple, accessible language
- Show genuine care and concern

You create a safe, non-judgmental space for people to share their thoughts and feelings."""

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

# --- VYLEPŠENÁ FUNKCIA NA DETEKCIU KRÍZY ---
def strip_accents(text):
    """Odstráni diakritiku z textu pre lepšie porovnávanie."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def detect_crisis_keywords(message):
    normalized_message = strip_accents(message.lower())
    crisis_keywords = [
        'suicide', 'suicidal', 'kill myself', 'end my life', 'want to die', 'better off dead', 'end it all', 'take my own life', 'hurt myself', 'cut myself', 'harm myself', 'self harm',
        'samovrazda', 'sebevrazda', 'zabijem sa', 'zabit sa', 'ukoncit zivot', 'chcem zomriet', 'chci umrit', 'ublizit si', 'uskodit si',
        'chcem to skoncit', 'chci to skoncit', 'nevladzem dalej', 'uz nemuzu', 'je po vsem', 'nema to zmysel', 'nema to smysl',
        'overdose', 'predavkoval', 'bad trip', 'halucinacie',
        'no point living', 'life is meaningless', 'cannot go on'
    ]
    
    if any(keyword in normalized_message for keyword in crisis_keywords):
        return True
    
    all_patterns = [
        r'myslim na (sebevrazd|samovrazd)',
        r'chci (spachat|spachat) (sebevrazd|samovrazd)',
        r'chcem (spachat|spachat) (sebevrazd|samovrazd)',
        r'chci (skocit|skoncit)',
        r'chcem (skocit|skoncit)',
        r'\bi want to (die|kill|hurt|harm)',
        r'\bi (wish|want) i (was|were) dead',
        r'\bi can\'?t (take|handle|deal with) (this|it) anymore',
        r'\blife isn\'?t worth',
        r'\bi (am|was) on [a-z]+',
        r'\bi took [a-z]+',
        r'\bi\'m (high|tripping|freaking)',
        r'\bseeing (fractals|patterns|colors)',
        r'\bhearing (things|voices)',
        r'\bcan\'?t (stop|come down|control)'
    ]
    
    return any(re.search(pattern, normalized_message) for pattern in all_patterns)

def generate_crisis_response_sequence():
    return [
        {"type": "validation", "content": "Ďakujem, že ste mi to povedali. Je to veľmi vážne a je dôležité, aby ste sa porozprávali s niekým, kto vám môže pomôcť práve teraz."},
        {"type": "resources_title", "content": "Tu sú kontakty na linky pomoci. Sú bezplatné, anonymné a dostupné nonstop:"},
        {"type": "resources_list", "content": "• **Ak ste v bezprostrednom ohrození, volajte 112**\n• **Linka dôvery Nezábudka (SK):** 0800 800 566\n• **Krízová linka pomoci (IPčko):** www.krizovalinkapomoci.sk (chat)\n• **Linka bezpečí (CZ):** 116 111"},
        {"type": "encouragement", "content": "Prosím, zvážte zavolanie alebo napísanie na jednu z týchto liniek. Sú tam ľudia, ktorí sú školení na to, aby vám pomohli."},
        {"type": "safety_check", "content": "Som tu s vami. Ste práve teraz v bezpečí?"}
    ]

def call_openai_api(user_message, conversation_history):
    if not MODEL_AVAILABLE or not client:
        print("❌ No OpenAI client available")
        return generate_fallback_response(user_message)
    
    try:
        # Pripravenie messages pre OpenAI API
        messages = [{"role": "system", "content": THERAPY_SYSTEM_PROMPT}]
        
        # Pridanie posledných 10 správ z histórie
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        for msg in recent_history:
            messages.append({
                "role": "user" if msg["role"] == "user" else "assistant",
                "content": msg["content"]
            })
        
        # Pridanie aktuálnej správy
        messages.append({"role": "user", "content": user_message})
        
        # Volanie OpenAI API
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=300,
            temperature=0.7,
            top_p=0.9,
            frequency_penalty=0.1,
            presence_penalty=0.1
        )
        
        if response.choices and len(response.choices) > 0:
            return response.choices[0].message.content.strip()
        else:
            print("❌ No choices in OpenAI response")
            return generate_fallback_response(user_message)
            
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg:
            print("❌ OpenAI API rate limit exceeded")
            return "Prepáčte, momentálne je server preťažený. Skúste to prosím o chvíľu."
        elif "invalid request" in error_msg:
            print(f"❌ OpenAI API Invalid Request: {e}")
            return generate_fallback_response(user_message)
        elif "authentication" in error_msg or "authorization" in error_msg:
            print("❌ OpenAI API Authentication failed")
            return "Chyba autentifikácie. Kontaktujte administrátora."
        else:
            print(f"❌ OpenAI API Error: {e}")
            return generate_fallback_response(user_message)

def generate_fallback_response(user_message):
    if any(word in user_message.lower() for word in ['ahoj', 'hello', 'hi', 'hey', 'dobry den']):
        return "Ahoj, som tu na to, aby som vám ponúkol podporu. Ako sa dnes cítite?"
    elif any(word in user_message.lower() for word in ['dakujem', 'thank', 'vďaka']):
        return "Nie je za čo. Som tu pre vás. Môžete mi povedať viac o tom, čo vás trápi?"
    else:
        return "Počujem vás a rozumiem, že prechádzate ťažkým obdobím. Môžete mi povedať viac o tom, čo sa deje?"

def list_available_models():
    """Vráti zoznam dostupných OpenAI modelov"""
    return ['gpt-3.5-turbo', 'gpt-4'] if MODEL_AVAILABLE else []

# ===== Frontend route =====
@app.route('/', methods=['GET'])
def frontend():
    """Servíruje frontend HTML aplikáciu"""
    try:
        return send_from_directory('static', 'index.html')
    except Exception as e:
        print(f"❌ Error serving frontend: {e}")
        return jsonify({
            "message": "Therapy Chatbot with OpenAI GPT", 
            "status": "healthy", 
            "mode": f"OpenAI {MODEL_NAME}",
            "available_models": list_available_models(),
            "features": ["Crisis detection", "Emergency resources", "Real AI responses"],
            "endpoints": {"health": "/health", "chat": "/chat", "new_session": "/new-session"},
            "frontend_error": "Could not load frontend HTML. Please check static/index.html file."
        })

@app.route('/api', methods=['GET'])
def api_info():
    """API informácie"""
    return jsonify({
        "message": "Therapy Chatbot with OpenAI GPT", 
        "status": "healthy", 
        "mode": f"OpenAI {MODEL_NAME}",
        "available_models": list_available_models(),
        "features": ["Crisis detection", "Emergency resources", "Real AI responses"],
        "endpoints": {"health": "/health", "chat": "/chat", "new_session": "/new-session"}
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "message": "OpenAI GPT therapy server is running",
        "mode": f"OpenAI {MODEL_NAME}", 
        "model_available": MODEL_AVAILABLE,
        "active_sessions": len(conversations)
    })

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data: 
            return jsonify({"error": "No data provided"}), 400
        
        user_message = data.get("message", "").strip()
        if not user_message: 
            return jsonify({"error": "Message is required"}), 400
        
        session_id = get_session_id()
        print(f"🤖 Session: {session_id} | 👤 User: {user_message}")

        # Kontrola krízy
        if detect_crisis_keywords(user_message):
            print(f"🚨 CRISIS DETECTED! Activating safety protocol for session {session_id}.")
            crisis_response_sequence = generate_crisis_response_sequence()
            
            if session_id not in conversations: 
                conversations[session_id] = []
            conversations[session_id].append({"role": "user", "content": user_message})
            
            full_crisis_text = "\n".join([msg["content"] for msg in crisis_response_sequence])
            conversations[session_id].append({"role": "assistant", "content": f"[CRISIS PROTOCOL ACTIVATED] {full_crisis_text}"})
            
            return jsonify({
                "response_sequence": crisis_response_sequence, 
                "session_id": session_id,
                "crisis_detected": True, 
                "powered_by": "Crisis Safety Protocol"
            })

        # Normálna konverzácia
        if session_id not in conversations: 
            conversations[session_id] = []
        
        conversations[session_id].append({"role": "user", "content": user_message})
        
        print(f"🔄 Calling OpenAI API ({MODEL_NAME})...")
        bot_reply = call_openai_api(user_message, conversations[session_id])
        print(f"🤖 OpenAI: {bot_reply[:100]}..." if len(bot_reply) > 100 else f"🤖 OpenAI: {bot_reply}")
        
        conversations[session_id].append({"role": "assistant", "content": bot_reply})
        
        # Obmedzenie histórie na posledných 20 správ
        if len(conversations[session_id]) > 20:
            conversations[session_id] = conversations[session_id][-20:]
        
        return jsonify({
            "response_sequence": [{"type": "standard", "content": bot_reply}], 
            "session_id": session_id,
            "powered_by": f"OpenAI {MODEL_NAME}", 
            "crisis_detected": False
        })
        
    except Exception as e:
        print(f"❌ Error in /chat: {e}")
        fallback = generate_fallback_response(user_message if 'user_message' in locals() else "hello")
        return jsonify({
            "response_sequence": [{"type": "fallback", "content": fallback}],
            "powered_by": "Fallback response", 
            "error": "Used backup system"
        })

@app.route('/new-session', methods=['POST'])
def new_session():
    try:
        if 'session_id' in session:
            if session['session_id'] in conversations: 
                del conversations[session['session_id']]
        session.clear()
        new_session_id = get_session_id()
        print(f"✨ New session created: {new_session_id}")
        return jsonify({"message": "New session started", "session_id": new_session_id})
    except Exception as e:
        print(f"❌ Error creating new session: {e}")
        return jsonify({"error": "Failed to create new session"}), 500

@app.route('/test-frontend', methods=['GET'])
def test_frontend():
    import os
    static_path = os.path.join(app.root_path, 'static')
    files = os.listdir(static_path) if os.path.exists(static_path) else []
    return jsonify({
        "static_folder": app.static_folder,
        "static_path": static_path,
        "static_files": files,
        "index_exists": os.path.exists(os.path.join(static_path, 'index.html'))
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

# Pre Azure App Service
if __name__ == '__main__':
    print("=" * 80)
    print("🩺 DR. SARAH CHEN - AI THERAPY PRACTICE (v3.0)")
    print("=" * 80)
    print(f"🧠 AI Model: OpenAI {MODEL_NAME}")
    print(f"🔗 Model Available: {'Yes' if MODEL_AVAILABLE else 'No'}")
    print("🚨 Crisis Protocol: Enhanced Detection")
    print("🌐 Starting Azure App Service with Frontend...")
    print("=" * 80)
    
    port = int(os.environ.get('PORT', 8000))
    app.run(debug=False, host="0.0.0.0", port=port)
