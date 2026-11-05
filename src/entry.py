import base64
from email.message import EmailMessage
from pydoc import text
from urllib.parse import urlencode

from requests import post

from js import fetch, Object
from pyodide.ffi import to_js

from workers import WorkerEntrypoint, response

from datetime import datetime, timedelta, timezone

import trafilatura

RECIPIENT = "pabrizzo@gmail.com"

async def gmail_request(url, options):
    return await fetch(
        url,
        to_js(options, dict_converter=Object.fromEntries),
    )


async def send_test_email(env):
    # 1. Ottieni un access token usando il refresh token
    token_response = await gmail_request(
        "https://oauth2.googleapis.com/token",
        {
            "method": "POST",
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded"
            },
            "body": urlencode({
                "client_id": env.GMAIL_CLIENT_ID,
                "client_secret": env.GMAIL_CLIENT_SECRET,
                "refresh_token": env.GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            }),
        },
    )

    if not token_response.ok:
        error = await token_response.text()
        raise RuntimeError(f"OAuth error: {error}")

    token_data = await token_response.json()
    access_token = token_data.access_token

    # 2. Prepara il messaggio MIME
    message = EmailMessage()
    message["To"] = RECIPIENT
    message["From"] = RECIPIENT
    message["Subject"] = "Test Lemmy Daily Digest"
    message.set_content(
        "Ciao!\n\n"
        "Questa è un'email di prova del progetto Lemmy Daily Digest.\n\n"
        "L'invio tramite Gmail API e Cloudflare Workers funziona!\n"
    )

    encoded_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("ascii")

    # 3. Invia tramite Gmail API
    gmail_response = await gmail_request(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
        {
            "method": "POST",
            "headers": {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            "body": __import__("json").dumps({
                "raw": encoded_message
            }),
        },
    )

    if not gmail_response.ok:
        error = await gmail_response.text()
        raise RuntimeError(f"Gmail API error: {error}")

    result = await gmail_response.json()
    print(f"Email inviata! Message ID: {result.id}")


async def fetch_lemmy_posts():
    url = (
        "https://lemmy.world/api/v3/post/list"
        "?community_name=world&sort=New&limit=50"
    )

    response = await gmail_request(
        url,
        {
            "method": "GET",
            "headers": {
                "Accept": "application/json",
                "User-Agent": "LemmyDailyDigest/1.0",
            },
        },
    )

    if not response.ok:
        error = await response.text()
        raise RuntimeError(f"Lemmy API error: {error}")

    data = (await response.json()).to_py()

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    recent_posts = []

    for item in data.get("posts", []):
        post = item["post"]

        published = datetime.fromisoformat(
            post["published"].replace("Z", "+00:00")
        )

        if published >= cutoff and post.get("url"):
            recent_posts.append({
                "id": post["id"],
                "title": post["name"],
                "url": post.get("url"),
                "body": post.get("body"),
                "published": post["published"],
                "creator": item["creator"]["name"],
            })

    return recent_posts

async def fetch_article(url):
    try:
        response = await gmail_request(
            url,
            {
                "method": "GET",
                "headers": {
                    "User-Agent": "LemmyDailyDigest/1.0",
                    "Accept": "text/html",
                },
            },
        )

        if not response.ok:
            return {
                "url": url,
                "text": None,
                "error": f"HTTP {response.status}",
            }

        html = await response.text()

        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )

        if not text:
            return {
                "url": response.url,
                "text": None,
                "error": "Nessun contenuto estraibile",
            }

        return {
            "url": response.url,
            "text": text,
            "error": None,
        }

    except Exception as error:
        return {
            "url": url,
            "text": None,
            "error": str(error),
        }


class Default(WorkerEntrypoint):
    async def scheduled(self, controller, env, ctx):
        #print(f"Trafilatura version: {trafilatura.__version__}")
        print("Recupero post da Lemmy...")
        posts = await fetch_lemmy_posts()

        print(f"Post trovati: {len(posts)}")

        articles = []
        
        for post in posts:
            article = await fetch_article(post["url"])

            articles.append({"title": post["title"],"url": article["url"],"text": article["text"], "error": article["error"],})

            if article["text"]:
                print(f"OK: {post['title']}")
                print(f"Caratteri estratti: {len(article['text'])}")
            else:
                print(f"ERRORE: {post['title']}")
                print(f"Motivo: {article['error']})")

        successful = sum(1 for a in articles if a["text"])
        failed = len(articles) - successful

        print(f"Articoli estratti: {successful}")
        print(f"Articoli non accessibili: {failed}")
        
        print("Test completato.")

    '''
    async def scheduled(self, controller, env, ctx):
        print("Recupero post da Lemmy...")

        posts = await fetch_lemmy_posts()

        print(f"Post trovati nelle ultime 24 ore: {len(posts)}")

        for post in posts:
            print(f"- {post['title']}")
            print(f"  Fonte: {post['url']}")

        print("Recupero completato.")
    '''

    '''
    async def scheduled(self, controller, env, ctx):
        print("Invio email di prova...")

        await send_test_email(self.env)

        print("Test completato.")
    '''