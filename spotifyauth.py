# Import standard libraries
import os
import asyncio
import concurrent.futures
import collections

# Import custom script
import spotifyapi
import computations

# Get information for spotify OAuth operations
client_id = os.getenv('SPOTIFY_ID')
client_secret = os.getenv('SPOTIFY_SECRET')
redirect_uri = "http://localhost:8080/"


async def setup_user(ctx, bot, scope: str) -> dict:
    """
    :arg ctx: A discord context object
    :arg bot: An instance of discord bot class
    :arg scope: The scope to set up for
    Sets up a user for the specified scope
    """
    # Get the url and instance of oauth
    # to authorise the user
    url, oauth = get_url(scope)

    # Show the user the url
    await ctx.author.send(url)

    # Define function to check the message is
    # by the needed user
    def check(m):
        return m.author == ctx.author

    # Wait for the user to send a message
    response = await bot.wait_for('message', check=check)

    # Get the auth_code from the url
    auth_code = response.content.split("?code=")[1]

    # Get the response from the spotify api
    response = oauth.grab_token(auth_code)

    # Add error handling here
    return response


def get_url(scope: str) -> list[str, object]:
    """
    :arg scope: The scope to authorise for
    :return str: Returns the url
    Gets the authentication url for the user to proceed with OAuth
    """
    # Make an OAuth instance
    oauth = spotifyapi.OAuth(client_id, client_secret, redirect_uri, scope)

    # Get a url to authorise with
    url = oauth.grab_code()

    # Return the url and instance for later use
    return [url, oauth]


async def get_user_songs(user: str) -> dict:
    """
    :arg user: The id of the user to save the songs for (Required)
    :return None:
    Sets up the users cache and saves all the
    unique songs in their playlists
    """
    scope = 'playlist-read-private'

    if computations.check_user(user, scope):
        return {"info": [],
                "Error": f'''```User has wrong scope
re-authenticate using the `+setup` command please```'''}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    # Get the total number of playlists the user has
    total = sp.get_users_playlists(0)['total']

    # Get every playlist from the api
    playlists = []
    for i in range(total // 50 + (total % 50 > 0)):
        playlists += sp.get_users_playlists(50, i*50)['items']

    # Get the playlist ids and the number of tracks
    # in each playlist
    playlist_ids = map(lambda x: x['id'], playlists)
    track_nums = map(lambda x: x['tracks']['total'], playlists)

    # Define tracks list
    tracks = []

    # Get the loop for asyncio
    loop = asyncio.get_event_loop()

    # Create a threading executor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # For each playlist
        for playlist_id, length in zip(playlist_ids, track_nums):
            # Get the tracks in the playlist
            futures = []
            for i in range(length // 100 + (length % 100 > 0)):
                futures.append(loop.run_in_executor(executor,
                                                    sp.get_tracks_playlist, playlist_id, 100, i*100))

            # Add the songs to the tracks list
            for future in futures:
                songs = await future
                tracks += songs['items']

    # Get all the songs ids and get all the unique songs
    track_ids = [x['track']['id'] for x in tracks]
    track_names = [x['track']['name'] for x in tracks]
    track_artists = [x['track']['artists'][0]['name'] for x in tracks]
    songs = dict(zip(track_ids, zip(track_names, track_artists)))

    return {"info": songs, "Error": 0}


async def sleep_timer(user: str, time: int) -> dict:
    """
    :arg user: The user to create a sleep time for
    :arg time: The time for the tracks to stop after in seconds (Required)
    Stops playback after the specified time
    """
    # Set the scope needed for this function
    scope = "user-modify-playback-state user-read-playback-state"

    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error user not authenticated for use"}

    # Wait for the sleep timer time
    await asyncio.sleep(time)

    # Get the auth code and APIReq class to interact with the API
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    sp = spotifyapi.APIReq(code)

    # Get the information about the user's playback so
    # playback can stop at the end of a track
    info = sp.get_info_playback()

    # Calculate the time left to wait for the end of the track
    time_left = (info['item']['duration_ms']-info['progress_ms'])

    # Wait for the rest of the song
    await asyncio.sleep(time_left//1000)

    # Pause the playback
    ret = sp.pause_playback()
    if ret != "Successful":
        return {"Info": [], "Error": ret}
    return {"Info": "Paused music", "Error": 0}


def get_recommendations(user: str, songs: int, source: list) -> dict:
    """
    :arg user: The user to get recommendations for
    :arg songs: The number of songs to get
    :arg source: The source for the seed, artists, tracks, playlist
    Return recommendations for the user
    """
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)
    if source[:17] == "spotify:playlist":
        # Get the first 5 tracks from the playlist or 5 random songs
        track_data = sp.get_tracks_playlist(source[17:], 5)['items']
        tracks = [item['id'] for item in track_data]
        artists = []
    else:
        tracks = []
        artists = []
        # For each item in the source, get the type and add to that list
        for item in source:
            if item[:14] == "spotify:track:":
                tracks.append(item[14:])
            if item[:15] == "spotify:artist:":
                artists.append(item[15:])

    # Sort through parameters to specify the correct seed to the command
    if len(artists) != 0 and len(tracks) != 0:
        recs = sp.get_recommendations(songs, artists=artists, tracks=tracks)
    elif len(artists) != 0:
        recs = sp.get_recommendations(songs, artists=artists)
    elif len(tracks) != 0:
        recs = sp.get_recommendations(songs, tracks=tracks)
    else:
        return {"info": [], "Error": "Error no seed source"}

    return {"info": recs, "Error": 0}


def add_to_queue(user: str, tracks: list) -> dict:
    """
    :arg tracks: A list of track instances from spotify api
    :return str: Whether the request worked or not
    Adds given tracks to the user's queue
    """
    scope = "user-modify-playback-state"
    if not computations.check_user(user, scope):
        # Get the auth code
        code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)
        # Initiate the APIReq class to interact with the api
        sp = spotifyapi.APIReq(code)

        for track in tracks:
            sp.add_track_playback(track['uri'])

        return {"info": "Request successful", "Error": 0}
    else:
        return {"info": [], "Error": "Error, user not authenticated for request, run `+setup all`"}


def create_playlist(user: str, tracks: list) -> dict:
    """
    :arg tracks: A list of track instances from spotify api
    :return str: Whether the request worked or not
    Adds given tracks to a playlist for the user
    """
    scope = "playlist-modify-public"
    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error, user not authenticated for request, use command `+setup`"}
    
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    # Get user id
    user_id = sp.get_user()['id']

    # Create playlist
    playlist_id = sp.create_playlist(user_id, 'DiscordRecs')['id']

    track_uris = [track['uri'] for track in tracks]

    sp.add_items_playlist(playlist_id, track_uris)

    return {"info": "Request successful", "Error": 0}


def top_ten(user: str, time_range: str) -> dict:
    """
    :arg user: The user to get the songs of
    Gets the top 10 tracks for the user
    """

    scope = "user-top-read"
    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error, user not authenticated for request, use command `+setup`"}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    tracks = sp.top_tracks(f"{time_range}_term", 10)

    return {"info": tracks['items'], "Error": 0}


async def genres(user: str, artists: list) -> list:
    """
    :arg user: The id of the user
    :arg artists: List of artists to get the genre of
    Gets the genres of a given list of artist
    """
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user, read_func=computations.get_user, update_func=computations.update_user, check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)
    genre_list = []
    for artist in sp.get_artists(artists)['artists']:
        genre_list += artist['genres']

    return list(set(genre_list))


