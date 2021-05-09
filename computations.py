# Import standard libraries
import os

# Import 3rd party libraries
import psycopg2

# Import custom script
import spotifyauth

URL = os.getenv('DATABASE_URL')


def check_user_exist(user: str) -> bool:
    """
    :arg user: The user to check
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
    :arg user: The user to check
    :arg scope: The scope to check
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


def save_user(user: str, token: str, refresh: str, time: float, scope: str):
    """
    :arg user: The user to save details about
    :arg token: The auth token for the user
    :arg refresh: The refresh token for the user
    :arg time: Time the token was received
    :arg scope: The scope of the token
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


def delete_user(user: str):
    """
    :arg user: The user to delete the data about
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
    :arg user: The user to get information about
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


def update_user(user: str, token: str, refresh: str, time: float, scope: str):
    """
    :arg user: The user to update details about
    :arg token: The auth token for the user
    :arg refresh: The refresh token for the user
    :arg time: Time the token was received
    :arg scope: The scope of the token
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
    """
    :arg link: The link to convert to uri
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
    :arg link: uri to convert
    :return str: Id version of the uri
    Converts an uri to an id
    """
    # Get the id from the end
    return uri.split(":")[-1]


def form_message(items: list) -> list:
    """
    :arg items: A list of items to put into inline text
    :return list: A list of message blocks
    Creates an inline text message to send to discord
    """
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
