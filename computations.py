# Import standard libraries
import os

# Import custom script
import spotifyauth


def check_user(user: str, scope: str) -> bool:
    """
    :arg user: The user to check
    :arg scope: The scope to check
    :return bool: Whether the user is new or not
    Returns whether the user is new or not/needs an updated scope
    """
    # Set new_user to True initially
    new_user = True

    # Check if the user has a .cache file and whether it has the
    # correct scope, if both conditions met, set new_user to false
    for file in os.listdir("cache"):
        if file == f"{user}.cache":
            if scope != "":
                with open(fr"cache/{user}.cache") as f:
                    auth_scope = f.readlines()[3].rstrip().split()
                    req_scope = scope.split()
                    if set(req_scope).issubset(set(auth_scope)):
                        new_user = False
            else:
                new_user = False

    # Return whether the user is new or not
    return new_user


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
    overlap_perc = format((len(songs) / total_songs) * 100, '.3')

    # Find song names with id dict
    id_dict = {}
    for song_dict in user_songs:
        for key in song_dict:
            id_dict.update({key: song_dict[key]})

    # Get all the names from the dict
    song_details = [id_dict[song_id] for song_id in songs]

    # Return the information
    return {"info": {"songs": song_details, "total": len(songs),
                     "percentage": overlap_perc}, "Error": 0}


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

