from pydantic import BaseModel, ConfigDict

from llmproxy import LLMProxy


# Pydantic class to define the desired structure
# Avoid nested classes, stick to flat hierarchy
class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

    # needs to be present otherwise generate will fail
    model_config = ConfigDict(extra="forbid")


if __name__ == '__main__':
    client = LLMProxy()

    response = client.generate(
        model='gemini-2.5-flash-lite',
        system='Extract event details',
        query='Bob and Alice are going to a science fair on Friday.',
        output_schema=CalendarEvent,
        temperature=0.5,
        lastk=3,
        session_id='TestSession',
        rag_usage=False,
    )

    print(response)
