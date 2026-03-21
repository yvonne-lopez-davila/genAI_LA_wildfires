from llmproxy import LLMProxy


if __name__ == "__main__":
    client = LLMProxy()

    response = client.generate(
        model="gemini-2.5-flash-lite",
        system="You are a concise assistant.",
        query="Who is the current POTUS?",
        websearch=True,
        session_id="TestSession",
    )

    print(response)
