from llmproxy import LLMProxy


if __name__ == '__main__':
    client = LLMProxy()

    response = client.upload_file(
        file_path='greentim.pdf',
        session_id='TestSession',
        strategy='smart',
    )

    print(response)
