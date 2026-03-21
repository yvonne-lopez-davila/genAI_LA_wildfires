from llmproxy import LLMProxy

if __name__ == '__main__':

    client = LLMProxy()
    response = client.retrieve(
        query = 'Tell me about green tim?',
        session_id='TestSession',
        rag_threshold = 0.6,
        rag_k = 4
    )

    print(response)