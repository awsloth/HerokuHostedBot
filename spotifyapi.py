# Import base libraries
import webbrowser
import time
import os
import json

# Import pip library
import requests

# Import from libraries
from base64 import b64encode
from urllib import parse
from typing import Callable
from functools import wraps

# Constant for time taken to timeout
TIMEOUT_TIME = 3600


# Type_check decorator used to check the arguments of the required type
def type_check(func: Callable) -> Callable:
    """
    :arg func: The function the decorator is assigned to (Required)
    :return Callable: The function combined with the decorator
    Adds the decorator to the function decorated with it
    """
    # noinspection PyUnresolvedReferences
    @wraps(func)
    def wrapper(*args: list, **kwargs: dict):
        """
        :arg args: The list of arguments
        :arg kwargs: The dict of arguments
        :return func_return: The return value of the decorated function
        Checks each argument against the type hints and
        rejects it if not the correct type
        """
        # Check the arguments for the function
        argument = func.__annotations__

        # Check through the given named arguments
        for key in kwargs:
            # If the named variable is not in the
            # specified variables raise an error
            if key not in argument:
                raise TypeError(f"Unknown argument {key}")
            # If the value is not of the type hinted type refuse call
            if not isinstance(kwargs[key], argument[key]):
                arg_type = str(argument[key]).replace("<class ", '')[1:-2]
                raise TypeError(f"{key} should be of type {arg_type}")

        # If the first argument is a
        # self argument remove from list
        if isinstance(args[0], object):
            arguments = args[1:]
        else:
            arguments = args

        # Go through the values in order
        for i in range(len(arguments)):
            # If the value is not of the type hinted type refuse call
            if not isinstance(arguments[i], list(argument.values())[i]):
                spec_arg = list(argument.keys())[i]
                arg_type = str(list(argument.values())[i])
                arg_type = arg_type.replace("<class ", '')[1:-2]
                raise TypeError(f"{spec_arg} should be of type {arg_type}")

        # If all arguments are of the type hinted go ahead with the request
        return func(*args, **kwargs)

    # Return the new function
    return wrapper


# OAuth class to organise functions for OAuth
class OAuth:
    """
    A class to deal with the spotify OAuth and get an access token
    """
    def __init__(self, cli_id: str, cli_secret: str,
                 red_uri: str, req_scope: str = None) -> None:
        """
        :arg cli_id: The spotify application client id (Required)
        :arg cli_secret: The spotify application client secret (Required)
        :arg red_uri: The uri to redirect the user to after
                      authorising the application (Required)
        :arg scope: The scope for the application to use (Optional)
        :return None:
        Init function for the OAuth class
        """
        # Define the 4 variables required to do oauth requests
        self.client_id = cli_id
        self.client_secret = cli_secret
        self.redirect_uri = red_uri
        self.scope = req_scope

    def grab_code(self) -> str:
        """
        :return str: The url of the site to visit
        Grabs the website so that the user can authorise the application
        """
        # Variables to pass the website
        variables = [f"client_id={self.client_id}", "response_type=code",
                     f"redirect_uri={self.redirect_uri}",
                     f"scope={self.scope}" if self.scope is not None else None]

        # Join the website parameters with a '&'
        params = "&".join(filter(None, variables))

        # Request the site
        r = requests.get("https://accounts.spotify.com/authorize?"+params)

        # Return the url
        return r.url

    def grab_token(self, code: str) -> dict:
        """
        :arg code: The code given by the redirect page after
                   the user authorises use (Required)
        :return dict: The tokens stored in a dictionary
        Grabs the tokens given the basic authentication
        code so the api can be used
        """
        # Body dict to provide arguments to the website
        body = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
            }
        # Convert body into url encoded text
        encoded = parse.urlencode(body)

        # Headers dict outlining the Authorisation
        auth = {
            "Authorization": "Basic "+encode_client(self),
            "Content-Type": "application/x-www-form-urlencoded"
            }

        # Send request to the api
        r = requests.post("https://accounts.spotify.com/api/token",
                          headers=auth, data=encoded)

        # Return tokens
        return r.json()

    def grab_token_refresh(self, refresh_tok: str) -> dict:
        """
        :arg refresh_tok: Token received that deals with
                          refreshing authentication token (Required)
        :return dict: The dict holding the new token
        Performs the steps to get a new authentication
        token with the refresh token
        """
        # Body dict to provide arguments to the website
        body = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_tok
            }

        # Convert body into url encoded text
        encoded = parse.urlencode(body)

        # Headers dict outlining the Authorisation
        auth = {
            "Authorization": "Basic "+encode_client(self),
            "Content-Type": "application/x-www-form-urlencoded"
            }

        # Send request to the api
        r = requests.post("https://accounts.spotify.com/api/token",
                          headers=auth, data=encoded)

        # Return tokens
        return r.json()

    def first_run(self, auto_open: bool = True) -> dict:
        """
        :arg auto_open: determines whether the function prints the link
                        or opens it using the web browser module (Optional)
        :return dict: The tokens received from running through the OAuth
        Performs the steps to authorise a session and returns the tokens
        """

        # Show the user the Authorisation page to authorise application
        auth_url = self.grab_code()
        print("After redirect paste url here:")

        # If the user turned auto open off print the link
        if auto_open:
            webbrowser.open(auth_url)
        else:
            print(auth_url)

        auth_code = input()[len(self.redirect_uri)+6:]

        # Grab the tokens with the code given
        tokens = self.grab_token(auth_code)

        # Return the tokens
        return tokens