async def get_artists(user: str, playlist: str) -> dict:
    """
    :arg user: The user id
    :arg playlist: The id of the playlist to look at
    """
    # If the user isn't in the database send an error
    if not computations.check_user_exist(user):
        return {"info": [],
                "Error": f'''```User doesn't exist
    authenticate using the `+setup` command please```'''}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    playlist_id = playlist.replace("spotify:playlist:", '')

    # Get the total number of playlists the user has
    total = sp.get_tracks_playlist(playlist_id, 1)['total']

    # Define tracks list
    tracks = []

    # Get the loop for asyncio
    loop = asyncio.get_event_loop()

    # Create a threading executor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for i in range(total // 100 + (total % 100 > 0)):
            futures.append(loop.run_in_executor(executor,
                                                sp.get_tracks_playlist, playlist_id, 100, i * 100))

        # Add the songs to the tracks list
        for future in futures:
            songs = await future
            tracks += songs['items']

    # Get all the artists for the tracks
    artists = []
    for track in tracks:
        artists += [artist['name'] for artist in track['track']['artists']]

    # Convert the list to a dictionary with counts of each artist
    artists = collections.Counter(artists)

    # Work out the percentage for each artist
    percentages = [format(artists[key]/sum(map(int, artists.values()))*100, '.3') for key in artists.keys()]

    return {"info": {"artists": sorted(list(zip(artists.keys(), percentages)), key=lambda x: 100-float(x[1]))[:10],
            "Total": sum(map(int, artists.values()))},
            "Error": 0}


def cur_song(user: str) -> dict:
    """
    :arg user: The id of the user to get the current song of
    """
    # If the user isn't in the database send an error
    if not computations.check_user_exist(user):
        return {"info": [],
                "Error": f'''```User doesn't exist
    authenticate using the `+setup` command please```'''}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Create an APIReq instance
    sp = spotifyapi.APIReq(code)

    # Get the information about the user's playback
    info = sp.get_info_playback()

    # Create a string holding the song name and artist
    search = f"{info['item']['name']} {info['item']['artists'][0]['name']}"

    # Return the information
    return {"info": search, "Error": 0}
