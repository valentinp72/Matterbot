import re
import json
import requests

from mattermostdriver import Driver
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

with open("config.json", "r") as f:
    config = json.load(f)

mattermost = Driver(config['mattermost'])
mattermost.login()

ME = mattermost.users.get_user(user_id='me')['id']

auth_manager = SpotifyClientCredentials(**config['spotify'])
sp = spotipy.Spotify(auth_manager=auth_manager)

def answer_to_post(text, post):
    mattermost.posts.create_post(
        options={
            'channel_id': post["channel_id"],
            'parent_id': post["id"],
            'root_id': post["id"],
            'message': text,
        }
    )


class Command:

    def match(self, message):
        raise NotImplementedError

    def get_answer(self, message):
        raise NotImplementedError

    def get_help(self):
        raise NotImplementedError

    def match_and_answer(self, message):
        if self.match(message):
            answer = self.get_answer(message)
            return answer
        return None

class TextCommand(Command):

    def __init__(self, source_text, target_text, exact=True, case_sensitive=False, hide=False):
        self.source_text = source_text
        self.target_text = target_text
        self.exact = exact
        self.case_sensitive = case_sensitive
        self.hide = hide
        if not self.case_sensitive:
            self.source_text = self.source_text.lower()

    def match(self, message):
        if self.case_sensitive:
            message = message.lower()

        if self.exact:
            return message == self.source_text
        else:
            return self.source_text in message

    def get_answer(self, message):
        return self.target_text

    def get_help(self):
        if self.hide:
            return None
        return f"`{self.source_text}` : print `{self.target_text}`"

class HelpCommand(Command):

    def __init__(self, commands):
        self.commands = commands

    def match(self, message):
        return message.lower() == '@liumbot help'

    def get_help(self):
        return "`@liumbot help` : print this help message"

    def get_answer(self, message):
        answer = ""
        for command in self.commands:
            help_message = command.get_help()
            if help_message:
                answer += '- ' + help_message + "\n"
        return answer

class SpotifyCommand(Command):

    SPOTIFY_TRACK_MATCHER = re.compile(r"https://open\.spotify\.com/track/(?P<track_id>[^\s\?]+)")

    def match(self, message):
        return "https://open.spotify.com/track/" in message

    def get_answer(self, message):
        track_id = SpotifyCommand.SPOTIFY_TRACK_MATCHER.search(message).group("track_id")
        url = f"https://open.spotify.com/track/{track_id}"
        spotify = SpotifyCommand.get_spotify(track_id)

        if spotify is None:
            return
        answer = f"![{spotify['title']}]({spotify['image']} =100)\n"
        answer += f"[**{spotify['title']}**]({url})\n"
        answer += f"{spotify['description']}"
        return answer

    def get_help(self):
        return "`https://open.spotify.com/track/<<TRACK ID>>` : print the Spotify song info"

    @classmethod
    def get_spotify(cls, track_id):
        out = sp.track(track_id)

        if "album" in out and "images" in out['album']:
            return {
                'image': out['album']['images'][0]['url'],
                'description': out['album']['name'],
                'description': f"{out['album']['name']} - {out['artists'][0]['name']} - {out['album']['release_date']}",
                'title': out['name']
            }
        print("Erreur get_spotify")
        print(out)
        return None

commands = [
    TextCommand(source_text="ping", target_text="pong"),
    TextCommand(source_text="ping ping", target_text="pong pong"),
    TextCommand(source_text="ping ping ping", target_text="non mais ça va oui hein !"),
    TextCommand(source_text="pong", target_text="~~pong~~ping"),
    TextCommand(source_text=":middle_finger:", target_text="Faites l'amour, pas la guerre... :peace_symbol:", exact=False),
    TextCommand(source_text="marco", target_text="polo"),
    SpotifyCommand(),
    TextCommand(source_text="@liumbot bzh", target_text="https://t.ly/282J"),
]
commands.append(HelpCommand(commands))

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
        print(text)
        message_id = post["id"]

        for command in commands:
            answer = command.match_and_answer(text)
            if answer is not None:
                answer_to_post(text=answer, post=post)

mattermost.init_websocket(event_handler)
