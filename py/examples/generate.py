from llmproxy import LLMProxy

if __name__ == '__main__':

    client = LLMProxy()

    response = client.generate(
        model = 'gemini-2.5-flash-lite',
        system = 'Answer my question in a funny manner',
        query = 'Who are the Jumbos?',
        temperature=0.5,
        lastk=3,
        session_id='TestSession',
        rag_usage = False,
    )

    print(response)