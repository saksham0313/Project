import os
from google import genai

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY is not configured.")

client = genai.Client(api_key=API_KEY)

MODEL = "gemini-2.5-flash"


def ask_gemini(prompt):
    """
    Send a prompt to Gemini and return the answer.
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt
    )

    return response.text


def explain_topic(topic, level="beginner"):
    """
    Generate a simple explanation of a topic.
    """

    prompt = f"""
You are an educational AI assistant.

Explain the following topic for a {level} student.

Topic:
{topic}

Requirements:
1. Use simple language.
2. Give a short definition.
3. Explain the important concepts.
4. Give an example.
5. Mention important points for an exam.
"""

    return ask_gemini(prompt)


def generate_quiz(topic, number_of_questions=5):
    """
    Generate multiple-choice questions.
    """

    prompt = f"""
Create {number_of_questions} multiple-choice questions
about the following topic:

{topic}

Return ONLY valid JSON in this format:

[
  {{
    "question": "Question here",
    "options": [
      "Option A",
      "Option B",
      "Option C",
      "Option D"
    ],
    "answer": "Option A",
    "explanation": "Short explanation"
  }}
]

Do not add markdown or extra text.
"""

    return ask_gemini(prompt)


def summarize_text(text):
    """
    Summarize study material.
    """

    prompt = f"""
Summarize the following study material.

Give:
- Short summary
- Important concepts
- Important definitions
- Exam points

Study material:

{text}
"""

    return ask_gemini(prompt)


def ask_about_document(document_text, question):
    """
    Answer a question using uploaded document content.
    """

    prompt = f"""
You are an AI study assistant.

Use ONLY the document content provided below to answer
the student's question.

DOCUMENT:
{document_text}

QUESTION:
{question}

If the answer cannot be found in the document,
say:

"I could not find the answer in the uploaded document."

Give a clear and simple answer.
"""

    return ask_gemini(prompt)