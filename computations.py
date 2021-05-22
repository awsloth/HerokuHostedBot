# Import standard libraries
import os
import collections

# Import 3rd party libraries
import psycopg2

# Import custom script
import spotifyauth

URL = os.getenv('DATABASE_URL')


def check_user_exist(user: str) -> bool:
    """
    :arg user: The user to check (Required)
    :return bool: Whether the user exists or not
    Checks whether any information is stored about the user in the database
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Get all personid-s in the database where the
    # id is the same as that of the user
    cur.execute(f"""SELECT personid FROM AuthData
    WHERE personid = '{user}';""")

    # Get the results
    person = cur.fetchone()

    # Close the connection to the database
    cur.close()
    con.close()

    # If there was a matching id return True, else False
    return person is not None


def check_user(user: str, scope: str) -> bool:
    """
    :arg user: The user to check (Required)
    :arg scope: The scope to check (Required)
    :return bool: Whether the user is new or not
    Returns whether the user is new or not/needs an updated scope
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Get all scope where the personid matches that of the user
    cur.execute(f"""SELECT scope FROM AuthData
WHERE personid = '{user}';""")

    # Get the results
    auth_scope = cur.fetchone()

    # Close the connection to the database
    cur.close()
    con.close()

    # If there is no scope return true
    if auth_scope is None:
        return True

    # If there is a scope get each scope and test
    # if the wanted scope is a subset of the authorized scope
    auth_scope = auth_scope[0].split()
    if not set(scope.split()).issubset(set(auth_scope)):
        return True
    return False


def save_user(user: str, token: str, refresh: str, time: float, scope: str) -> None:
    """
    :arg user: The user to save details about (Required)
    :arg token: The auth token for the user (Required)
    :arg refresh: The refresh token for the user (Required)
    :arg time: Time the token was received (Required)
    :arg scope: The scope of the token (Required)
    :return None:
    Saves details about the user
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Insert a new user into the database
    cur.execute(f"""INSERT INTO AuthData
VALUES ('{user}', '{token}', '{refresh}', {time}, '{scope}');""")

    # Close the connection to the database
    # and commit changes to the database
    cur.close()
    con.commit()
    con.close()


def delete_user(user: str) -> None:
    """
    :arg user: The user to delete the data about (Required)
    :return None:
    Deletes any stored information about the user
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Delete from the database where the id matches that of the user
    cur.execute(f"DELETE FROM AuthData WHERE personid = '{user}';")

    # Close the connection to the database
    # and commit changes to the database
    cur.close()
    con.commit()
    con.close()


def get_user(user: str) -> list:
    """
    :arg user: The user to get information about (Required)
    :return list: A list containing the information
    Grabs the information about the user from the database
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Get all the information about the user where the id matches
    cur.execute(f"""SELECT * FROM AuthData
WHERE personid = '{user}';""")

    # Get the results
    result = cur.fetchone()

    # Close the connection to the database
    cur.close()
    con.close()
    return result[1:]


def update_user(user: str, token: str, refresh: str, time: float, scope: str) -> None:
    """
    :arg user: The user to update details about (Required)
    :arg token: The auth token for the user (Required)
    :arg refresh: The refresh token for the user (Required)
    :arg time: Time the token was received (Required)
    :arg scope: The scope of the token (Required)
    :return None:
    Updates details about the user
    """
    # Open a connection to the database
    con = psycopg2.connect(URL)
    cur = con.cursor()

    # Update the database where the id matches that of the user
    cur.execute(f"""UPDATE AuthData
SET authtoken = '{token}', refreshtoken = '{refresh}', time={time}, scope = '{scope}'
WHERE personid = '{user}';""")

    # Close the connection to the database
    # and commit changes to the database
    cur.close()
    con.commit()
    con.close()
    

async def show_overlap(*users: list[str]) -> dict:
    """
    :arg users: The id of users to compare (Required)
    :return list: Contains the songs that overlap,
    The total songs that overlap and the percent overlap
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

    overlap = intersection(user_songs)

    return overlap


