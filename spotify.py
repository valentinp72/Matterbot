import re
import json
import random
import datetime
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

class RandomSong(Command):

    def __init__(self, songs, theme, random_daily=False):
        self.songs = songs
        self.theme = theme
        self.random_daily = random_daily
        self.current_date = None
        self.current_choice = None

    def match(self, message):
        return message.lower() == f'@liumbot {self.theme}'.lower()

    def get_answer(self, message):
        if self.random_daily:
            now = datetime.datetime.today().strftime("%d-%m-%Y")
            if self.current_date != now:
                self.current_date = now
                self.current_choice = random.choice(self.songs)
            random_track = self.current_choice
        else:
            random_track = random.choice(self.songs)
        spotify = SpotifyCommand.get_spotify(random_track)
        url = f"https://open.spotify.com/track/{random_track}"

        if spotify is None:
            return
        answer = f"![{spotify['title']}]({spotify['image']} =100)\n"
        answer += f"[**{spotify['title']}**]({url})\n"
        answer += f"{spotify['description']}"
        return answer

    def get_help(self):
        more = ''
        if self.random_daily:
            more = ' (daily)'
        return f'`@liumbot {self.theme}`: get a random song from {self.theme}' + more

class SpotifyCommand(Command):

    SPOTIFY_TRACK_MATCHER = re.compile(r"https://open\.spotify\.com/track/(?P<track_id>[^\s\?]+)")

    def match(self, message):
        return "https://open.spotify.com/track/" in message

    def get_answer(self, message):
        today = datetime.date.today()
        if today.month == 12 and today.day == 25:
            message = "https://open.spotify.com/track/0bYg9bo50gSsH3LtXe2SQn"
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
    TextCommand(source_text="boom shack a lak", target_text="https://open.spotify.com/track/5rYJbmPYDaC4yJ8toRSrof"),
    SpotifyCommand(),
    RandomSong(
        songs=["0bYg9bo50gSsH3LtXe2SQn", "2FRnf9qhLbvw8fu4IBXx78", "5hslUAKq9I9CG2bAulFkHN", "2uFaJJtFpPDc5Pa95XzTvg", "09OojFvtrM9YRzRjnXqJjA", "1RMDXedcRno6rDBCbNHDJf", "07RmHXaYqBdUyfAESPZkRO", "4MXjNlvbzwCMWHrxlya9pW", "4SiAzqioAQcigeBzCQ3U2j", "3PIDciSFdrQxSQSihim3hN", "1rv46mRwDqMEhOBZ7vODg3", "0NSAlbl5xcKOu7BKDbVk7I", "3jKVI7aQfr11uhEOcOIwcZ", "6r2QqSbil8Din17Y51Scen", "2xGO2UjzxeVQSIkyg98vck", "5yNgdD8E6WruhULb4n2Con", "4PS1e8f2LvuTFgUs1Cn3ON", "26hUXfKoJYkAMK07nW2dzQ", "27RYrbL6S02LNVhDWVl38b", "65irrLqfCMRiO3p87P4C0D", "3B7FO3kJ5kv3mX7yiaB7sT", "5mZpq33J8jsDVQ42TmjizK", "5Q2P43CJra0uRAogjHyJDK", "67mgz7S5y7hnCE63YBjfO6", "1V0qqWBbIWt8hlAjxTZedR", "7xapw9Oy21WpfEcib2ErSA", "48N60kr2DFvTYfvZvTAqoj", "4c4LylLvTh91IhwQgSXPRc", "2pnPe4pJtq7689i5ydzvJJ", "1SV1fxF65n9NhRHp3KlBuu", "7aKOrnegxN1BRuFERyz550", "27qAMKrDdKEs8HDXcvR24R", "4EOJWkvkVDpkZrhC8iTDsI", "3aHDEjyb4ZMpdj0G2xDGUM", "3WrG9BpOPQWUus3FjA1Tny", "280jC1bGyGtZq3VXsSk6hH", "6pPLhUHaxNy37eIUNYu5JL", "3sDdyBHQ60Cs1opmIyRvhp", "3M0zQnFBi3FTNGhkMGikGI", "2X5noCM9Klrm4zXfyyPdRN"],
        theme='NOËL',
        random_daily=True
    ),
    RandomSong(
        songs=["4CLPZNwUITqYekTvyPeive", "2Ras8TV02rraE9JCkEVfwB", "3w4U9vZldQ5kgEi0N4Unc6", "6TWT2UFCPoi0scf55M39ls", "2MSFiP3ntDhHGEz5Fy4Gqc", "5wbXbE6URBfTPZecZuSYT8", "4SWkhL9w3GyvbkKUbovvFg", "3y1bCmGGMVnthn6r2u6Pew", "5AckvDuR4Ga5KOP6M0gnFH", "2igdTZeMTdtINAH41WJaix", "5UUS6mVUeEaN8dsrxycxdC", "7C0cO16ZSSmJPyYmSruQgt", "6QHArSuqT0o4CTB15NEbNK", "7vs3WkE9wB9G6hxNtKpmXd"],
        theme='Théo Mariotte',
    ),
    RandomSong(
        songs=["6RECDe6BIdnADiavD9kvqk", "5JXbFbY9oJFI5GgfXKCTAo", "5mPxk22dPoO7DrywL6xT3n", "4cYFep5SECqb4EsSkF82e0", "64gCM9yZv2jpNflclKUnXu", "54OBgO0Xwu20Jak9TMXbR7", "5qcHNtNeQWSEVTeIwBLwss", "4qRHwcsUkrYFZe2fOlcrAR", "3nXpsXtbeZkyu1iuOgbeQK", "1tol8fVsDQasYsy5pb8raT", "6SS9OF7qgf1EK2mr1Vmvbs", "1AHIVgpK90TTvBe1HM49hM", "5LppNo9DpHXcbJzIuo9VTo", "5aYwgXdg6FzTJ1EHLmFW5r", "2LtBLSQsCLca2flQpDHhOA", "01xA7P2ryJ0ohiFSWZFChL", "2itXGPskhSohSd7e67uKhv", "0x530BpHWXCqpqU5P4gXDr", "5VgQkhPoKcdJqggCJd1MsC", "2kOuJlOIup1upp9NtlvPnZ", "6tdWV3xGZD1yvRgwcZ72uV", "1ZK8WJqkD1XhEYI1AlkMHG", "3z613YwTlIIDulcfPRp6GE"],
        theme='Bretagne'
    ),
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
