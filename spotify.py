import re
import json
import random
import datetime
import requests
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--spotify_client_id', type=str)
parser.add_argument('--spotify_client_secret', type=str)
args = parser.parse_args()

from mattermostdriver import Driver
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

with open("config.json", "r") as f:
    config = json.load(f)

mattermost = Driver(config['mattermost'])
mattermost.login()

ME = mattermost.users.get_user(user_id='me')['id']

if args.spotify_client_id is not None and args.spotify_client_secret is not None:
    auth_manager = SpotifyClientCredentials(client_id=args.spotify_client_id, client_secret=args.spotify_client_secret)
else:
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
        answer += f"**{spotify['title']}**\n"
        answer += f"{spotify['description']}\n"
        answer += f"Link: [**Desktop**](spotify:track:{random_track}) - [**Web**]({url})"
        return answer

    def get_help(self):
        more = ''
        if self.random_daily:
            more = ' (daily)'
        return f'`@liumbot {self.theme}`: get a random song from {self.theme}' + more

class SpotifyCommand(Command):

    SPOTIFY_TRACK_MATCHER = re.compile(r"https://open\.spotify\.com/(intl-fr/)?track/(?P<track_id>[^\s\?]+)")

    def match(self, message):
        return "https://open.spotify.com/" in message

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
        answer += f"**{spotify['title']}**\n"
        answer += f"{spotify['description']}\n"
        answer += f"Link: [**Desktop**](spotify:track:{track_id}) - [**Web**]({url})"
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
    TextCommand(source_text="je veux mon pompon !!!", target_text="@mlebourdais @tprouteau rendez le pompon de Valentin !"),
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
    RandomSong(
        songs=["4VqPOruhp5EdPBeR92t6lQ","3lPr8ghNDBLc2uZovNyLs9","7xyYsOvq5Ec3P4fr6mM9fD","2UKARCqDrhkYDoVR4FN5Wi","0It6VJoMAare1zdV2wxqZq","3skn2lauGk7Dx6bVIt5DVj","2takcwOaAZWiXQijPHIx7B","0c4IEciLCDdXEhhKxj4ThA","383QXk8nb2YrARMUwDdjQS","7ouMYWpwJ422jRcDASZB7P","5PK1JCSdr34gWgzYHgt3Jq","6Wi8Byfq6xH0lEkqZbOZg9","1tjHKKI0r82IB5KL29whHs","3eSyMBd7ERw68NVB3jlRmW","6kyxQuFD38mo4S3urD2Wkw","2xO0NhSt9kzKBbNjNVixfC","1C2QJNTmsTxCDBuIgai8QV","5VVWgWH8HFLAtM8lbttvn9","5YXr4AGfUQpLSxtFSsKUh6","6tpl3yuDnYHAHb6dY60p5O","57lCa95tmjJ8EYdNTex8Kk","5wq8wceQvaFlOZovDtfr0j","0j3obufLXq5toSs592dX9U","4k0hvjglHbcZI203QI4pF7","40pPI2TbaYSZlKfV44HRjn","7gmQ329Ocmvb9OImqevFBF","2VrJMuLt2m9HbifGrKWHqk","35E8of4u0B5PI8o4Hy0tWq","5rupf5kRDLhhFPxH15ZmBF","0dMYPDqcI4ca4cjqlmp9mE","2daZovie6pc2ZK7StayD1K","0C5U4go8KKWHmAipujRH6I","0xJLcjd0gaZct43xG1UlXS","3Y4m9Td603gbfMB86UNafs","2qkmPUG7ARsRwhVICQVwQS","6JnFVmPyJvjnfBag0hhIFa","1hHuyqVCZCbhYQixEkdQCo","2IFqUmfW8oQoKn6ToxKsMs","4AIazttPmHpd7p7pwJw692","6xq3Bd7MvZVa7pda9tC4MW","0RILico3Gbl5jxSNg3zLrJ","2raJLzvNRvipP8cJuchk6U","0MrkZz4D3fGlEkhebjPPrh","1244xKUG27TnmQhUJlo3gU","2zmR3FG7iOGDAdwrVPzdg9","6r9tjMWLv8fNdZKKTnqCEr","7f0vVL3xi4i78Rv5Ptn2s1","28FJMlLUu9NHuwlZWFKDn7","1esX5rtwwssnsEQNQk0HGg"],
        theme='Muse'
    ),
    RandomSong(
        songs=["5LYAuItJcXH06adHkebOmf","3h7fLhqLyPRxV0PCuefud9","5v9xa2Nv0oYxh1XilPR8r9","2yjMkZBof4BnTgpk8N7SWt","6K4t31amVTZDgR3sKmwUJJ","3hGpoBRBJpQlZVwVbVygav","6DLylbY93X5wKOPxhLfUHE","6EtKlIQmGPB9SX8UjDJG5s","3u5N55tHf7hXATSQrjBh2q","6wsGayuJ14nOtVvx8utHUW","0lqi60soNz0g9nC0IHFlni","7tRCBEVxgBG8EZNLUzzv8R","37sRZ6Zj5YdVy0dZM0MOwM","6oZub1HODkC3sRK7CAFpRc","0iJgOtbNDJg7A7iFfAdd3R","1boz1DGJjXV4PHsMpAMYqP","51pCXIv46lQcfwtWXotX0p","2EWnKuspetOzgfBtmaNZvJ","2sfnGAHcam37qlF5Ovc8xx","4rHIGjDTXXL9Eudf3YF036","0I3StbOvOKwXKhg7kadCxy","4i17ViZoevssgUvRifo0V5","5TmQOp6XVbcy2qYMjte3MI","18AXbzPzBS8Y3AkgSxzJPb","1RSy7B2vfPi84N80QJ6frX","71SvfhuWqZuzx7pG44DOib","2kRFrWaLWiKq48YYVdGcm8","5oDHtv5XcJzLeXR7mjp86f","3W2ZcrRsInZbjWylOi6KhZ","1MdbDBwEEecnlLiyWChJFh","2NRWckehPD8dwH2iXmjZeB","4IDdUssauEYJ9kTit6tOU6","76NmJpsXiPAmMdcCsPXHyu","56cqmGid7J5wMyfXJzOEOd","6RaJbbhKDOuBGQhbZCubCW","11erd78PxLLisWkQjWYUWt","6k4V7X9vAY5Tul798zzR2l","6gCXxz0Gy4PQ4uDXLTBhkf","27pIyLmBECesAiEOud5mqQ","4JFHAlZfL67UF1uotyCPfr","6V0LX0hP1S0qH513CChAKt","5HacUj9C7OZ53fuIJ9kB8J","1N3bdxmsu3wimLy3E4d4cf","7uv632EkfwYhXoqf8rhYrg","7nPnjPDxao5TKMjsw44rai","67Hna13dNDkZvBpTXRIaOJ","732E6ibFkQR5lNIPEeiEnx","55gYvmb7abmFAq6s46eDWP","2cWKBlF08tW56oqDvVa0sG","4TQcARE7Fd58akNhr3N7AE","1r3Yn5CuNvO4RissOzTnXK","4kJWtxDDNb9oAk3h7sX3N4","0qnqsfFYgBo0sPHM2JmfTq","5exiWZkZho6AvCGkabEMeA","7pAW3XGsByG4avvzn3BGYE","3deEptZz3e8PggoFhiFGra","3eFGq6bRioPV20zBDvMeYw","5MHnT8tTakjzZsiuHGxXyc","3tKP4uEWIbOhsFzPBkSumU","026m9k1JEGh8y36dZl2S82","7rrcyumzejmKhlTghcQOxY","20ecx8o3II4wMmoDA7jjPf","4hElE1DmCfpoFVjczvfB5U","6a9mRPQKKnuaayzY0RcRwD","2caABDipxldhTNWvVMNh0U","5bM6mVTOD8RBNCBKSq94GA","31KWQUc0jo0qjZeqduEovA","6kOkhuico8F2222r3WVAT7","6gbmylJ7sB7NFfMfTQHosf","3PfIrDoz19wz7qK7tYeu62","6cxKsHtjSzUbp2vFRcw5qI","5fXdbH7woFgkGGPgkq16Qc","7gi9ulaPPCuh97l52zUPuf","61R34KLwTrNMs2KCi7rIFC","6dVcdpGeAVqvVDAMKrZkak","4qO03RMQm88DdpTJcxlglY","2Qb5ly9QzzlfAN9PDeIi9X","3qyWNgkq39EhCq18s2ZtIW","3x2bfrSIuGuxR5Qj6KxKyk","0XDA8IPloCFvf8c0ZNzRnB","1WIT85qChJThW4G53ZtP3x","2YW1MNJFs8nhtzgEPsBcLu","3mnqWACBGfk2AO2eonicIT","4BfCAtIw8hy2DOW8QAyo30","3fAOSZc5hTpnXxSO43ymwu","2mj4Wu0odyns6lzjVZqATq","7iiSNaTl7uGAaLiKnQC9ot","0N0BYHAmSf0Pwdv9v3JIqo","5F8UfAhHNFipR1bKVjokTt","3AQnOXGTaQsZ8jRzjRqVYI","490opGdIqqybYW3PDngJsy","20X7r4ZCq2e6SKRYUNwzO2","0cwEvwz7syhgHKXX1z4puc","57S7JmztNeYbGzpW3F6nNu","14buky8FI8YsyAmErymMW3","1N1Ic1TSwksIqCUUbbwM1H","6VTbbVjKOC2qWagIDbkJrC","5squamHGWDnolLP3f98SXH","7dMOzsTZOUtOF7W5kLN0gf","5cVPf771xprBPyZQrD0hla","5qtjAOtSPuUGLwzZqSGDpW","3RcoIYZ9HOJ8nhKLRV9c4e","0kmWzly3fqBOFlVE39q7JT"],
        theme='Dr PhD'
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