async def playlist_overlap(user: str, accuracy: str, *playlist_ids) -> dict:
    """
    :arg user: The user to authenticate (Required)
    :arg accuracy: The type of intersection to find (Required)
    :arg playlist_ids: The ids of the playlists to compare (Required)
    :return dict: The overlapping songs
    Finds the intersections between the playlists
    """
    tracks = []
    for playlist_id in playlist_ids:
        playlist_songs = await spotifyauth.get_playlist_songs(user, playlist_id, False)
        if playlist_songs['Error'] != 0:
            return {'info': [], 'Error': playlist_songs['Error']}
        tracks.append(playlist_songs['info'])

    user_songs = []
    for play_tracks in tracks:
        track_ids = [x['track']['id'] for x in play_tracks if not x['track']['is_local']]
        track_dict = [[x['track']['name'], x['track']['artists'][0]['name']] for x in play_tracks
                      if not x['track']['is_local']]
        songs = dict(zip(track_ids, track_dict))
        user_songs.append(songs)

    if accuracy == "exact":
        return intersection(user_songs)

    return ordered_songs(user_songs)


def intersection(song_list: list) -> dict:
    """
    :arg song_list: List of song lists to find the intersection of (Required)
    :return dict: The songs that overlap exactly
    Finds the intersection of the songs
    """

    # Find the set intersection between all the user's songs
    songs = set(song_list[0].keys())
    for i in range(1, len(song_list)):
        songs = set(song_list[i].keys()) & songs

    # Find the total number of songs
    total_songs = sum(map(len, [song_set for song_set in song_list]))

    # Find the percentage overlap
    overlap_percentage = format((len(songs) / total_songs) * 100, '.3')

    # Find song names with id dict
    id_dict = {}
    for song_dict in song_list:
        id_dict.update(song_dict)

    # Get all the names from the dict
    song_details = [[id_dict[song_id], song_id] for song_id in songs]

    # Return the information
    return {"info": {"songs": song_details, "total": len(songs),
                     "percentage": overlap_percentage}, "Error": 0}


def ordered_songs(song_list: list) -> dict:
    """
    :arg song_list: List of song lists to find the intersection of (Required)
    :return dict: The songs that overlap with more than half of the lists
    Finds the intersection of the songs
    """
    songs = []
    for song_set in song_list:
        songs += list(set(song_set))

    song_counts = collections.Counter(songs)

    num_cutoff = max(len(song_list)/2, 2)
    filtered_songs = [[song_counts[song], song] for song in song_counts.keys() if song_counts[song] >= num_cutoff]

    song_dict = {}
    for sub_dict in song_list:
        song_dict.update(sub_dict)

    song_info = sorted([[song_count, song_dict[song], song] for song_count, song in filtered_songs],
                       key=lambda x: x[0], reverse=True)

    return {"info": {"songs": song_info}, "Error": 0}


def link_to_uri(link: str) -> str:
    """
    :arg link: The link to convert to uri (Required)
    :return str: The uri
    Converts a spotify link to a uri
    """
    # If the link contains the ?si= section remove it
    if "?si=" in link:
        link = link.split("?si=")[0]

    # replace the url base with spotify
    link = link.replace("https://open.spotify.com", "spotify")

    # Change slashes to colons
    link = link.replace("/", ":")

    return link


def uri_to_id(uri: str) -> str:
    """
    :arg link: uri to convert (Required)
    :return str: Id version of the uri
    Converts an uri to an id
    """
    # Get the id from the end
    return uri.split(":")[-1]


def form_message(items: list) -> list:
    """
    :arg items: A list of items to put into inline text (Required)
    :return list: A list of message blocks
    Creates an inline text message to send to discord
    """
    # TODO check this function works, because it is slightly dodgy

    # Go through all lines and if the line still fits within
    # the 2000 character limit add it, else create a new message
    i = 0
    messages = []
    while i < len(items):
        message = "```"
        while i < len(items) and (len(message) + 3 + len(items[i]) < 2000):
            message += f"{items[i]}\n"
            i += 1

        message += "```"
        messages.append(message)

    return messages


def id_to_uri(id_type: str, id_: int) -> str:
    """
    :arg id_type: The type of thing the id is
    :arg id: id to convert (Required)
    :return str: uri version of the id
    Converts an id to a uri
    """
    uri = f"spotify:{id_type}:{id_}"
    return uri
