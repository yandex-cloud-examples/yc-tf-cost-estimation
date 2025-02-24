import argparse
import requests
import json

# Initial URL
API_URL     = "https://billing.api.cloud.yandex.net/billing/v1/skus"

# Output file
OUTPUT_FILE = "sku.json"

# Initialize the aggregated data structure
all_skus = []

# Function to perform a request and process the response
def perform_request(url, headers, params=None):
    response = requests.get(url, headers=headers, params=params)
    data = response.json()
    return data

# First request

def main():
    parser = argparse.ArgumentParser(description="Yandex Cloud IAM token")
    parser.add_argument("token", help="IAM token")
    args = parser.parse_args()

    token = args.token

    headers = {
        "Authorization": f"Bearer {token}"
    }

    data = perform_request(API_URL, headers)
    all_skus.extend(data.get("skus", []))
    next_page_token = data.get("nextPageToken")

    # Loop through pages
    while next_page_token:
        params = {"pageToken": next_page_token}
        data = perform_request(API_URL, headers, params)
        all_skus.extend(data.get("skus", []))
        next_page_token = data.get("nextPageToken")

    # Save the aggregated results to the output file
    with open(OUTPUT_FILE, "w") as f:
        json.dump({"skus": all_skus}, f, indent=4)

    print(f"All pages have been fetched and saved to {OUTPUT_FILE}.")

if __name__ == "__main__":
    main()