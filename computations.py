# Import standard libraries
import psycopg2

# Import custom script
import spotifyauth

URL = "postgres://vqknvpawvibctc:3416e185bcfa3ba0423ac101e908d815f01a1837322c4950ad31a1ca897e2cb2@ec2-54-228-139-34.eu-west-1.compute.amazonaws.com:5432/d2if6njdaf83bu"


def check_user_exist(user: str) -> bool:
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"""SELECT personid FROM AuthData
    WHERE personid = '{user}';""")
    person = cur.fetchone()
    cur.close()
    con.close()
    return person is not None


def check_user(user: str, scope: str) -> bool:
    """
    :arg user: The user to check
    :arg scope: The scope to check
    :return bool: Whether the user is new or not
    Returns whether the user is new or not/needs an updated scope
    """
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"""SELECT scope FROM AuthData
WHERE personid = '{user}';""")
    auth_scope = cur.fetchone()
    cur.close()
    con.close()
    if auth_scope is None:
        return True
    auth_scope = auth_scope[0].split()
    if not set(scope.split()).issubset(set(auth_scope)):
        return True
    return False


def save_user(user: str, token: str, refresh: str, time: float, scope: str):
    """
    Saves details about a user
    """
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"""INSERT INTO AuthData
VALUES ('{user}', '{token}', '{refresh}', {time}, '{scope}');""")
    cur.close()
    con.commit()
    con.close()


def delete_user(user: str):
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"DELETE FROM AuthData WHERE personid = '{user}';")
    cur.close()
    con.commit()
    con.close()


def get_user(user: str):
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"""SELECT * FROM AuthData
WHERE personid = '{user}';""")
    result = cur.fetchone()
    cur.close()
    con.close()
    return result[1:]


def update_user(user: str, token: str, refresh: str, time: float, scope: str):
    con = psycopg2.connect(URL)
    cur = con.cursor()
    cur.execute(f"""UPDATE AuthData
SET authtoken = '{token}', refreshtoken = '{refresh}', time={time}, scope = '{scope}'
WHERE personid = '{user}';""")
    cur.close()
    con.commit()
    con.close()
    

async def show_overlap(*users: list[str]) -> dict:
    """
    :arg users: The id of users to compare
    :return list: Contains the songs that overlap,
    the total songs that overlap and the percent overlap
    Gives information about the overlap of song taste between 2 users
    """

    # For each user grab their songs via the api
    user_songs = []
    for user in users:
        response = await spotifyauth.get_user_songs(str(user))
        if response['Error'] == 0:
            user_songs.append(response['info'])
        else:
            return response

    # Find the set intersection between all the user's songs
    songs = set(user_songs[0])
    for i in range(1, len(user_songs)):
        songs = set(user_songs[i]) & songs

    # Find the total number of songs
    total_songs = sum(map(len, [song_set for song_set in user_songs]))

    # Find the percentage overlap
    overlap_percentage = format((len(songs) / total_songs) * 100, '.3')

    # Find song names with id dict
    id_dict = {}
    for song_dict in user_songs:
        for key in song_dict:
            id_dict.update({key: song_dict[key]})

    # Get all the names from the dict
    song_details = [id_dict[song_id] for song_id in songs]

    # Return the information
    return {"info": {"songs": song_details, "total": len(songs),
                     "percentage": overlap_percentage}, "Error": 0}


def link_to_uri(link: str) -> str:
    if "?si=" in link:
        link = link.split("?si=")[0]

    link = link.replace("https://open.spotify.com", "spotify")
    link = link.replace("/", ":")

    return link


def form_message(items: list) -> list:
    """
    :arg items: A list of items to put into inline text
    Creates an inline text message to send to discord
    """
    i = 0
    messages = []
    while i < len(items):
        message = "```"
        while i < len(items) and (len(message) + 3) + len(items[i]) < 2000:
            message += f"{items[i]}\n"
            i += 1

        message += "```"
        messages.append(message)

    return messages
