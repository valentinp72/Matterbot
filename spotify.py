import re
import json
import requests
from mattermostdriver import Driver

with open("mattermost_config.json", "r") as f:
    mattermost_config = json.load(f)

mattermost = Driver(mattermost_config)
mattermost.login()

ME = mattermost.users.get_user(user_id='me')['id']
URL_MATCHER = re.compile(r"(?P<url>https?://[^\s\?]+)")

def get_spotify(url):
    x = requests.get(url)
    x = x.text
    twitter_image = re.findall(r'<meta name="twitter:image" content="([^\"]*)"\/>', x)
    twitter_title = re.findall(r'<meta name="twitter:title" content="([^\"]*)"\/>', x)
    twitter_description = re.findall(r'<meta name="twitter:description" content="([^\"]*)"\/>', x)

    if len(twitter_image) == 1 and len(twitter_title) == 1 and len(twitter_description) == 1:
        return {'image': twitter_image[0], 'title': twitter_title[0], 'description': twitter_description[0]}
    else:
        print("Erreur dans le parsing de la requête.")
        print(twitter_title)
        print(twitter_description)
        print(twitter_image)
        return None

async def event_handler(message):
    message = json.loads(message)
    if not "event" in message or message["event"] != "posted":
        return
    if "data" in message and "post" in message["data"]:
        post = json.loads(message["data"]["post"])
        if not "message" in post:
            return
        if post["user_id"] == ME:
            return
        text = post["message"]
        message_id = post["id"]

        if "https://open.spotify.com/track/" in text:
            url = URL_MATCHER.search(text).group("url")
            spotify = get_spotify(url)
            if spotify is None:
                return
            answer = f"![{spotify['title']}]({spotify['image']} =100)\n"
            answer += f"[**{spotify['title']}**]({url})\n"
            answer += f"{spotify['description']}"

            mattermost.posts.create_post(
                options={
                    'channel_id': post["channel_id"],
                    'parent_id': message_id,
                    'root_id': message_id,
                    'message': answer,
                }
            )

mattermost.init_websocket(event_handler)
