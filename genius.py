# Import libraries
import requests

# Import from libraries
from bs4 import BeautifulSoup

# Auth code for authorization
code = "_1YXXDNRoLkdYrWlMaVZcs4BwfX_srqX2duNPqsdSrVhe-Lea8kKuSSnGMDCQaCM"

# Header to prove identity to website
header = {"Authorization": f"Bearer {code}"}

# Base url of site
base = "http://api.genius.com"


def get_lyrics(search_term: str) -> dict:
    """
    :arg search_term: The name of the song to find the lyrics for
    :return list: A list containing the lines of the song
    Searches the genius website to get the lyrics of a song
    """
    # Convert spaces to %20 for url 
    search_term = search_term.replace(" ", "%20")

    # Create url for request
    url = f"{base}/search?q={search_term}"

    # Create the request to get the lyrics url and get the json
    r = requests.get(url, headers=header).json()

    # Get the returned results
    results = r['response']['hits']

    # If there are no results return an error
    if not len(results) > 0:
        return {"info": [], "Error": "Search term came up with no results, try again"}

    # Get the url from the results
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
        lines = lyrics.text.replace("<br/>", "").split("\n")

    else:
        # Find the lyrics div
        divs = soup.find_all("div", {"class": "Lyrics__Container-sc-1ynbvzw-6 krDVEH"})

        # Stores the lines split by the <br/> tags and
        # removing div tags from front and end
        lines = []
        for i in range(len(divs)//2):
            lines += str(divs[i*2])[51:-6].split("<br/>")

    # Return the results
    return {"info": lines, "Error": 0}
