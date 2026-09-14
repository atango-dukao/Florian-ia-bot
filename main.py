import os
import base64
import time
from threading import Thread
from flask import Flask
import requests

# Lecture des clés configurées dans Render
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "VOTRE_TOKEN_TELEGRAM_ICI")
GEMINI_KEY = os.getenv("GEMINI_KEY", "VOTRE_CLE_GEMINI_ICI")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
TELEGRAM_FILE_URL = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_KEY}"

app = Flask(__name__)

@app.route('/')
def home():
    return "Florian IA est en ligne 24h/24 !"

def lancer_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

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
    """Interroge Gemini 3.6 Flash avec texte et/ou fichier multimédia."""
    headers = {"Content-Type": "application/json"}
    consignes = (
        "Tu es Florian IA, un assistant virtuel d'élite, intelligent, courtois et polyvalent sur Telegram.\n"
        "Tu as des capacités multimodales avancées : tu peux écouter et comprendre des fichiers audio et notes vocales, "
        "lire et analyser des images ou photos d'exercices/documents, lire des PDF et analyser des vidéos.\n\n"
        "RÈGLES D'AFFICHAGE STRICTES POUR MOBILE :\n"
        "1. N'utilise JAMAIS de syntaxe LaTeX (interdit d'utiliser les symboles $, $$, \\frac, \\text, etc.).\n"
        "2. Écris les formules mathématiques et scientifiques en texte clair et naturel (ex: f' = 1/25 = 4 cm).\n"
        "3. N'utilise pas de dièses (pas de ###). Utilise des titres simples en MAJUSCULES et des puces claires (- ou •).\n"
        "4. Sois structuré, chaleureux et direct.\n"
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
            "\n[FICHIER REÇU] Analyse attentivement le fichier multimédia joint. "
            "S'il s'agit d'un message vocal ou audio, écoute-le et réponds précisément à ce qui est dit. "
            "S'il s'agit d'une image, d'un PDF ou d'une vidéo, résous ou explique ce qui est demandé."
        )

    consigne_demande = texte_utilisateur if texte_utilisateur else "(L'utilisateur a envoyé ce fichier sans texte, analyse-le directement et donne-lui une réponse complète)"
    prompt_final = f"{consignes}\n\nDemande de l'utilisateur : {consigne_demande}"
    parts.append({"text": prompt_final})

    payload = {"contents": [{"parts": parts}]}

    try:
        reponse = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=60)
        reponse_json = reponse.json()
        if "candidates" in reponse_json and len(reponse_json["candidates"]) > 0:
            return reponse_json["candidates"][0]["content"]["parts"][0]["text"]
        if "error" in reponse_json:
            msg = reponse_json["error"].get("message", "Erreur inconnue")
            return f"Problème technique : {msg}"
        return "Je n'ai pas pu analyser ce contenu pour le moment."
    except Exception as e:
        return f"Erreur de communication avec l'IA : {e}"

def envoyer_message(chat_id, texte):
    """Envoie un message texte sur Telegram avec découpage si nécessaire."""
    url = f"{TELEGRAM_URL}/sendMessage"
    limite = 4000
    for i in range(0, len(texte), limite):
        payload = {"chat_id": chat_id, "text": texte[i:i + limite]}
        try:
            requests.post(url, data=payload, timeout=10)
        except Exception as e:
            print(f"Erreur envoi Telegram : {e}")

