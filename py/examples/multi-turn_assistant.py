import requests
from llmproxy import LLMProxy

if __name__ == '__main__':
    # 1. Create client
    client = LLMProxy()

    # 2. Setup your parameters
    model_name = 'gemini-2.5-flash-lite'
    system_instructions = (
            "You are a university professor who answers queries in a clear, academic style."
            "Respond briefly and kindly, and always include a concise illustrative example."
        )
    temperature_value = 0.5
    last_queries = 3
    session_id_value = 'conversation'
    rag_enabled = False

    # 3. The program runs in a loop, allowing you to enter multiple consequetive queries. 
    #    After typing a query, press Enter to send it to the LLMProxy.
    #    To stop the loop, type "ctrl+x" and press Enter.
    while True:
        query_prompt = input("Enter your query or type EXIT to stop the program: ")
        if query_prompt.strip().lower() == "exit": 
            break
        
        response = client.generate(
            model = model_name,
            system = system_instructions,
            query = query_prompt,
            temperature = temperature_value,
            lastk = last_queries,
            session_id = session_id_value,
            rag_usage = rag_enabled,
        )

        print(response)