# API request class to make requests to the spotify api
class APIReq:
    """
    A class to make requests to the Spotify API
    """
    @type_check
    def __init__(self, auth_token: str) -> None:
        """
        :arg auth_token: The authorization token from spotify
        :return None:
        Sets up the API request class to make requests to the Spotify API
        """
        # Create the variable base to store the base of the url for spotify api
        self.base = "https://api.spotify.com/v1/"

        # Create the base headers with the auth token for verification
        self.headers = {
            "Authorization": f"Bearer {auth_token}"
            }

    @type_check
    def follow_playlist(self, playlist_id: str, private: bool = False) -> str:
        """
        :arg playlist_id: The id of the spotify playlist to follow (Required)
        :arg private: Whether the playlist to follow is
                      private or not (Optional)
        :return str: Success if request worked, else the
                     error associated with the request
        Follows the given spotify playlist
        """
        # Create the url for the request with the specified id
        url = f"{self.base}playlists/{playlist_id}/tracks"

        # Add a new header with the content type identifier
        header = self.headers.copy()
        header.update({"Content-Type": "application/json"})

        # Create a body holding the arguments
        body = {
            "public": "false" if private else "true"
            }

        # Turn the body into json format
        body = json.dumps(body)

        # Create the request and get the body contents
        r = requests.put(url, data=body, headers=header).content

        # If the body was blank return success else return the generated error
        return r if r else "Success"

    @type_check
    def unfollow_playlist(self, playlist_id: str,
                          private: bool = False) -> str:
        """
        :arg playlist_id: The id of the spotify playlist
                          to unfollow (Required)
        :arg private: Whether the playlist to unfollow is
                      private or not (Optional)
        :return str: Success if request worked,
                     else the error associated with the request
        Unfollows the given spotify playlist
        """
        # Creates the url for the request
        url = f"{self.base}playlists/{playlist_id}/tracks"

        # Add a new header with the content type identifier
        header = self.headers.copy()
        header.update({"Content-Type": "application/json"})

        # Create a body holding the arguments
        body = {
            "public": "false" if private else "true"
            }

        # Turn the body into json format
        body = json.dumps(body)

        # Create the request and get the body contents
        r = requests.delete(url, headers=header, data=body).content

        # If the body was blank return success else return the generated error
        return r if r else "Success"

    @type_check
    def add_items_playlist(self, playlist_id: str,
                           uris: list, position: int = None) -> dict:
        """
        :arg playlist_id: The id of  the spotify playlist to
                          add items to (Required)
        :arg uris: A list of string uris referring to the spotify tracks
                    to be added to the playlist (Required)
        :arg position: The position for the song to inserted into (Optional)
        :return dict: The json returned by the request
        Adds songs to the specified playlist at the given index or at the end
        """
        # Creates the url for the request
        url = f"{self.base}playlists/{playlist_id}/tracks"

        # Add a new header with the content type identifier
        header = self.headers.copy()
        header.update({"Content-Type": "application/json"})

        # Create a body holding the arguments
        body = {
            "uris": uris
            }
        if position is not None:
            body.update({"position": position})

        body = json.dumps(body)

        # Create the request and grab the returned json file
        r = requests.post(url, headers=header, data=body).json()

        return r

    @type_check
    def change_details_playlist(self, playlist_id: str,
                                name: str = None, public: bool = None,
                                collaborative: bool = None,
                                description: str = None) -> str:
        """
        :arg playlist_id: The id of the playlist to
                          change details about (Required)
        :arg name: The new name of the given playlist (Optional)
        :arg public: Whether to make the playlist public or not (Optional)
        :arg collaborative: Whether to make the playlist
                            collaborative or not (Optional)
        :arg description: The new description of the playlist (Optional)
        :return str: Success if request worked,
                     else the error associated with the request
        Changes details about the playlist like description,
        name and publicity (optional)
        """
        # Creates the url for the request
        url = f"{self.base}playlists/{playlist_id}"

        # Add a new header with the content type identifier
        header = self.headers.copy()
        header.update({"Content-Type": "application/json"})

        # Create a body for holding the arguments
        body = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("name", "public", "collaborative", "description")
        args = (name, public, collaborative, description)
        arg_values = (name, "true" if public else "false",
                      "true" if collaborative else "false", description)

        for i in range(len(args)):
            if args[i] is not None:
                body.update({arg_names[i]: arg_values[i]})

        body = json.dumps(body)

        # Create the request and get the body contents
        r = requests.put(url, headers=header, data=body).content

        # If the body was blank return success else return the generated error
        return r if r else "Success"

    @type_check
    def create_playlist(self, user_id: str, name: str,
                        public: bool = None, collaborative: bool = None,
                        description: str = None) -> dict:
        """
        :arg user_id: The user id to add the playlist to (Required)
        :arg name: The name of the created playlist (Required)
        :arg public: Whether the playlist will be public or not (Optional)
        :arg collaborative: Whether the playlist created
                            will be public or not (Optional)
        :arg description: The description of the created playlist (Optional)
        :return dict: The json returned by the request
        Creates a new playlist with given the parameters
        """
        # Creates the url for the request
        url = f"{self.base}users/{user_id}/playlists"

        # Add a new header with the content type identifier
        header = self.headers.copy()
        header.update({"Content-Type": "application/json"})

        # Create a body for holding the arguments
        params = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("name", "public", "collaborative", "description")
        args = (name, public, collaborative, description)
        arg_values = (name, "true" if public else "false",
                      "true" if collaborative else "false", description)

        # Loop through arguments and add to body if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: arg_values[i]})

        body = json.dumps(params)

        # Create the request and grab the returned json file
        r = requests.post(url, headers=header, data=body).json()

        return r

    @type_check
    def get_playlist(self, playlist_id: str) -> dict:
        """
        :arg playlist_id: The id of the playlist to get (Required)
        :return dict: The json returned by the request
        Gets the playlist from the id
        """
        # Creates the url for the request
        url = f"{self.base}playlists/{playlist_id}"

        # Create the request and grab the returned json file
        r = requests.get(url, headers=self.headers).json()

        return r

    @type_check
    def get_tracks_playlist(self, playlist_id: str, limit: int = None,
                            offset: int = None) -> dict:
        """
        :arg playlist_id: The id of the playlist to get (Required)
        :arg limit: The max number of tracks to get (max 100) (Optional)
        :arg offset: The index to start the tracks from (Optional)
        :return dict: The json returned by the request, with the tracks
        Gets the playlist tracks within the specified range
        """
        # Creates the url for the request
        url = f"{self.base}playlists/{playlist_id}/tracks"

        # Create a params dict for holding the arguments
        params = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("limit", "offset")
        args = (limit, offset)

        # Loop through arguments and add to dict if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: args[i]})

        # Create the request
        r = requests.get(url, params=params, headers=self.headers)

        # If the request failed, return the header for timeout time
        if 'items' not in r.json():
            return {'time_out': r.headers['retry-after'],
                    'params': [playlist_id, limit, offset]}

        return r.json()

    @type_check
    def top_tracks(self, time_range: str = None, limit: int = None,
                   offset: int = None) -> dict:
        """
        :arg time_range: The time range to get the top tracks
                         for (long, medium or short _term) (Optional)
        :arg limit: The number of tracks to get (max 50) (Optional)
        :arg offset: The index to start at (max 49) (Optional)
        :return dict: The json holding the top tracks
        Gets the top tracks for the specified range
        """
        # Creates the url for the request
        url = f"{self.base}me/top/tracks"

        # Create a params dict for holding the arguments
        params = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("time_range", "limit", "offset")
        args = (time_range, limit, offset)

        # Loop through arguments and add to dict if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: args[i]})

        # Create the request and grab the returned json file
        r = requests.get(url, params=params, headers=self.headers).json()

        return r

    @type_check
    def top_artists(self, time_range: str = None,
                    limit: int = None, offset: int = None) -> dict:
        """
        :arg time_range: The time range to get the top artists
                         for (long, medium or short _term) (Optional)
        :arg limit: The number of artists to get (max 50) (Optional)
        :arg offset: The index to start at (max 49) (Optional)
        :return dict: The json holding the top artists
        Gets the top artists for the specified range
        """
        # Creates the url for the request
        url = f"{self.base}me/top/artists"

        # Create a params dict for holding the arguments
        params = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("time_range", "limit", "offset")
        args = (time_range, limit, offset)

        # Loop through arguments and add to dict if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: args[i]})

        # Create the request and grab the returned json file
        r = requests.get(url, params=params, headers=self.headers).json()

        return r

    @type_check
    def get_users_playlists(self, limit: int = None,
                            offset: int = None) -> dict:
        """
        :arg limit: The number of playlists to get (max 50) (Optional)
        :arg offset: The index to start getting
                     the playlists at (Optional)
        :return dict: The json object returned by the
                      request holding the playlists
        Gets the users playlists
        """
        # Creates the url for the request
        url = f"{self.base}me/playlists"

        # Create a params dict for holding the arguments
        params = {}

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("limit", "offset")
        args = (limit, offset)

        # Loop through arguments and add to dict if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: args[i]})

        # Create the request and grab the returned json file
        r = requests.get(url, params=params, headers=self.headers).json()

        return r

    @type_check
    def genres_recommend(self) -> dict:
        """
        :return dict: The dict containing the available genres
        Gets the available genre seeds from the api
        """
        # Creates the url for the request
        url = f"{self.base}recommendations/available-genre-seeds"

        # Create the request and grab the returned json file
        r = requests.get(url, headers=self.headers).json()

        return r

    @type_check
    def get_tracks(self, id_list: list) -> dict:
        """
        :arg id_list: A list of ids (max 50) (Required)
        :return dict: A dict containing the song items
        Gets the information about multiple tracks from a list of ids
        """
        # Creates the url for the request
        url = f"{self.base}tracks"

        if len(id_list) > 50:
            return {"Error": "Error, too many ids"}

        # Set parameters holding the ids
        params = {"ids": ",".join(id_list)}

        # Create the request and grab the returned json file
        r = requests.get(url, params=params, headers=self.headers).json()

        return r

    @type_check
    def get_info_playback(self) -> dict:
        """
        :return dict: The info about the playback
        Grabs the information about a users playback from the api
        """
        # Creates the url for the request
        url = f"{self.base}me/player"

        # Create the request and get the returned json
        r = requests.get(url, headers=self.headers).json()

        return r

    @type_check
    def add_track_playback(self, track_uri: str) -> str:
        """
        :arg track_uri: track uri to add to the user's playback (Required)
        :return str: Whether the request succeeded
        Adds a track to the current user's playback
        """
        # Creates the url for the request
        url = f"{self.base}me/player/queue"

        # Create the parameter for the request
        params = {"uri": track_uri}

        # Create the request to the site
        r = requests.post(url, params=params, headers=self.headers)

        # Check the status of the request and return the meanings
        if r.status_code == 403:
            return "Error, not a premium user"
        elif r.status_code == 404:
            return "Error, device not found"

        # If the request was successful return as such
        return "Successful"

    @type_check
    def pause_playback(self) -> str:
        """
        :return str: Returns the result of the request
        Pauses a user's playback
        """
        # Creates the url for the request
        url = f"{self.base}me/player/pause"

        # Create the request to the site
        r = requests.put(url, headers=self.headers)

        # Check the status of the request and return the meanings
        if r.status_code == 403:
            return "Error, not a premium user"
        elif r.status_code == 404:
            return "Error, device not found"

        # If the request was successful return as such
        return "Successful"

    @type_check
    def get_recommendations(self, limit: int = None, artists: list = None,
                            genres: list = None, tracks: list = None) -> dict:
        """
        :arg limit: The number of songs to return (max 100)
        :arg artists: Artists for the seed
        :arg genres: Genres for the seed
        :arg tracks: Tracks for the seed
        :return dict: The dictionary holding the recommended songs
        Returns recommended songs based upon the entered values
        """
        # Create the url for the request
        url = f"{self.base}recommendations"

        # Create params with limit if limit argument given
        params = {}
        if limit is not None:
            params.update({"limit": limit})

        # Define the argument names and values to
        # check whether they were entered
        arg_names = ("seed_artists", "seed_genres", "seed_tracks")
        args = (artists, genres, tracks)

        # Loop through arguments and add to dict if entered
        for i in range(len(args)):
            if args[i] is not None:
                params.update({arg_names[i]: ",".join(args[i])})

        # Create the request and get the returned json
        r = requests.get(url, headers=self.headers, params=params).json()

        return r

    @type_check
    def get_user(self) -> dict:
        """
        :return dict: Information about the user
        Gets information about the current user
        """
        # Create url
        url = f"{self.base}me"

        # Create the request and get the returned json
        r = requests.get(url, headers=self.headers).json()

        return r

    @type_check
    def get_artists(self, ids: list) -> dict:
        """
        :arg ids: A list of track ids
        :return dict: The dictionary with information about the artists
        Gets the artists corresponding to the ids
        """
        # Create url
        url = f"{self.base}artists"

        # Create parameters
        params = {'ids': ",".join(ids)}

        # Create the request and get the returned json file
        r = requests.get(url, params=params, headers=self.headers).json()

        return r