def boucle_telegram():
    print("Florian IA - Mode Multimodal actif 24h/24.")
    dernier_id = 0
    while True:
        try:
            url = f"{TELEGRAM_URL}/getUpdates?offset={dernier_id + 1}&timeout=30"
            res = requests.get(url, timeout=35).json()

            for update in res.get("result", []):
                dernier_id = update["update_id"]
                message = update.get("message")
                if not message:
                    continue

                chat_id = message["chat"]["id"]
                texte_recu = message.get("text") or message.get("caption", "")

                file_id = None
                mime_type = None

                # 1. Message vocal (voice note)
                if "voice" in message:
                    file_id = message["voice"]["file_id"]
                    mime_type = message["voice"].get("mime_type", "audio/ogg")
                    if "ogg" in mime_type or "opus" in mime_type:
                        mime_type = "audio/ogg"

                # 2. Fichier audio (musique ou chanson)
                elif "audio" in message:
                    file_id = message["audio"]["file_id"]
                    mime_type = message["audio"].get("mime_type", "audio/mpeg")

                # 3. Photo
                elif "photo" in message:
                    file_id = message["photo"][-1]["file_id"]
                    mime_type = "image/jpeg"

                # 4. Document (PDF, Word, fichier)
                elif "document" in message:
                    doc = message["document"]
                    file_id = doc["file_id"]
                    mime_type = doc.get("mime_type", "application/pdf")

                # 5. Vidéo
                elif "video" in message:
                    file_id = message["video"]["file_id"]
                    mime_type = message["video"].get("mime_type", "video/mp4")

                # Commande /start
                if texte_recu == "/start":
                    bienvenue = (
                        "Salutations ! Je suis Florian IA, votre assistant virtuel complet.\n\n"
                        "Voici tout ce que je peux faire pour vous 24h/24 :\n"
                        "• Répondre à vos questions écrites.\n"
                        "• Écouter vos messages vocaux et fichiers audio.\n"
                        "• Résoudre les exercices sur vos photos et images.\n"
                        "• Lire et résumer vos documents et fichiers PDF.\n"
                        "• Visionner et analyser vos vidéos.\n\n"
                        "Envoyez-moi simplement votre question ou votre fichier !"
                    )
                    envoyer_message(chat_id, bienvenue)
                    continue

                # Si ni texte ni fichier, ignorer
                if not texte_recu and not file_id:
                    continue

                # Télécharger le média si présent
                media_b64 = None
                if file_id:
                    requests.post(f"{TELEGRAM_URL}/sendChatAction", data={"chat_id": chat_id, "action": "typing"}, timeout=5)
                    media_b64 = telecharger_fichier_telegram(file_id)
                    if not media_b64:
                        envoyer_message(chat_id, "Désolé, je n'ai pas pu récupérer ce fichier (la taille maximale autorisée par Telegram pour les bots est de 20 Mo).")
                        continue

                # Appel à Gemini avec le texte et/ou le fichier
                reponse = demander_a_gemini(texte_recu, media_b64=media_b64, mime_type=mime_type)
                envoyer_message(chat_id, reponse)

        except Exception as e:
            print("Erreur de boucle Telegram :", e)
            time.sleep(3)

if __name__ == "__main__":
    Thread(target=lancer_web).start()
    boucle_telegram()
      "3. Pas de dièses (pas de ###). Utilise des titres simples et des tirets"
      " (-).\n\n"
      f"Message : {texte_utilisateur}"
  )
  payload = {"contents": [{"parts": [{"text": consignes}]}]}
  try:
    r = requests.post(GEMINI_URL, headers=headers, json=payload, timeout=30)
    data = r.json()
    if "candidates" in data and len(data["candidates"]) > 0:
      return data["candidates"][0]["content"]["parts"][0]["text"]
    return "Je n'ai pas pu générer de réponse pour le moment."
  except Exception as e:
    return f"Erreur de connexion : {e}"


def envoyer_message(chat_id, texte):
  url = f"{TELEGRAM_URL}/sendMessage"
  limite = 4000
  for i in range(0, len(texte), limite):
    payload = {"chat_id": chat_id, "text": texte[i : i + limite]}
    try:
      requests.post(url, data=payload, timeout=10)
    except Exception as e:
      print(f"Erreur d'envoi : {e}")


def boucle_telegram():
  print("Boucle Telegram active.")
  dernier_id = 0
  while True:
    try:
      url = f"{TELEGRAM_URL}/getUpdates?offset={dernier_id + 1}&timeout=30"
      res = requests.get(url, timeout=35).json()
      for update in res.get("result", []):
        dernier_id = update["update_id"]
        msg = update.get("message")
        if not msg or "text" not in msg:
          continue

        chat_id = msg["chat"]["id"]
        texte = msg["text"]

        if texte == "/start":
          envoyer_message(
              chat_id,
              "Bonjour ! Je suis Florian IA, disponible 24h/24. Posez-moi vos"
              " questions !",
          )
        else:
          reponse = demander_a_gemini(texte)
          envoyer_message(chat_id, reponse)
    except Exception as e:
      print("Erreur Telegram :", e)
      time.sleep(3)


if __name__ == "__main__":
  # Lance le serveur web sur un fil d'exécution séparé
  Thread(target=lancer_web).start()
  # Lance le bot Telegram
  boucle_telegram()
