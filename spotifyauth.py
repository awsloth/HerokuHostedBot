# Import standard libraries
import os
import asyncio
import math
import concurrent.futures
import collections

# Import 3rd party libraries
from discord.ext import commands

# Import custom script
import spotifyapi
import computations

# Get information for spotify OAuth operations
client_id = os.getenv('SPOTIFY_ID')
client_secret = os.getenv('SPOTIFY_SECRET')
redirect_uri = "http://localhost:8080/"


async def setup_user(ctx: commands.Context, bot: commands.Bot, scope: str) -> dict:
    """
    :arg ctx: A discord context object (Required)
    :arg bot: An instance of discord bot class (Required)
    :arg scope: The scope to set up for (Required)
    :return dict: A dict containing tokens and info about the oauth request
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

    if "?code=" not in response:
        return {"info": [], "Error": "Invalid url sent"}

    # Get the auth_code from the url
    auth_code = response.content.split("?code=")[1]

    # Get the response from the spotify api
    response = oauth.grab_token(auth_code)

    if "access_token" not in response:
        return {"info": [], "Error": "Request failed, try again"}

    return {"info": response, "Error": 0}


def get_url(scope: str) -> list[str, object]:
    """
    :arg scope: The scope to authorise for (Required)
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
    :return dict: A dict containing the information about the songs
    Sets up the users cache and saves all the
    unique songs in their playlists
    """
    scope = 'playlist-read-private'

    if computations.check_user(user, scope):
        return {"info": [],
                "Error": f'''```User has wrong scope
re-authenticate using the `+setup all` command please```'''}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    # Get the total number of playlists the user has
    response = sp.get_users_playlists(0)

    # TODO Check response has total in keys so that error is handled
    # Do request again or raise error?
    total = response['total']

    # Get every playlist from the api
    playlists = []
    for i in range(math.ceil(total/50)):
        playlists_info = sp.get_users_playlists(50, i*50)

        # TODO Check playlists_info is of form expected
        playlists += playlists_info['items']

    # Get the playlist ids and the number of tracks
    # in each playlist
    playlist_ids = map(lambda x: x['id'], playlists)

    # Define tracks list
    tracks = []

    for play_id in playlist_ids:
        play_tracks = await get_playlist_songs(user, play_id, True, sp)
        if play_tracks['Error'] != 0:
            return play_tracks
        tracks += play_tracks['info']

    # Get all the songs ids and get all the unique songs
    track_ids = [x['track']['id'] for x in tracks if not x['track']['is_local']]
    track_dict = [[x['track']['name'], x['track']['artists'][0]['name']] for x in tracks
                  if not x['track']['is_local']]
    songs = dict(zip(track_ids, track_dict))

    return {"info": songs, "Error": 0}


async def sleep_timer(user: str, time: int) -> dict:
    """
    :arg user: The user to create a sleep time for (Required)
    :arg time: The time for the tracks to stop after in seconds (Required)
    :return dict: Info about the request made
    Stops playback after the specified time
    """
    # Set the scope needed for this function
    scope = "user-modify-playback-state user-read-playback-state"

    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error user not authenticated for use, use `+setup all` command"}

    # Wait for the sleep timer time
    await asyncio.sleep(time)

    # Get the auth code and APIReq class to interact with the API
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    sp = spotifyapi.APIReq(code)

    # Get the information about the user's playback so
    # playback can stop at the end of a track
    info = sp.get_info_playback()

    # TODO check that the info has expected dict keys
    # Calculate the time left to wait for the end of the track
    time_left = (info['item']['duration_ms']-info['progress_ms'])

    # Wait for the rest of the song
    await asyncio.sleep(time_left//1000)

    # Pause the playback
    ret = sp.pause_playback()

    if ret != "Successful":
        return {"info": [], "Error": ret}

    return {"info": "Paused music", "Error": 0}


def get_recommendations(user: str, songs: int, source: list[str]) -> dict:
    """
    :arg user: The user to get recommendations for (Required)
    :arg songs: The number of songs to get (Required)
    :arg source: The source for the seed, artists, tracks, playlist (Required)
    :return dict: Recommendations based upon the seed
    Return recommendations for the user
    """
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    # Convert seed
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

    # TODO add error handling to the returned recommendations
    return {"info": recs, "Error": 0}


def add_to_queue(user: str, tracks: list[str]) -> dict:
    """
    :arg user: The user to add the tracks to (Required)
    :arg tracks: A list of track instances from spotify api (Required)
    :return str: Whether the request worked or not
    Adds given tracks to the user's queue
    """
    scope = "user-modify-playback-state"
    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error, user not authenticated for request, run `+setup all`"}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    for track in tracks:
        # TODO check that the tracks are added to playback
        # TODO and add error handling if not
        sp.add_track_playback(computations.id_to_uri("track", track))

    return {"info": "Request successful", "Error": 0}


def create_playlist(user: str, tracks: list, name: str) -> dict:
    """
    :arg user: The name of the user to add the playlist to (Required)
    :arg tracks: A list of track instances from spotify api (Required)
    :arg name: The name of the playlist (Required)
    :return str: Whether the request worked or not
    Adds given tracks to a playlist for the user
    """
    scope = "playlist-modify-public"
    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error, user not authenticated for request, use command `+setup all`"}
    
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    # Get user id
    response = sp.get_user()

    # TODO add error handling to check id in the keys
    user_id = response['id']

    # Create playlist
    playlist = sp.create_playlist(user_id, name)

    # TODO check the returned dict has id key
    playlist_id = playlist['id']

    track_uris = [track['uri'] for track in tracks]

    for i in range(math.ceil(len(track_uris)/100)):
        # TODO check that each request is made successfully
        sp.add_items_playlist(playlist_id, track_uris[i*100:(i+1)*100])

    return {"info": "Request successful", "Error": 0}


def top_ten(user: str, time_range: str) -> dict:
    """
    :arg user: The user to get the songs of (Required)
    :arg time_range: The range to get the songs for (Required)
    :return dict: The top 10 songs
    Gets the top 10 tracks for the user
    """

    scope = "user-top-read"
    if computations.check_user(user, scope):
        return {"info": [], "Error": "Error, user not authenticated for request, use command `+setup all`"}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    response = sp.top_tracks(f"{time_range}_term", 10)

    # TODO check the returned tracks are of form expected
    tracks = response['items']

    return {"info": tracks, "Error": 0}


async def genres(user: str, artists: list[str]) -> list:
    """
    :arg user: The id of the user (Required)
    :arg artists: List of artists to get the genre of (Required)
    :return list: The list of genres
    Gets the genres of a given list of artist
    """
    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Initiate the APIReq class to interact with the api
    sp = spotifyapi.APIReq(code)

    genre_list = []

    artist_list = sp.get_artists(artists)

    # TODO check the response is of form expected
    artists = artist_list['artists']
    for artist in artists:
        genre_list += artist['genres']

    return list(set(genre_list))


async def get_playlist_songs(user: str, playlist_id: str, private: bool, sp: spotifyapi.APIReq = None) -> dict:
    """
    :arg user: The user to authenticate (Required)
    :arg playlist_id: The id of the playlist to get songs for (Required)
    :arg private: Whether the playlist is private or not (Required)
    :arg sp: An instance of the spotify api APIReq class for use (Optional)
    :return dict: The dict of songs in the playlist
    Gets all the songs in a playlist
    """
    if sp is None:
        scope = ""
        if private:
            scope = "playlist-read-private"

        if computations.check_user(user, scope):
            return {"info": [],
                    "Error": f'''```User has wrong scope
    re-authenticate using the `+setup all` command please```'''}

        # Get the auth code
        if scope != "":
            code = spotifyapi.init(redirect_uri, user, scope=scope, save_func=computations.save_user,
                                   read_func=computations.get_user, update_func=computations.update_user,
                                   check_func=computations.check_user_exist)
        else:
            code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                                   read_func=computations.get_user, update_func=computations.update_user,
                                   check_func=computations.check_user_exist)

        # Initiate the APIReq class to interact with the api
        sp = spotifyapi.APIReq(code)

    # Get the total number of songs on the playlist
    response = sp.get_tracks_playlist(playlist_id, 1)

    # TODO check that response has total key
    total = response['total']

    # Create a list of requests to be made
    requests = [[100, i*100] for i in range(math.ceil(total/100))]

    # Create list of requests in chunks of 50
    request_chunks = [requests[i*50: (i+1)*50] for i in range(math.ceil(len(requests)/50))]

    tracks = []

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for request_set in request_chunks:
            songs, wait_time = await get_tracks(request_set, loop, executor, sp, playlist_id)
            while wait_time is not None:
                await asyncio.sleep(int(wait_time))
                songs, wait_time = await get_tracks(request_set, loop, executor, sp, playlist_id)

            tracks += songs

    return {'info': tracks, 'Error': 0}


async def get_artists(user: str, playlist: str) -> dict:
    """
    :arg user: The user id (Required)
    :arg playlist: The id of the playlist to look at (Required)
    :return dict: Info about the artists
    Gets the artists in a playlist
    """
    # If the user isn't in the database send an error
    if not computations.check_user_exist(user):
        return {"info": [],
                "Error": f'''```User doesn't exist
    authenticate using the `+setup all` command please```'''}

    playlist_id = computations.uri_to_id(playlist)

    tracks = await get_playlist_songs(user, playlist_id, False)

    # Get all the artists for the tracks
    artists = []
    for track in tracks['info']:
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
    :arg user: The id of the user to get the current song of (Required)
    :return dict: Info about the current song
    Gets the current song the user is playing
    """
    # If the user isn't in the database send an error
    if not computations.check_user_exist(user):
        return {"info": [],
                "Error": f'''```User doesn't exist
    authenticate using the `+setup all` command please```'''}

    # Get the auth code
    code = spotifyapi.init(redirect_uri, user, save_func=computations.save_user,
                           read_func=computations.get_user, update_func=computations.update_user,
                           check_func=computations.check_user_exist)

    # Create an APIReq instance
    sp = spotifyapi.APIReq(code)

    # Get the information about the user's playback
    info = sp.get_info_playback()

    if 'item' not in info:
        return {"info": [], "Error": "```The request failed, make sure that you have an active"
                                     " device and are a premium user```"}

    # Create a string holding the song name and artist
    search = [info['item']['name'], info['item']['artists'][0]['name']]

    # Return the information
    return {"info": search, "Error": 0}


async def get_tracks(request_set: list, loop: asyncio.AbstractEventLoop,
                     executor,
                     sp: spotifyapi.APIReq, playlist_id: str) -> list[list, int]:
    """
    :arg request_set: The set of requests (Required)
    :arg loop: The asyncio loop (Required)
    :arg executor: The executor from concurrent.futures to run the requests in (Required)
    :arg sp: Instance of the spotify api class to make requests to (Required)
    :arg playlist_id: The id of the playlist to get (Required)
    :return list: A list of the songs returned by the requests
    Makes requests with asyncio, with pauses when a timeout error
    occurs so that all songs are fetched
    """
    print(f"Started fetching ~{len(request_set)*100} songs")
    fetched_tracks = []
    futures = []
    wait_time = None
    for request in request_set:
        futures.append(loop.run_in_executor(executor,
                                            sp.get_tracks_playlist, playlist_id,
                                            *request))

    for future in futures:
        songs = await future
        # TODO add other error handling for case where not expected
        # TODO but not with a time_out
        if 'time_out' in songs:
            # Failed request
            wait_time = songs['time_out']
        else:
            fetched_tracks += songs['items']

    print("Finished fetching songs")
    return [fetched_tracks, wait_time]
