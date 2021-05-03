# Import standard libraries
import os
import asyncio
import sys
import time
import typing

# Import 3rd party libraries
import discord

# Import from libraries
from discord.ext import commands

# Import custom scripts
import spotifyapi
import spotifyauth
import computations

# Load the env file containing the discord bot token
TOKEN = os.getenv('DISCORD_TOKEN')

# Set discord intents to all (Need to specify later)
intents = discord.Intents.all()

# Initialise the bot with the '+' prefix and all intents
bot = commands.Bot(command_prefix='+', intents=intents)

# Create the message to send to the user
message = '''```I'm going to send you a link
Open the link and sign into your Spotify account
Then accept the bot access
After redirect to the localhost site copy the new url and paste here```'''


# Function for dealing with reactions
async def auth_scope(ctx, command, req_scope):
    message = f"The command {command} requires {' '.join(req_scope)}"
    msg = await ctx.send(message+", do you want to authenticate this scope?")

    await msg.add_reaction("\N{THUMBS UP SIGN}")
    await msg.add_reaction("\N{THUMBS DOWN SIGN}")

    def check(reaction, user):
        return (
                (ctx.message.author == user) and
                (msg == reaction.message) and
                (str(reaction.emoji) in ["👍", "👎"])
                )

    try:
        reaction, user = await bot.wait_for('reaction_add',
                                            timeout=120.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send(f"Timed out {i}")

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

        ########################################################
        ##                                                    ##
        ##            Clean this function up                  ##
        ##                                                    ##
        ########################################################

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
        command_names = ['compare', 'sleep']
        scope = []
        for scope_type in scopes:
            required_scope = scope_translate[scope_type]
            if scope_type in command_names:
                if await auth_scope(ctx, scope_type, required_scope):
                    scope += required_scope
            else:
                scope += required_scope
        scope = " ".join(set(scope))
        # If the user is new, set the user up,
        # else show they have already set up
        if computations.check_user(ctx.author.id, scope):
            # Send the user the message to explain what to do
            await ctx.author.send(message)

            # Get the url and instance of oauth
            # to authorise the user
            url, oauth = spotifyauth.get_url(scope)

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

            # Print the response (For debug purposes)
            print(response)

            # If there is no access token, then error has occured
            # and show the error
            if 'access_token' not in response:
                await ctx.author.send(''' ```Error with url, try again
Make sure url takes the form http:/localhost:8080/... or localhost:8080/...```''')
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

            # Save details to a file
            with open(fr"cache\{ctx.author.id}.cache", "w") as f:
                print(access_token, refresh_token, time_left,
                      scope, sep='\n', file=f)

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
        # Cache file location
        file = f"cache\\{ctx.author.id}.cache"

        # If the file exists remove it
        if os.path.exists(file):
            os.remove(file)
            await ctx.send("Removed all information")
        else:
            await ctx.send("All information already removed")


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

        # If an error occured, send the error to the user
        if not info['Error'] == 0:
            await ctx.send(info['Error'])
            return -1

        # Get the overlap, overlap percentage and songs
        overlap_perc = info['info']['percentage']
        overlap = info['info']['total']
        song_details = info['info']['songs']

        # Show the user the overlap and songs
        await ctx.send(f"You have a {overlap_perc}% overlap, or {overlap} songs")

        # Form inline code message to show song names and artists
        messages = computations.form_message([f"{name} by {artist}" for name, artist in song_details])
            
        for message in messages:
            await ctx.send(message)

    @commands.command(name='sleep')
    async def sleep_timer(self, ctx, time, fade_time: typing.Union[int, None]):
        """
        Stops music playing after given time,
        but waits until the end of the track
        :arg time: Time to wait before sleeping (HH:MM:SS)
        :arg fade_time: The fade time set in spotify settings between songs
        """
        # Split up the time into hours, mins and secs
        hours, minutes, seconds = map(int, time.split(":"))

        # Calculate the total time in seconds
        total_time_secs = hours*3600+minutes*60+seconds

        await ctx.send("Waiting to sleep")
        result = await spotifyauth.sleep_timer(ctx.author.id,
                                               total_time_secs, fade_time)
        await ctx.send(result)

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
        :arg source: A playlist id or a list of song/artist ids (max 5)
        """
        source = [computations.link_to_uri(link) for link in source]
        recs = spotifyauth.get_recommendations(str(ctx.author.id),
                                               number, source)
        if not isinstance(recs, dict):
            await ctx.send(recs)
            return -1

        track_info = [[tracks['name'], tracks['artists'][0]['name']] for track in recs['tracks']]

        if output.lower() == "dm":
            # Form inline code message to show song names and artists
            messages = computations.form_message([f"{name} by {artist}" for name, artist in track_info])
                
            for message in messages:
                await ctx.author.send(message)

        elif output.lower() == "queue":
            # add tracks to queue
            await ctx.send(spotifyauth.add_to_queue(str(ctx.author.id),
                                                    tracks))

        elif output.lower() == "playlist":
            # Create/add to a playlist with recommended tracks
            await ctx.send(spotifyauth.create_playlist(str(ctx.author.id),
                                                       tracks))

    @commands.command(name='artists')
    async def artists(self, ctx, playlist: str):
        """
        Displays artists in playlist
        :arg playlist: A playlist link, id or uri
        """
        #artist = await spotifyauth.get_track(playlist)
        #await ctx.send(artists)
        await ctx.send("In the works pls be patient")

    @commands.command(name='top10')
    async def top10(self, ctx, time_range: str):
        """
        Shows your top 10 songs ever, past 6 months and past 2 weeks
        :arg time_range: Range for top songs (long, medium, short)
        """
        options = ['long', 'medium', 'short']
        time_range = time_range.lower()
        
        if time_range not in options:
            await ctx.send(f"{time_range} not available, user 'long', 'medium' or 'short'")
            return -1
        
        songs = spotifyauth.topten(str(ctx.author.id), time_range)

        song_details = [[i, track['name'], track['artists'][0]['name']] for i, track in enumerate(songs)]

        # Form inline code message to show song names and artists
        messages = computations.form_message([f"{i+1}. {name} by {artist}" for i, name, artist in song_details])
            
        for message in messages:
            await ctx.send(message)

    @commands.command(name='genrecent')
    async def recent(self, ctx):
        """
        Shows the recent genres you have been listening to
        """
        
        songs = spotifyauth.topten(str(ctx.author.id), "short")

        artists = []
        for song in songs:
            for artist in song['artists']:
                artists.append(artist['id'])

        genres = await spotifyauth.genres(str(ctx.author.id), artists)

        # Form inline code message to show song names and artists
        messages = computations.form_message(sorted(list(genres)))
            
        for message in messages:
            await ctx.send(message)



# Add cogs to bot
bot.add_cog(AccountCommands())
bot.add_cog(SpotifyAPI())

# Run the bot
bot.run(TOKEN)
