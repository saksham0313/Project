import os
import json
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv
from google import genai
from pypdf import PdfReader

# ============================================================
# BHAVYA AI STUDY ASSISTANT
# Google Gemini + Flask
# ============================================================

load_dotenv()

app = Flask(__name__)

# ------------------------------------------------------------
# GEMINI CONFIGURATION
# ------------------------------------------------------------

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY is missing. "
        "Create a .env file and add your Gemini API key."
    )

client = genai.Client(api_key=API_KEY)

MODEL = "gemini-2.5-flash"


# ============================================================
# GEMINI FUNCTION
# ============================================================

def ask_gemini(prompt):

    try:

        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )

        return response.text

    except Exception as e:

        return f"Gemini Error: {str(e)}"


# ============================================================
# AI FEATURES
# ============================================================

def explain_topic(topic):

    prompt = f"""
You are Bhavya AI, an educational assistant.

Explain the following topic to a college student:

TOPIC:
{topic}

Give the answer using this structure:

1. Simple Definition
2. Explanation
3. Important Concepts
4. Example
5. Advantages / Uses
6. Important Exam Points

Use simple language.
"""

    return ask_gemini(prompt)


def generate_quiz(topic):

    prompt = f"""
You are an educational quiz generator.

Create 5 multiple-choice questions about:

{topic}

For every question give:

Question:
A)
B)
C)
D)

Correct Answer:
Explanation:

Make the questions suitable for college students.
"""

    return ask_gemini(prompt)


def summarize_text(text):

    prompt = f"""
You are a study assistant.

Summarize the following study material.

Give:

1. Short Summary
2. Important Concepts
3. Important Definitions
4. Key Points
5. Exam Preparation Points

STUDY MATERIAL:

{text}
"""

    return ask_gemini(prompt)


def ask_about_pdf(text, question):

    prompt = f"""
You are an educational AI assistant.

Answer the student's question using the uploaded
study material.

STUDY MATERIAL:
{text}

STUDENT QUESTION:
{question}

Rules:

1. Prefer information from the study material.
2. Explain in simple language.
3. If the answer is not present in the document,
   clearly say that it was not found.
"""

    return ask_gemini(prompt)


# ============================================================
# HOME PAGE
# ============================================================

HTML = """

<!DOCTYPE html>

<html>

<head>

<title>Bhavya AI Study Assistant</title>

<meta name="viewport"
content="width=device-width, initial-scale=1">

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    font-family:
    Arial,
    Helvetica,
    sans-serif;

    background:
    linear-gradient(
        135deg,
        #667eea,
        #764ba2
    );

    min-height: 100vh;

    padding: 30px;
}


.container {

    max-width: 900px;

    margin: auto;

    background: white;

    border-radius: 20px;

    padding: 30px;

    box-shadow:
    0 15px 40px
    rgba(0,0,0,0.25);

}


h1 {

    text-align: center;

    color: #4f46e5;

    margin-bottom: 5px;

}


.subtitle {

    text-align: center;

    color: #666;

    margin-bottom: 30px;

}


textarea {

    width: 100%;

    min-height: 130px;

    padding: 15px;

    border: 2px solid #ddd;

    border-radius: 10px;

    resize: vertical;

    font-size: 16px;

}


.buttons {

    display: flex;

    flex-wrap: wrap;

    gap: 10px;

    margin-top: 15px;

}


button {

    border: none;

    padding: 12px 18px;

    border-radius: 8px;

    color: white;

    background: #4f46e5;

    cursor: pointer;

    font-size: 15px;

}


button:hover {

    background: #3730a3;

}


.pdf-section {

    margin-top: 30px;

    padding: 20px;

    background: #f5f7ff;

    border-radius: 12px;

}


input[type=file] {

    margin: 10px 0;

}


#answer {

    margin-top: 25px;

    padding: 20px;

    background: #f8fafc;

    border-radius: 12px;

    border-left: 5px solid #4f46e5;

    white-space: pre-wrap;

    line-height: 1.6;

    min-height: 100px;

}


.loading {

    color: #4f46e5;

    font-weight: bold;

}


.footer {

    text-align: center;

    margin-top: 25px;

    color: #777;

    font-size: 13px;

}

</style>

</head>


<body>


<div class="container">


<h1>🤖 Bhavya AI</h1>

<div class="subtitle">

Google Gemini Powered Study Assistant

</div>


<textarea
id="message"
placeholder="Enter your question or topic here...">
</textarea>


<div class="buttons">

<button onclick="chat()">
💬 Ask AI
</button>

<button onclick="explain()">
📚 Explain Topic
</button>

<button onclick="quiz()">
📝 Generate Quiz
</button>

<button onclick="summarize()">
📋 Summarize
</button>

</div>


<div class="pdf-section">

<h3>📄 Ask Questions From PDF</h3>

<input
type="file"
id="pdf"
accept=".pdf">

<br>

<textarea
id="pdfQuestion"
placeholder="Example: What is inheritance?">
</textarea>

<button onclick="askPDF()">
🔍 Ask From PDF
</button>

</div>


<div id="answer">

AI response will appear here...

</div>


<div class="footer">

Bhavya AI • Google Gemini

</div>


</div>


<script>


function loading() {

    document.getElementById("answer")
    .innerHTML =
    "<div class='loading'>🤖 Gemini is thinking...</div>";

}


async function chat() {

    const message =
    document.getElementById("message").value;

    if (!message.trim()) {

        alert("Please enter a question.");

        return;

    }

    loading();


    const response =
    await fetch("/chat", {

        method: "POST",

        headers: {
            "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
            message: message
        })

    });


    const data =
    await response.json();


    document.getElementById("answer")
    .innerText =
    data.answer || data.error;

}


async function explain() {

    const topic =
    document.getElementById("message").value;


    if (!topic.trim()) {

        alert("Please enter a topic.");

        return;

    }


    loading();


    const response =
    await fetch("/explain", {

        method: "POST",

        headers: {
            "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
            topic: topic
        })

    });


    const data =
    await response.json();


    document.getElementById("answer")
    .innerText =
    data.result || data.error;

}


async function quiz() {

    const topic =
    document.getElementById("message").value;


    if (!topic.trim()) {

        alert("Please enter a topic.");

        return;

    }


    loading();


    const response =
    await fetch("/quiz", {

        method: "POST",

        headers: {
            "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
            topic: topic
        })

    });


    const data =
    await response.json();


    document.getElementById("answer")
    .innerText =
    data.quiz || data.error;

}


async function summarize() {

    const text =
    document.getElementById("message").value;


    if (!text.trim()) {

        alert("Please enter study material.");

        return;

    }


    loading();


    const response =
    await fetch("/summarize", {

        method: "POST",

        headers: {
            "Content-Type":
            "application/json"
        },

        body: JSON.stringify({
            text: text
        })

    });


    const data =
    await response.json();


    document.getElementById("answer")
    .innerText =
    data.summary || data.error;

}


async function askPDF() {

    const file =
    document.getElementById("pdf").files[0];

    const question =
    document.getElementById("pdfQuestion").value;


    if (!file) {

        alert("Please select a PDF.");

        return;

    }


    if (!question.trim()) {

        alert("Please enter a question.");

        return;

    }


    loading();


    const formData =
    new FormData();

    formData.append(
        "pdf",
        file
    );

    formData.append(
        "question",
        question
    );


    const response =
    await fetch("/ask-pdf", {

        method: "POST",

        body: formData

    });


    const data =
    await response.json();


    document.getElementById("answer")
    .innerText =
    data.answer || data.error;

}


</script>


</body>

</html>

"""


