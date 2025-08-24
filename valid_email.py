import requests

def is_email_valid(email):
    url = f"https://emailvalidation.abstractapi.com/v1/?api_key=147c02cdd5a24448a9a90681dd797eb5&email={email}"

    response = requests.get(url)

    # --- Check for quota exceeded or other error ---
    if response.status_code == 422:
        print("⚠️ API quota exceeded. Skipping validation.")
        return None   # or False, depending on your app logic

    if response.status_code != 200:
        print(f"⚠️ API error {response.status_code}: {response.text}")
        return None   # don’t proceed

    # --- Parse only if success ---
    data = response.json()

    deliverability = data.get("deliverability", "UNDELIVERABLE")
    if deliverability == "DELIVERABLE":
        return True
    else:
        return False

if __name__ == "__main__":
    # Example usage
    pass
    #print(is_email_valid("yateeshec0131@gmail.com"))