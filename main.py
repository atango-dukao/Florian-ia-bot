import os
from threading import Thread
import time
from flask import Flask
import requests

# Clés d'API (lues depuis les variables d'environnement ou en dur)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_KEY")

TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_KEY}"

# Mini-serveur web pour maintenir le bot actif sur l'hébergeur
app = Flask(__name__)


@app.route("/")
def home():
  return "Florian IA est en ligne 24h/24 !"


def lancer_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


def demander_a_gemini(texte_utilisateur):
  headers = {"Content-Type": "application/json"}
  consignes = (
      "Tu es Florian IA, un assistant personnel intelligent, clair et"
      " courtois.\n"
      "RÈGLES D'AFFICHAGE STRICTES POUR MOBILE :\n"
      "1. N'utilise JAMAIS de syntaxe LaTeX (pas de $, \\frac, \\text, etc.).\n"
      "2. Écris les formules mathématiques en texte naturel (ex : f' = 1/25 = 4"
      " cm).\n"
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
