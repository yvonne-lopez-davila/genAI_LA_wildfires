import requests
from llmproxy import LLMProxy

if __name__ == '__main__':

    # 1. Fetch a webpage
    url = "https://www.eecs.tufts.edu/~abdullah/"
    page = requests.get(url)
    html_text = page.text



    # 2. Create client
    client = LLMProxy()

    # 3. Call LLM with the HTML as the query
    response = client.generate(
        model='gemini-2.5-flash-lite',
        system=(
            "You will receive the raw HTML of a webpage. "
            "Extract the key findings, important topics, and any key dates. "
            "Respond briefly and clearly."
        ),
        query=html_text,
        temperature=0.5,
        lastk=3,
        session_id='WebSummarySession',
        rag_usage=False,
    )

    print(response)
