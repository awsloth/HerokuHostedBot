# Import libraries
import requests
import bs4

# Import from libraries
from bs4 import BeautifulSoup

# Auth code for authorization
code = "_1YXXDNRoLkdYrWlMaVZcs4BwfX_srqX2duNPqsdSrVhe-Lea8kKuSSnGMDCQaCM"

# Header to prove identity to website
header = {"Authorization": f"Bearer {code}"}

# Base url of site
base = "http://api.genius.com"


def search(search_term: str) -> dict:
    """
    :arg search_term: The name of the song to find the lyrics for
    Searches through genius for the song and returns the dict
    """
    # Create url for request
    url = f"{base}/search?q={search_term}"

    # Create the request to get the lyrics url and get the json
    r = requests.get(url, headers=header).json()

    # Get the returned results
    results = r['response']['hits']

    return results


def encode_search(name: str, artist: str = None) -> str:
    """
    :arg name: Name of song
    :arg artist: Artist of song
    Encodes search for use in url
    """
    # Convert spaces to %20 for url
    if artist is not None:
        encoded_term = str(name+" "+artist).replace(" ", "%20")
    else:
        encoded_term = str(name).replace(" ", "%20")

    return encoded_term


def get_lyrics(search_term: str, artist: str = None) -> dict:
    """
    :arg search_term: The name of the song to find the lyrics for
    :arg artist: Artist of song
    :return list: A list containing the lines of the song
    Searches the genius website to get the lyrics of a song
    """
    print(search_term, artist)
    search_term = encode_search(search_term, artist)

    results = search(search_term)

    # If there are no results return an error
    if not len(results) > 0:
        return {"info": [], "Error": "Search term came up with no results, try again"}

    lyrics_url = None

    # Get the url from the results
    if artist is not None:
        found = False
        for result in results:
            name = [letter for letter in result['result']['primary_artist']['name'].lower() if ord(letter) != 8203]
            if artist.lower() in ''.join(name):
                lyrics_url = result['result']['url']
                found = True
                break
        if not found:
            return {'info': [], 'Error': 'Lyrics not found'}
    else:
        lyrics_url = results[0]['result']['url']

    # Get the returned html
    r = requests.get(lyrics_url)

    # Create a soup object with returned html
    soup = BeautifulSoup(r.content, features='lxml')

    # Attempt to find div with class lyrics
    lyrics_div = soup.find_all("div", {"class": "lyrics"})

    # If the div exists, go with the normal method
    # otherwise go with the alternative option
    if len(lyrics_div) > 0:
        # Find the child p element
        lyrics = lyrics_div[0].find("p")
        # Store the lines with <br/> cleared and separated by \n chars
        lines = lyrics.text.split("\n")

    else:
        # Find the lyrics div
        div = soup.find("div", {"class": "Lyrics__Container-sc-1ynbvzw-6 krDVEH"})
        tag_text = [child.text if not isinstance(child, bs4.NavigableString) else child for child in div.children]
        lines = list(filter(lambda x: x != '', tag_text))

    # Return the results
    return {"info": lines, "Error": 0}
