# Import standard libraries
import os
import asyncio
import time
import typing

# Import 3rd party libraries
import discord

# Import from libraries
from discord.ext import commands

# Import custom scripts
import spotifyauth
import computations
import genius

# Load the env file containing the discord bot token
TOKEN = os.getenv('DISCORD_TOKEN')

# Set discord intents to all (Need to specify later)
intents = discord.Intents.all()

# Initialise the bot with the '+' prefix and all intents
bot = commands.Bot(command_prefix='+', intents=intents)

# Create the message to send to the user
auth_message = '''```I'm going to send you a link
Open the link and sign into your Spotify account
Then accept the bot access
After redirect to the localhost site copy the new url and paste here```'''


# Function for dealing with reactions
async def auth_scope(ctx: discord.ext.commands.Context, command: str, req_scope: list) -> bool:
    """
    :arg ctx: discord context class for current event
    :arg command: The command being verified
    :arg req_scope: The scope required for the command
    :return bool: Whether the user verified it or not
    Allows the user to react to a message to show their response to a scope
    """
    # Create a message to show the user the commands they are agreeing to
    message = f"The command {command} requires {' '.join(req_scope)}"
    msg = await ctx.send(message+", do you want to authenticate this scope?")

    # Add the thumbs up and down signs to the message
    await msg.add_reaction("\N{THUMBS UP SIGN}")
    await msg.add_reaction("\N{THUMBS DOWN SIGN}")

    # Create a function to check whether the wanted conditions are met
    def check(s_reaction, s_user):
        return (
                (ctx.message.author == s_user) and
                (msg == s_reaction.message) and
                (str(s_reaction.emoji) in ["👍", "👎"])
                )

    # Wait for the user to complete the actions needed
    try:
        reaction, user = await bot.wait_for('reaction_add',
                                            timeout=120.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(f"Timed out")
        return False

    # If the user used thumbs up accept they agreed else not agreed
    if str(reaction) == "👍":
        await ctx.send("Scope accepted")
        return True
    else:
        await ctx.send("Scope not accepted")
        return False


# AccountCommands class, holds commands dealing with spotify accounts
class AccountCommands(commands.Cog):
    """
    The commands to do with the users account
    such as setting up and removing data
    """
    # Decorate command
    @commands.command(name='setup')
    async def setup_auth(self, ctx, *scopes):
        """
        Sets up a user so that songs can be compared
        :arg scopes: The scope for the bot to access:
        Scopes available:
            'all' - all scopes needed will be verified
            'read-only' - all scopes that involve reading
                            information about the user will be
                            verified (includes modify playback)
            'public-only' - only public scopes will be verified
            The name of a command will tell you the scopes for that command and
                ask if you want to verify for it
        """
        scope_translate = {'all': ['user-top-read', 'playlist-read-private',
                                   'playlist-modify-public',
                                   'user-modify-playback-state',
                                   'user-read-playback-state'],
                           'read-only': ['user-top-read',
                                         'playlist-read-private',
                                         'user-read-playback-state'],
                           'public-only': ['user-top-read',
                                           'user-read-playback-state'],
                           'compare': ['playlist-read-private'],
                           'sleep': ['user-modify-playback-state',
                                     'user-read-playback-state'],
                           'recs': ['user-modify-playback-state',
                                    'playlist-modify-public']}
        command_names = ['compare', 'sleep', 'recs']
        scope = []
        # For each scope type specified, add the scope referenced
        # and check if the scope type is a command that the scope is ok
        for scope_type in scopes:
            required_scope = scope_translate[scope_type]
            if scope_type in command_names:
                if await auth_scope(ctx, scope_type, required_scope):
                    scope += required_scope
            else:
                scope += required_scope

        # Create the scope as a string with only unique scopes
        scope = " ".join(set(scope))

        # If the user is new, set the user up,
        # else show they have already set up
        if computations.check_user(ctx.author.id, scope):
            # Send the user the message to explain what to do
            await ctx.author.send(auth_message)

            # Go through the setup steps with the spotify auth command
            response = await spotifyauth.setup_user(ctx, bot, scope)

            # If there is no access token, then error has occurred
            # and show the error
            if 'access_token' not in response:
                await ctx.send("`An error has occurred")
                return -1

            # Get the access and refresh token from the response
            access_token = response['access_token']
            refresh_token = response['refresh_token']

            # If the api returned a scope get that
            # or use the scope authorised
            if 'scope' in response:
                scope = response['scope']

            # Set time left to current time
            time_left = time.time()

            # Save details to database
            computations.save_user(ctx.author.id, access_token, refresh_token, time_left, scope)

            # Tell the user the authorisation process is complete
            await ctx.author.send("Successfully set up spotify account for use")

        else:
            # Tell the user the account is already set up
            await ctx.author.send("Account already set up")

    @commands.command('remove')
    async def remove_user(self, ctx):
        """
        Removes any stored information about you
        """
        # If the user exists in the system, remove them
        if computations.check_user_exist(ctx.author.id):
            computations.delete_user(ctx.author.id)

        # Show the user the information was deleted
        await ctx.send("Cleared Information")


class SpotifyAPI(commands.Cog):
    """
    The commands that involve you signing into your account
    """
    @commands.command(name='compare')
    async def compare_songs(self, ctx,
                            *users: typing.Union[discord.Member, str]):
        """
        Compares the music taste of the specified users
        :arg users: The users to compare the music tastes of.
                    To compare @ the user of use their discord id (Required)
        """
        # Get the overlap of the users songs
        user_ids = list(map(lambda x: x.id if not isinstance(x, str) else x, users))
        info = await computations.show_overlap(*user_ids)

        # If an error occurred, send the error to the user
        if not info['Error'] == 0:
            await ctx.send(info['Error'])
            return -1

        # Get the overlap, overlap percentage and songs
        overlap_percentage = info['info']['percentage']
        overlap = info['info']['total']
        song_details = info['info']['songs']

        # Show the user the overlap and songs
        await ctx.send(f"You have a {overlap_percentage}% overlap, or {overlap} songs")

        # Form inline code message to show song names and artists
        messages = computations.form_message([f"{name} by {artist}" for name, artist in song_details])

        # Send each separate message
        for message in messages:
            await ctx.send(message)

    @commands.command(name='sleep')
    async def sleep_timer(self, ctx, sleep_time):
        """
        Stops music playing after given time,
        but waits until the end of the track
        :arg time: Time to wait before sleeping (HH:MM:SS)
        """
        # Split up the time into hours, minutes and secs
        hours, minutes, seconds = map(int, sleep_time.split(":"))

        # Calculate the total time in seconds
        total_time_secs = hours*3600+minutes*60+seconds

        await ctx.send("Waiting to sleep")
        result = await spotifyauth.sleep_timer(ctx.author.id,
                                               total_time_secs)

        # If an error occurred, send the error to the user
        if not result['Error'] == 0:
            await ctx.send(result['Error'])
            return -1

        # Send the user the information
        await ctx.send(result['info'])

    @commands.command(name='recs')
    async def recommendations(self, ctx, number: int, output: str, *source):
        """
        Gets recommendations based upon input
        :arg number: The number of songs to recommend
        :arg output: Where to output:
                        'DM' - Dms the user all the song ids
                        'queue' - Adds the songs to the user's spotify queue
                        'playlist' - Creates or adds to an
                                        existing playlist holding the songs
        :arg source: A playlist link or a list of song/artist links (max 5)
        """
        # Convert the links to uris
        source = [computations.link_to_uri(link) for link in source]

        # Gets recommendations based upon the specified links
        recs = spotifyauth.get_recommendations(str(ctx.author.id),
                                               number, source)

        # If an error occurred show the error
        if recs['Error'] != 0:
            await ctx.send(recs['Error'])
            return -1

        # Grab the track info from the returned data
        track_info = [[tracks['name'], tracks['artists'][0]['name']] for tracks in recs['info']['tracks']]

        # Send the songs by the method specified by the user
        if output.lower() == "dm":
            # Form inline code message to show song names and artists
            messages = computations.form_message([f"{name} by {artist}" for name, artist in track_info])

            # Send each specified message
            for message in messages:
                await ctx.author.send(message)

        elif output.lower() == "queue":
            # add tracks to queue
            result = spotifyauth.add_to_queue(str(ctx.author.id),
                                              recs['info']['tracks'])

            # If an error occurred adding to queue, send the error
            if result['Error'] != 0:
                await ctx.send(result['Error'])
                return -1

            # Show the message showing the successful adding
            await ctx.send(result['info'])

        elif output.lower() == "playlist":
            # Create/add to a playlist with recommended tracks
            result = spotifyauth.create_playlist(str(ctx.author.id),
                                                 recs['info']['tracks'])

            # If an error occurred creating a playlist, send the error
            if result['Error'] != 0:
                await ctx.send(result['Error'])
                return -1

            # Show the message showing the successful adding
            await ctx.send(result['info'])

    @commands.command(name='artists')
    async def artists(self, ctx, playlist: str):
        """
        Displays the number or artists and top 10 artists and their percentage playlist
        :arg playlist: A playlist link, id or uri
        """
        # Get the artist's info
        artists = await spotifyauth.get_artists(str(ctx.author.id), computations.link_to_uri(playlist))

        # If there was an error send the error to thw user
        if artists['Error'] != 0:
            await ctx.send(artists['Error'])
            return -1

        # Get the artists info as a string
        artists_info = [f"{i+1}. {artist_info[0]} with {artist_info[1]}%" for i,
                        artist_info in enumerate(artists['info']['artists'])]

        # Form inline code message to show artist names and percentages
        messages = computations.form_message(artists_info+[f"Total artists: {artists['info']['Total']}"])

        # Send each message
        for message in messages:
            await ctx.send(message)

    @commands.command(name='top10')
    async def top10(self, ctx, time_range: str):
        """
        Shows your top 10 songs ever, past 6 months and past 2 weeks
        :arg time_range: Range for top songs (long, medium, short)
        """
        # Tuple showing each value
        options = ('long', 'medium', 'short')

        # If the time range is not one of the specified,
        # show an error and stop the command
        time_range = time_range.lower()
        if time_range not in options:
            await ctx.send(f"{time_range} not available, user 'long', 'medium' or 'short'")
            return -1

        # Get the top ten songs for the specified range
        songs = spotifyauth.top_ten(str(ctx.author.id), time_range)

        # If an error occurred send a message
        if songs['Error'] != 0:
            await ctx.send(songs['Error'])
            return -1

        # Get the song details
        songs = songs['info']
        song_details = [[i, track['name'], track['artists'][0]['name']] for i, track in enumerate(songs)]

        # Form inline code message to show song names and artists
        messages = computations.form_message([f"{i+1}. {name} by {artist}" for i, name, artist in song_details])

        # Send each message
        for message in messages:
            await ctx.send(message)

    @commands.command(name='topGenre')
    async def recent(self, ctx, time_range: str):
        """
        Shows the recent genres you have been listening to
        :arg time_range: Range for top songs (long, medium, short)
        """
        # Tuple showing each value
        options = ('long', 'medium', 'short')

        # If the time range is not one of the specified,
        # show an error and stop the command
        time_range = time_range.lower()
        if time_range not in options:
            await ctx.send(f"{time_range} not available, user 'long', 'medium' or 'short'")
            return -1

        # Get the songs in the specified range
        songs = spotifyauth.top_ten(str(ctx.author.id), time_range)

        # If an error occurred send a message
        if songs['Error'] != 0:
            await ctx.send(songs['Error'])
            return -1

        # Get the artist ids for all the songs
        songs = songs['info']
        artists = []
        for song in songs:
            for artist in song['artists']:
                artists.append(artist['id'])

        # Get the genres for all the ids
        genres = await spotifyauth.genres(str(ctx.author.id), list(set(artists)))

        # Form inline code message to show song names and artists
        messages = computations.form_message(sorted(list(genres)))

        # Send each message
        for message in messages:
            await ctx.send(message)

    @commands.command(name='lyrics')
    async def lyrics(self, ctx, *search):
        """
        Searches for lyrics of given song
        :arg search: The name (and artist) of the song
        """
        # Attempt to get the lyrics of the song from the genius website
        result = genius.get_lyrics(' '.join(search))

        # If an error occurred show the error
        if result['Error'] != 0:
            await ctx.send(result['Error'])
            return -1

        # Create inline text to show the info
        messages = computations.form_message(result['info'])

        # Send each message
        for message in messages:
            await ctx.send(message)

    @commands.command(nane='curLyrics')
    async def curLyrics(self, ctx):
        """
        Grabs the lyrics of the song being currently listened to
        """
        # Get the search value for the song
        search_term = spotifyauth.cur_song(str(ctx.author.id))

        # If an error occurred show as such
        if search_term['Error'] != 0:
            await ctx.send(search_term['Error'])
            return -1

        # Get the lyrics for the song
        result = genius.get_lyrics(*search_term['info'])

        # If an error occurred show the error
        if result['Error'] != 0:
            await ctx.send(result['Error'])
            return -1

        print(result['info'])

        # Create inline text to show the info
        messages = computations.form_message(result['info'])

        # Send each message
        for message in messages:
            await ctx.send(message)


# Add cogs to bot
bot.add_cog(AccountCommands())
bot.add_cog(SpotifyAPI())

# Run the bot
bot.run(TOKEN)
