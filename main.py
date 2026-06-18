import requests

def main():

    uid = "100534214"
    url = f"https://api.mihomo.me/sr_info_parsed/{uid}?lang=cn"
    data = requests.get(url, timeout=10).json()

    print(data)

    print(data["player"]["nickname"])
    print(data["player"]["level"])

    for avatar in data.get("characters", []):
        print(avatar["name"], avatar["level"])


if __name__ == "__main__":
    main()
