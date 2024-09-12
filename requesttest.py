import requests

url = "https://api.chess.com/pub/player/geosirey/stats"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0"
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
    print(f"Success! Content: {response.content}")
else:
    print(f"Failed! Status Code: {response.status_code}, Content: {response.content}")
