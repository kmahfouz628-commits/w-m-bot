import requests

def send(token, chat_id, text):
    if not token or not chat_id:
        raise RuntimeError('Telegram credentials missing')
    r = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat_id, 'text': text},
        timeout=15
    )
    r.raise_for_status()
