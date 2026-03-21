from llmproxy import LLMProxy

if __name__ == "__main__":
    client = LLMProxy()

    image = client.upload_media(
        file_path="test_image.jpg",
        session_id="TestSession",
        content_type="image/jpeg",
    )
    audio = client.upload_media(
        file_path="voice_note.mp3",
        session_id="TestSession",
        content_type="audio/mpeg",
    )

    response = client.generate(
        model="gemini-2.5-flash-lite",
        system="You are a concise assistant.",
        query="Describe the provided media briefly and transcribe the audio",
        session_id="TestSession",
        media=[
            {"id": image["id"], "type": image["type"]},
            {"id": audio["id"], "type": audio["type"]},
        ],
    )

    print(response)
