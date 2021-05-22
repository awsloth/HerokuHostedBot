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

# TODO add more searches to try and get the correct song


def search(search_term: str) -> dict:
    """
    :arg search_term: The name of the song to find the lyrics for (Required)
    :return dict: A dict containing the result of the search
    Searches through genius for the song and returns the dict
    """
    # Create url for request
    url = f"{base}/search?q={search_term}"

    # Create the request to get the lyrics url and get the json
    r = requests.get(url, headers=header).json()

    # TODO check that the returned json is of expected form

    # Get the returned results
    results = r['response']['hits']

    return results


def encode_search(name: str, artist: str = None) -> str:
    """
    :arg name: Name of song (Required)
    :arg artist: Artist of song (Optional)
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
    :arg search_term: The name of the song to find the lyrics for (Required)
    :arg artist: Artist of song (Optional)
    :return list: A list containing the lines of the song
    Searches the genius website to get the lyrics of a song
    """
    search_term = encode_search(search_term, artist)

    results = search(search_term)

    # If there are no results return an error
    if len(results) == 0:
        return {"info": [], "Error": "Search term came up with no results, try again"}

    lyrics_url = None

    # TODO improve this for better search accuracy
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
        lines = []
        divs = soup.find_all("div", {"class": "Lyrics__Container-sc-1ynbvzw-6 krDVEH"})
        for div in divs:
            tag_text = []
            for child in div.children:
                tag_text += get_text([child])
            lines += list(filter(lambda x: x != '', tag_text))

        # Insert \n before square brackets
        for i in range(len(lines)):
            if lines[i][0] == "[":
                lines[i] = "\n"+lines[i]

    # Return the results
    return {"info": lines, "Error": 0}


def get_text(children: list) -> list:
    """
    :arg child: A child of the div to find the text of
    :return list: A list of strings
    Gets all text from a child element
    """
    text = []
    for child in children:
        if isinstance(child, bs4.NavigableString):
            text.append(child)
        elif isinstance(child, bs4.Tag):
            text += get_text(child.children)

    return text