# Functions
def encode_client(client_inst: OAuth) -> str:
    """
    :arg client_inst: An instance of the OAuth class (Required)
    :return str: The base64 encoded string
    Encodes the client id and secret into base64 for use as Authorisation
    """
    # Join the client id and secret into format:
    # client_id:client_secret
    joined_client = ":".join((client_inst.client_id,
                              client_inst.client_secret))

    # Encode the result and d and ' from d'...'
    encoded_client = b64encode(joined_client.encode('utf-8'))
    encoded_client = f"{encoded_client}"[2:-1]

    # Return formatted and encoded string
    return encoded_client


# Function to save user data
def save_data(user: str, auth_token: str, refresh_token: str,
              time_left: float, scope: str):
    """
    :arg user: The user to save the data for
    :arg auth_token: The auth token for the user
    :arg refresh_token: The refresh token for the user
    :arg time_left: The time left that the auth token is valid for
    :arg scope: The scope the user is authenticated for
    Saves the given data in a file for later use
    """
    # Create file name string
    file_name = fr"\\{user}.cache"

    # Define file_location
    file_location = f"{os.getcwd()}\\cache"

    # Create directory if not already existent
    os.makedirs(f"{file_location}", exist_ok=True)

    # Save details
    with open(f"{file_location}{file_name}", "w") as f:
        print(auth_token, refresh_token, time_left,
              scope, sep='\n', file=f)


