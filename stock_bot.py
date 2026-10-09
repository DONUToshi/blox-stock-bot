"""
Bot de Stock do Blox Fruits -> Discord

Lê https://fruityblox.com/stock, confere se alguma fruta da sua lista está no
Stock Normal ou no Mirage e avisa por webhook do Discord.

Variáveis de ambiente:
  DISCORD_WEBHOOK_URL  (obrigatória) URL do webhook do canal do Discord
  WATCH_FRUITS         (opcional) frutas separadas por vírgula. Padrão: magnet

Uso:
  python stock_bot.py          # execução normal
  python stock_bot.py --test   # só manda uma mensagem de teste ao Discord
"""

import json
import os
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

URL = "https://fruityblox.com/stock"
BASE = "https://fruityblox.com"
STATE_FILE = Path(__file__).parent / "state.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; blox-stock-notifier/1.0; uso pessoal)"
}
SECTIONS = {"normal": "Normal", "mirage": "Mirage"}


def fetch_stock():
    """Retorna {'normal': {slug: info}, 'mirage': {slug: info}}."""
    resp = requests.get(URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    stock = {key: {} for key in SECTIONS}
    current = None

    # Percorre a página em ordem: cada título (Normal/Mirage) abre uma seção
    # e os links /items/<fruta> seguintes pertencem a ela.
    for el in soup.find_all(["h1", "h2", "h3", "a"]):
        if el.name in ("h1", "h2", "h3"):
            title = el.get_text(strip=True).lower()
            if title in SECTIONS:
                current = title
            continue

        href = el.get("href", "")
        if current and "/items/" in href:
            slug = href.rstrip("/").split("/items/")[-1].lower()
            text = el.get_text(" ", strip=True)
            numbers = re.findall(r"\d[\d.,]*", text)
            stock[current][slug] = {
                "name": slug.replace("-", " ").title(),
                "beli": numbers[-2] if len(numbers) >= 2 else "?",
                "robux": numbers[-1] if numbers else "?",
                "url": href if href.startswith("http") else BASE + href,
            }
    return stock


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {key: [] for key in SECTIONS}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_discord(content):
    webhook = os.environ["DISCORD_WEBHOOK_URL"]
    r = requests.post(webhook, json={"content": content}, timeout=30)
    r.raise_for_status()


def main():
    if "--test" in sys.argv:
        send_discord("✅ Teste: o bot do Blox Fruits está conectado ao Discord.")
        print("Mensagem de teste enviada.")
        return

    watch = {
        f.strip().lower().replace(" ", "-")
        for f in os.environ.get("WATCH_FRUITS", "magnet").split(",")
        if f.strip()
    }

    stock = fetch_stock()

    # Se a página mudou e nada foi lido, falha de propósito para você ser avisado
    # (o GitHub manda e-mail quando um workflow falha) e o estado não é sobrescrito.
    if not any(stock.values()):
        print("Nenhuma fruta encontrada: o layout do site pode ter mudado.")
        sys.exit(1)

    previous = load_state()
    new_state = {}
    alerts = []

    for key, label in SECTIONS.items():
        current_slugs = set(stock[key])
        new_state[key] = sorted(current_slugs)
        # só avisa se a fruta é nova no stock desde a última checagem
        fresh = (current_slugs & watch) - set(previous.get(key, []))
        for slug in sorted(fresh):
            info = stock[key][slug]
            alerts.append(
                f"🍎 **{info['name']}** está no Stock **{label}**!\n"
                f"Preço: {info['beli']} Beli ou {info['robux']} Robux\n"
                f"{info['url']}"
            )

    for msg in alerts:
        send_discord(msg)
        print("Alerta enviado:", msg.splitlines()[0])

    if not alerts:
        print("Nenhuma fruta de interesse nova no stock.")

    save_state(new_state)


if __name__ == "__main__":
    main()
