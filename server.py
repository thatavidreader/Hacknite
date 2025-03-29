from flask import Flask, render_template, jsonify
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Function to scrape welfare programs
def scrape_welfare_programs():
    url = "https://agricoop.nic.in/en/welfare-schemes"  # Change this to the correct government website
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    schemes = []
    for item in soup.select("div.scheme-item"):  # Change selector based on actual website structure
        title = item.find("h3").text.strip() if item.find("h3") else "Unknown Scheme"
        link = item.find("a")["href"] if item.find("a") else "#"
        schemes.append({"title": title, "link": link})

    return schemes

# API to fetch welfare programs
@app.route("/welfare-programs")
def welfare_programs():
    schemes = scrape_welfare_programs()
    return jsonify(schemes)

# Serve index.html
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