# Function to read user data
def read_data(user: str) -> list:
    """
    :arg user: The user whose data is going to be read
    :return list: A list containing the data about the user
    Reads the data from the user's file
    """
    # Define file_location
    file_location = f"{os.getcwd()}\\cache"
    with open(f"{file_location}\\{user}.cache") as f:
        contents = [line.rstrip() for line in f.readlines()]

    return contents


# Function to check user's data exists
def check_user(user: str) -> bool:
    """
    :arg user: The user to check the data for
    :return bool: Whether the user has data stored about them
    A function that checks through the stored files to check
    if the user has a file
    """
    # Define file_location
    file_location = f"{os.getcwd()}\\cache"

    # Create file name string
    file_name = f"{user}.cache"

    # If file name in the files at the location
    return file_name in os.listdir(file_location)


@type_check
def init(redirect_uri: str, user: str,
         client_id: str = None, client_secret: str = None,
         scope: str = None, save_func: Callable = save_data,
         read_func: Callable = read_data, update_func: Callable = save_data,
         check_func: Callable = check_user) -> str:
    """
    :arg redirect_uri: The uri to redirect the user to when
                       making the request (Required)
    :arg user: For handling multiple users (Required)
    :arg client_id: The client_id of your application, if not given will
                    search for SPOTIFY_ID in environment variables (Optional)
    :arg secret_id: The client_secret of your application, if not given will
                    search for SPOTIFY_SECRET in environment
                    variables (Optional)
    :arg scope: The scope for the request (Optional)
    :arg file_loc: The location to hold the token file (Optional)
    :arg save_func: A function to save user data, must take user,
                    authentication token, refresh token, time and
                    scope as inputs (Optional)
    :arg read_func: A function to read user data, must take user as
                    argument and return stored data about them (Optional)
    :arg update_func: A function to update user data, must take user,
                      authentication token, refresh token, time and
                      scope as inputs (Optional)
    :arg check_func: A function to check whether a user's data is
                     stored already or not takes user as the
                     argument True if stored else False (Optional)
    :return str: The token needed to make requests
    Initialises the program so that requests can be made
    and gives the access token
    """
    # If the user is stored already grab the existing data
    # else set new_user to false
    if check_func(user):
        access_token, refresh_token, time_left, verified_scope = read_func(user)
    else:
        # Define variables for editor
        access_token = None
        refresh_token = None
        time_left = None
        verified_scope = ""

    # If the user didn't enter their id or secret
    # attempt to get it from the environment variables
    if client_id is None:
        client_id = os.getenv('SPOTIFY_ID')

    if client_secret is None:
        client_secret = os.getenv('SPOTIFY_SECRET')

    # Tests if requested scope is subset of available scope
    if scope is not None:
        scope_st = set(scope.split())
    else:
        scope_st = set()

    # Create instance of OAuth class to handle OAuth
    client = OAuth(client_id, client_secret, redirect_uri, scope)

    # If scope unsuitable, run out of time or new user re-request tokens
    if (
            (not check_func(user)) or
            (not scope_st.issubset(set(verified_scope.split())) and scope != "")
    ):
        # Grab the json from the api
        response = client.first_run()

        # Grab the tokens and scope from the api
        access_token = response['access_token']
        refresh_token = response['refresh_token']

        # If there was an entered scope get it
        if 'scope' in response:
            scope = response['scope']

        # Set the time to a new time as token just received
        time_left = time.time()

    elif not time.time() - TIMEOUT_TIME < float(time_left):
        # Grab the json from the api
        response = client.grab_token_refresh(refresh_token)

        # Grab the tokens and scope from the api
        access_token = response['access_token']

        # If there was an entered scope get it
        if 'scope' in response:
            scope = response['scope']

        # Set the time to a new time as token just received
        time_left = time.time()

    else:
        # Set scope as prior scope
        # so all available functions can be used
        scope = verified_scope

    if check_func(user):
        update_func(user, access_token, refresh_token, time_left, scope)
    else:
        save_func(user, access_token, refresh_token, time_left, scope)

    # Return the auth token
    return access_token
