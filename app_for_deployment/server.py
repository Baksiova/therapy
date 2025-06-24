from flask import Flask, request, jsonify, session
from flask_cors import CORS
import google.generativeai as genai
import uuid
import time
import re
import unicodedata

# Inicializácia aplikácie
app = Flask(__name__)
app.secret_key = "gemini-therapy-key"
CORS(app, supports_credentials=True)

# Konfigurácia Google Gemini
GEMINI_API_KEY = "AIzaSyBsnHofeQikg91qylDx0fb6TvuRQy4LBoE" # Nahraďte svojím kľúčom
genai.configure(api_key=GEMINI_API_KEY)

# Inicializácia Gemini modelu
try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    MODEL_NAME = 'gemini-1.5-flash'
except Exception as e:
    print(f"Failed to load 'gemini-1.5-flash': {e}. Trying 'gemini-pro'.")
    try:
        model = genai.GenerativeModel('gemini-pro')
        MODEL_NAME = 'gemini-pro'
    except Exception as e_pro:
        print(f"Failed to load 'gemini-pro': {e_pro}. No model available.")
        model = None
        MODEL_NAME = 'No model available'

# Uchovávanie konverzácií
conversations = {}

# Systémový prompt (bez zmeny)
THERAPY_SYSTEM_PROMPT = """You are Dr. Sarah Chen, an experienced licensed psychotherapist..."""

def get_session_id():
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    return session['session_id']

# --- VYLEPŠENÁ FUNKCIA NA DETEKCIU KRÍZY ---
def strip_accents(text):
    """Odstráni diakritiku z textu pre lepšie porovnávanie."""
    return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')

def detect_crisis_keywords(message):
    """
    VYLEPŠENÉ: Používa normalizáciu textu a rozšírený zoznam slov a vzorov
    pre oveľa spoľahlivejšiu detekciu.
    """
    # Normalizácia vstupu - odstránenie diakritiky a malé písmená
    normalized_message = strip_accents(message.lower())

    # Rozšírený zoznam kľúčových slov bez diakritiky
    crisis_keywords = [
        'suicide', 'suicidal', 'kill myself', 'end my life', 'want to die', 'better off dead', 'end it all', 'take my own life', 'hurt myself', 'cut myself', 'harm myself', 'self harm',
        'samovrazda', 'sebevrazda', 'zabijem sa', 'zabit sa', 'ukoncit zivot', 'chcem zomriet', 'chci umrit', 'ublizit si', 'uskodit si',
        'chcem to skoncit', 'chci to skoncit', 'nevladzem dalej', 'uz nemuzu', 'je po vsem', 'nema to zmysel', 'nema to smysl',
        'overdose', 'predavkoval', 'bad trip', 'halucinacie',
        'no point living', 'life is meaningless', 'cannot go on'
    ]

    # Priame porovnanie so zoznamom
    if any(keyword in normalized_message for keyword in crisis_keywords):
        return True

    # Rozšírené regulárne výrazy pre normalizovaný text
    all_patterns = [
        # Samovražda a sebapoškodzovanie
        r'myslim na (sebevrazd|samovrazd)',
        r'chci (spachat|spachat) (sebevrazd|samovrazd)',
        r'chcem (spachat|spachat) (sebevrazd|samovrazd)',
        r'chci (skocit|skoncit)',
        r'chcem (skocit|skoncit)',
        r'\bi want to (die|kill|hurt|harm)',
        r'\bi (wish|want) i (was|were) dead',
        r'\bi can\'?t (take|handle|deal with) (this|it) anymore',
        r'\blife isn\'?t worth',
        # Užívanie drog
        r'\bi (am|was) on [a-z]+',
        r'\bi took [a-z]+',
        r'\bi\'m (high|tripping|freaking)',
        r'\bseeing (fractals|patterns|colors)',
        r'\bhearing (things|voices)',
        r'\bcan\'?t (stop|come down|control)'
    ]

    # Prehľadávanie pomocou regulárnych výrazov
    return any(re.search(pattern, normalized_message) for pattern in all_patterns)

# (Ostatné funkcie zostávajú bez zmeny)
def generate_crisis_response_sequence():
    return [
        {"type": "validation", "content": "Ďakujem, že ste mi to povedali. Je to veľmi vážne a je dôležité, aby ste sa porozprávali s niekým, kto vám môže pomôcť práve teraz."},
        {"type": "resources_title", "content": "Tu sú kontakty na linky pomoci. Sú bezplatné, anonymné a dostupné nonstop:"},
        {"type": "resources_list", "content": "• **Ak ste v bezprostrednom ohrození, volajte 112**\n• **Linka dôvery Nezábudka (SK):** 0800 800 566\n• **Krízová linka pomoci (IPčko):** www.krizovalinkapomoci.sk (chat)\n• **Linka bezpečí (CZ):** 116 111"},
        {"type": "encouragement", "content": "Prosím, zvážte zavolanie alebo napísanie na jednu z týchto liniek. Sú tam ľudia, ktorí sú školení na to, aby vám pomohli."},
        {"type": "safety_check", "content": "Som tu s vami. Ste práve teraz v bezpečí?"}
    ]

def call_gemini_ai(user_message, conversation_history):
    if model is None:
        print("❌ No Gemini model available")
        return generate_fallback_response(user_message)
    try:
        context = THERAPY_SYSTEM_PROMPT + "\n\n"
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        if recent_history:
            context += "Previous conversation:\n"
            for msg in recent_history:
                context += f"{msg['role'].capitalize()}: {msg['content']}\n"
        context += f"\nCurrent user message: {user_message}\n\nPlease respond as a compassionate therapy assistant:"
        response = model.generate_content(context, generation_config=genai.types.GenerationConfig(temperature=0.7, max_output_tokens=300, top_p=0.8, top_k=40))
        if hasattr(response, 'text') and response.text:
            return response.text.strip()
        elif hasattr(response, 'candidates') and response.candidates:
            return response.candidates[0].content.parts[0].text.strip()
        else:
            print("❌ No text in Gemini response")
            return generate_fallback_response(user_message)
    except Exception as e:
        print(f"❌ Gemini API Error: {e}")
        return generate_fallback_response(user_message)

def generate_fallback_response(user_message):
    if any(word in user_message.lower() for word in ['hello', 'hi', 'hey']):
        return "Hello, I'm here to offer support. How are you feeling today?"
    return "I hear you, and it sounds like you're going through a lot. Can you tell me more about what's happening?"

def list_available_models():
    try:
        return [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
    except Exception as e:
        print(f"❌ Error listing models: {e}")
        return []

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        "message": "Therapy Chatbot with Google Gemini AI", "status": "healthy", "mode": f"GOOGLE {MODEL_NAME}",
        "available_models": list_available_models(),
        "features": ["Crisis detection", "Emergency resources", "Real AI responses"],
        "endpoints": {"health": "/health", "chat": "/chat", "new_session": "/new-session"}
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", "message": "Gemini AI therapy server is running",
        "mode": f"GOOGLE {MODEL_NAME}", "model_available": model is not None,
        "active_sessions": len(conversations)
    })

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data: return jsonify({"error": "No data provided"}), 400
        user_message = data.get("message", "").strip()
        if not user_message: return jsonify({"error": "Message is required"}), 400
        session_id = get_session_id()
        print(f"🤖 Session: {session_id} | 👤 User: {user_message}")

        # Krízový protokol sa teraz spúšťa oveľa spoľahlivejšie
        if detect_crisis_keywords(user_message):
            print(f"🚨 CRISIS DETECTED! Activating safety protocol for session {session_id}.")
            crisis_response_sequence = generate_crisis_response_sequence()
            if session_id not in conversations: conversations[session_id] = []
            conversations[session_id].append({"role": "user", "content": user_message})
            full_crisis_text = "\n".join([msg["content"] for msg in crisis_response_sequence])
            conversations[session_id].append({"role": "assistant", "content": f"[CRISIS PROTOCOL ACTIVATED] {full_crisis_text}"})
            return jsonify({
                "response_sequence": crisis_response_sequence, "session_id": session_id,
                "crisis_detected": True, "powered_by": "Crisis Safety Protocol"
            })

        if session_id not in conversations: conversations[session_id] = []
        conversations[session_id].append({"role": "user", "content": user_message})
        print(f"🔄 Calling Google Gemini AI ({MODEL_NAME})...")
        bot_reply = call_gemini_ai(user_message, conversations[session_id])
        print(f"🤖 Gemini: {bot_reply[:100]}..." if len(bot_reply) > 100 else f"🤖 Gemini: {bot_reply}")
        conversations[session_id].append({"role": "assistant", "content": bot_reply})
        if len(conversations[session_id]) > 20:
            conversations[session_id] = conversations[session_id][-20:]
        return jsonify({
            "response_sequence": [{"type": "standard", "content": bot_reply}], "session_id": session_id,
            "powered_by": f"Google {MODEL_NAME}", "crisis_detected": False
        })
    except Exception as e:
        print(f"❌ Error in /chat: {e}")
        fallback = generate_fallback_response(user_message if 'user_message' in locals() else "hello")
        return jsonify({
            "response_sequence": [{"type": "fallback", "content": fallback}],
            "powered_by": "Fallback response", "error": "Used backup system"
        })

@app.route('/new-session', methods=['POST'])
def new_session():
    try:
        if 'session_id' in session:
            if session['session_id'] in conversations: del conversations[session['session_id']]
        session.clear()
        new_session_id = get_session_id()
        print(f"✨ New session created: {new_session_id}")
        return jsonify({"message": "New session started", "session_id": new_session_id})
    except Exception as e:
        print(f"❌ Error creating new session: {e}")
        return jsonify({"error": "Failed to create new session"}), 500

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    print("=" * 80)
    print("🩺 DR. SARAH CHEN - AI THERAPY PRACTICE (v2.2 - Robust Crisis Detection)")
    print("=" * 80)
    print(f"🧠 AI Model: {MODEL_NAME}")
    print(f"🔗 Model Available: {'Yes' if model else 'No'}")
    print("🚨 Crisis Protocol: Sequential, Clear, Action-Oriented (Enhanced)")
    print("🌐 Server: http://127.0.0.1:5000")
    print("❤️ Health: http://127.0.0.1:5000/health")
    print("🛑 Press CTRL+C to stop")
    print("=" * 80)
    app.run(debug=True, host="127.0.0.1", port=5000)