# ============================================================
# ROUTES
# ============================================================

@app.route("/")
def home():

    return render_template_string(HTML)


# ------------------------------------------------------------
# CHAT
# ------------------------------------------------------------

@app.route("/chat", methods=["POST"])
def chat():

    try:

        data = request.get_json()

        message = data.get("message")

        if not message:

            return jsonify({
                "error":
                "Message is required."
            }), 400


        answer = ask_gemini(message)


        return jsonify({

            "success": True,

            "answer": answer

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ------------------------------------------------------------
# EXPLAIN
# ------------------------------------------------------------

@app.route("/explain", methods=["POST"])
def explain():

    try:

        data = request.get_json()

        topic = data.get("topic")

        if not topic:

            return jsonify({
                "error":
                "Topic is required."
            }), 400


        result =
        explain_topic(topic)


        return jsonify({

            "success": True,

            "result": result

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ------------------------------------------------------------
# QUIZ
# ------------------------------------------------------------

@app.route("/quiz", methods=["POST"])
def quiz():

    try:

        data = request.get_json()

        topic = data.get("topic")

        if not topic:

            return jsonify({
                "error":
                "Topic is required."
            }), 400


        result =
        generate_quiz(topic)


        return jsonify({

            "success": True,

            "quiz": result

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

@app.route("/summarize", methods=["POST"])
def summarize():

    try:

        data = request.get_json()

        text = data.get("text")

        if not text:

            return jsonify({
                "error":
                "Study material is required."
            }), 400


        result =
        summarize_text(text)


        return jsonify({

            "success": True,

            "summary": result

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ------------------------------------------------------------
# PDF QUESTION
# ------------------------------------------------------------

@app.route("/ask-pdf", methods=["POST"])
def ask_pdf():

    try:

        pdf = request.files.get("pdf")

        question =
        request.form.get("question")


        if not pdf:

            return jsonify({
                "error":
                "PDF file is required."
            }), 400


        if not question:

            return jsonify({
                "error":
                "Question is required."
            }), 400


        if not pdf.filename.lower().endswith(".pdf"):

            return jsonify({
                "error":
                "Only PDF files are supported."
            }), 400


        reader =
        PdfReader(pdf)


        text = ""


        for page in reader.pages:

            page_text =
            page.extract_text()


            if page_text:

                text += (
                    page_text +
                    "\n"
                )


        if not text.strip():

            return jsonify({
                "error":
                "Could not extract text from PDF."
            }), 400


        answer =
        ask_about_pdf(
            text,
            question
        )


        return jsonify({

            "success": True,

            "answer": answer

        })


    except Exception as e:

        return jsonify({

            "success": False,

            "error": str(e)

        }), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    print("")
    print("====================================")
    print("       BHAVYA AI STUDY ASSISTANT")
    print("====================================")
    print("")
    print("Open in browser:")
    print("http://127.0.0.1:5000")
    print("")

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )