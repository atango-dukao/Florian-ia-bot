import os
import base64
import time
from threading import Thread, Lock
from flask import Flask
import requests

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "VOTRE_TOKEN_TELEGRAM_ICI")
GEMINI_KEYS_RAW = os.getenv("GEMINI_KEY", "VOTRE_CLE_GEMINI_ICI")
# Découpe les clés séparées par des virgules pour la rotation
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_RAW.split(",") if k.strip()]

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_FILE_URL = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"

app = Flask(__name__)

@app.route('/')
def home():
    return "Florian IA est en ligne 24h/24 !"

def lancer_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# Mécanisme de rotation équitable des clés
index_cle = 0
lock_cle = Lock()

def get_prochaine_cle():
    global index_cle
    with lock_cle:
        cle = GEMINI_KEYS[index_cle % len(GEMINI_KEYS)]
        index_cle += 1
        return cle

def telecharger_fichier_telegram(file_id):
    """Télécharge le fichier depuis Telegram et le convertit en Base64."""
    try:
        res = requests.get(f"{TELEGRAM_URL}/getFile?file_id={file_id}", timeout=20).json()
        if not res.get("ok"):
            return None
        file_path = res["result"]["file_path"]
        download_res = requests.get(f"{TELEGRAM_FILE_URL}/{file_path}", timeout=45)
        if download_res.status_code == 200:
            return base64.b64encode(download_res.content).decode("utf-8")
    except Exception as e:
        print(f"Erreur téléchargement fichier : {e}")
    return None

def demander_a_gemini(texte_utilisateur, media_b64=None, mime_type=None):
    """Interroge Gemini avec bascule automatique sur les clés suivantes si quota plein."""
    headers = {"Content-Type": "application/json"}
    consignes = (
        "Tu es Florian IA, un assistant virtuel d'élite, ultra-rapide, intelligent et polyvalent sur Telegram.\n"
        "Tu as des capacités multimodales : tu comprends les audios, notes vocales, photos, PDF et vidéos.\n\n"
        "RÈGLES D'AFFICHAGE POUR SMARTPHONE :\n"
        "1. N'utilise JAMAIS de syntaxe LaTeX (pas de $, $$, \\frac, \\text, etc.).\n"
        "2. Écris les formules scientifiques en texte naturel et lisible (ex: f' = 1/25 = 4 cm).\n"
        "3. Pas de dièses (pas de ###). Utilise des titres simples et des tirets (- ou •).\n"
        "4. Réponds en français de manière claire, dynamique et précise.\n"
    )

    parts = []
    if media_b64 and mime_type:
        parts.append({
            "inlineData": {
                "mimeType": mime_type,
                "data": media_b64
            }
        })
        consignes += (
            "\n[FICHIER REÇU] Analyse attentivement le fichier joint. "
            "S'il s'agit d'un vocal ou audio, écoute-le et réponds précisément. "
            "S'il s'agit d'une image, d'un PDF ou d'une vidéo, résous ou explique ce qui est demandé."
        )

    consigne_demande = texte_utilisateur if texte_utilisateur else "(Fichier envoyé sans texte : analyse-le directement et donne une réponse complète)"
    prompt_final = f"{consignes}\n\nDemande de l'utilisateur : {consigne_demande}"
    parts.append({"text": prompt_final})
    payload = {"contents": [{"parts": parts}]}

    # Essaie les clés disponibles en cas de saturation
    tentatives = max(len(GEMINI_KEYS), 1)
    for _ in range(tentatives):
        cle_actuelle = get_prochaine_cle()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={cle_actuelle}"
        try:
            reponse = requests.post(url, headers=headers, json=payload, timeout=40)
            reponse_json = reponse.json()
            if "candidates" in reponse_json and len(reponse_json["candidates"]) > 0:
                return reponse_json["candidates"][0]["content"]["parts"][0]["text"]
            if "error" in reponse_json:
                code = reponse_json["error"].get("code", 0)
                msg = reponse_json["error"].get("message", "Erreur")
                if code == 429 or "quota" in msg.lower():
                    # Bascule immédiate sur la clé suivante
                    continue
                return f"Problème technique : {msg}"
        except Exception as e:
            continue

    return "Florian IA reçoit énormément de messages à la seconde ! Merci de patienter quelques instants."

def envoyer_message(chat_id, texte):
    """Envoie un message sur Telegram avec découpage si nécessaire."""
    url = f"{TELEGRAM_URL}/sendMessage"
    limite = 4000
    for i in range(0, len(texte), limite):
        payload = {"chat_id": chat_id, "text": texte[i:i + limite]}
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"Erreur envoi Telegram : {e}")

def traiter_en_parallele(chat_id, texte_recu, file_id, mime_type):
    """Traite chaque message dans un fil séparé pour une réponse instantanée."""
    media_b64 = None
    if file_id:
        requests.post(f"{TELEGRAM_URL}/sendChatAction", data={"chat_id": chat_id, "action": "typing"}, timeout=5)
        media_b64 = telecharger_fichier_telegram(file_id)
        if not media_b64:
            envoyer_message(chat_id, "Désolé, ce fichier dépasse la limite autorisée de 20 Mo.")
            return

    reponse = demander_a_gemini(texte_recu, media_b64=media_b64, mime_type=mime_type)
    envoyer_message(chat_id, reponse)

def boucle_telegram():
    print("Florian IA - Mode Parallèle & Multi-clés actif.")
    dernier_id = 0

    bot_username = ""
    try:
        me = requests.get(f"{TELEGRAM_URL}/getMe", timeout=15).json()
        if me.get("ok"):
            bot_username = me["result"].get("username", "").lower()
            print(f"Bot identifié sous : @{bot_username}")
    except Exception as e:
        print("Erreur bot_username :", e)

    while True:
        try:
            url = f"{TELEGRAM_URL}/getUpdates?offset={dernier_id + 1}&timeout=30"
            res = requests.get(url, timeout=35).json()

            for update in res.get("result", []):
                dernier_id = update["update_id"]
                message = update.get("message")
                if not message:
                    continue

                chat = message.get("chat", {})
                chat_id = chat.get("id")
                chat_type = chat.get("type", "private")
                texte_recu = message.get("text") or message.get("caption", "")

                file_id = None
                mime_type = None

                if "voice" in message:
                    file_id = message["voice"]["file_id"]
                    mime_type = message["voice"].get("mime_type", "audio/ogg")
                    if "ogg" in mime_type or "opus" in mime_type:
                        mime_type = "audio/ogg"
                elif "audio" in message:
                    file_id = message["audio"]["file_id"]
                    mime_type = message["audio"].get("mime_type", "audio/mpeg")
                elif "photo" in message:
                    file_id = message["photo"][-1]["file_id"]
                    mime_type = "image/jpeg"
                elif "document" in message:
                    doc = message["document"]
                    file_id = doc["file_id"]
                    mime_type = doc.get("mime_type", "application/pdf")
                elif "video" in message:
                    file_id = message["video"]["file_id"]
                    mime_type = message["video"].get("mime_type", "video/mp4")

                # GESTION DES GROUPES
                if chat_type in ["group", "supergroup"]:
                    mention_bot = f"@{bot_username}" if bot_username else ""
                    est_reponse_au_bot = False
                    if "reply_to_message" in message:
                        expediteur = message["reply_to_message"].get("from", {})
                        if expediteur.get("is_bot") and expediteur.get("username", "").lower() == bot_username:
                            est_reponse_au_bot = True

                    est_tague = (mention_bot and mention_bot in texte_recu.lower()) or ("florian" in texte_recu.lower())
                    
                    # Ignore si on ne s'adresse pas directement au bot
                    if not est_tague and not est_reponse_au_bot and not texte_recu.startswith("/"):
                        continue

                    if mention_bot and mention_bot in texte_recu.lower():
                        texte_recu = texte_recu.lower().replace(mention_bot, "").strip()

                if texte_recu == "/start":
                    bienvenue = (
                        "Salutations ! Je suis Florian IA, votre assistant virtuel ultra-rapide.\n\n"
                        "Je réponds instantanément en privé (IB) et dans les groupes dès qu'on me tague !"
                    )
                    envoyer_message(chat_id, bienvenue)
                    continue

                if not texte_recu and not file_id:
                    continue

                # LANCEMENT EN PARALLÈLE : réponse instantanée garantie pour tout le monde
                Thread(
                    target=traiter_en_parallele,
                    args=(chat_id, texte_recu, file_id, mime_type)
                ).start()

        except Exception as e:
            print("Erreur Telegram :", e)
            time.sleep(2)

if __name__ == "__main__":
    Thread(target=lancer_web).start()
    boucle_telegram()
    
