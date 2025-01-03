import streamlit as st
import os
import random
from typing import List, Union
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
import pickle

# Define the models for Quiz
class Option(BaseModel):
    text: str = Field(description="The text of the option.")
    correct: str = Field(description="Whether the option is correct or not. Either 'true' or 'false'")

class QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question about recent AI developments.")
    options: List[Option] = Field(description="The possible answers to the question. The list should contain 4 options.")
    news_context: str = Field(default=None, description="Contextual news information related to the question.")
    tags: List[str] = Field(default_factory=list, description="Tags related to the question.")
    metadata: dict = Field(default={}, description="Additional metadata for the question.")

class QuizQuestionList(BaseModel):
    questions: List[QuizQuestion]

# Load environment variables
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
SUPABASE_URL = os.getenv('SUPABASE_BFWAI_URL')
SUPABASE_KEY = os.getenv('SUPABASE_BFWAI_KEY')

# News scraping function
def scrape_news():
    url = "https://economictimes.indiatimes.com/tech/artificial-intelligence"
    response = requests.get(url)
    if response.status_code == 200:
        soup = BeautifulSoup(response.content, "html.parser")
        articles = soup.find_all("div", class_="story-box")
        news_list = []
        for article in articles:
            title = article.find("h4").get_text(strip=True) if article.find("h4") else "No title"
            description = article.find("p").get_text(strip=True) if article.find("p") else "No description"
            news_list.append({"title": title, "description": description})
        return news_list
    else:
        st.error(f"Failed to fetch news. Status code: {response.status_code}")
        return []

# Shuffle options
def shuffle_options(mcq_list):
    shuffled_questions = []
    for mcq in mcq_list:
        mcq_copy = mcq.model_copy()
        random.shuffle(mcq_copy.options)
        shuffled_questions.append(mcq_copy)
    return shuffled_questions

# Insert quiz questions into Supabase
def push_to_db(questions: QuizQuestionList, content_source):
    if not all([SUPABASE_URL, SUPABASE_KEY]):
        st.error("Supabase credentials not found in environment variables!")
        return
    
    client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    shuffled_questions = shuffle_options(questions.questions)
    for question in shuffled_questions:
        question.metadata = {"source": content_source}
        try:
            client.table("daily_genai_quiz").insert(question.dict()).execute()
            st.success(f"Successfully inserted question: {question.question[:50]}...")
        except Exception as e:
            st.error(f"Failed to insert question: {e}")

# Generate quiz questions
def generate_quiz(content: str, num_questions: int) -> QuizQuestionList:
    if not OPENAI_API_KEY:
        st.error("OpenAI API key not found in environment variables!")
        return QuizQuestionList(questions=[])
    
    try:
        llm = ChatOpenAI(model="gpt-4", temperature=0.7, openai_api_key=OPENAI_API_KEY)
        prompt = PromptTemplate(
            template=
            """"Generate {num_questions} context-based multiple-choice quiz questions from the following news content:\n\n{content}\n\n"

            Guidelines:

            1. Question Structure:
                Each question must include a brief context or background related to the news item.
                Ensure the question text references specific details from the news to make it engaging and informative.

            2. Answer Options:
                Provide four distinct multiple-choice options, including only one correct answer.
                Ensure the incorrect options are plausible but clearly distinguishable from the correct answer.

            3. Correct Answer:
                Clearly identify the correct answer in the response.

            4. News Context:
                Include a short "news_context" for each question, summarizing the relevant news item.

            5. Variety:
                Focus on unique aspects of the content to ensure a variety of topics and perspectives in the questions.

            Please ensure the variety and elaboration make the questions engaging and informative."
            {format_instructions}""",
            input_variables=["content", "num_questions"],
            partial_variables={
                "format_instructions": PydanticOutputParser(pydantic_object=QuizQuestionList).get_format_instructions()
            }
        )
        chain = prompt | llm | PydanticOutputParser(pydantic_object=QuizQuestionList)
        return chain.invoke({"content": content, "num_questions": num_questions})
    except Exception as e:
        st.error(f"Error generating quiz: {e}")
        return QuizQuestionList(questions=[])

# Save questions locally
def save_questions(questions: QuizQuestionList, filename="questions.pkl"):
    with open(filename, "wb") as f:
        pickle.dump(questions, f)
    st.success("Questions saved successfully!")

# Load questions locally
def load_questions(filename="questions.pkl") -> Union[QuizQuestionList, None]:
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            return pickle.load(f)
    return None

# Streamlit app
def main():
    st.title("AI News Quiz Generator")
    st.write("Generate quiz questions from AI news articles or custom text")

    # Main content
    num_questions = st.number_input("Number of questions to generate", min_value=1, max_value=10, value=3)
    
    tab1, tab2, tab3 = st.tabs(["Generate Questions", "View Questions", "Push to Database"])

    # Generate Questions Tab
    with tab1:
        st.header("Generate Questions")
        source_option = st.radio("Choose source:", ["Scrape News", "Custom Text"])

        if source_option == "Scrape News":
            if st.button("Scrape AI News"):
                with st.spinner("Scraping news articles..."):
                    news_list = scrape_news()
                    if news_list:
                        st.success(f"Scraped {len(news_list)} articles.")
                        content = "\n\n".join([f"Title: {news['title']}\nDescription: {news['description']}" for news in news_list])
                        st.text_area("Scraped Content", content, height=200)
                        
                        if st.button("Generate Quiz"):
                            with st.spinner("Generating questions..."):
                                questions = generate_quiz(content, num_questions)
                                if questions.questions:
                                    save_questions(questions)
                                    st.success(f"Generated {len(questions.questions)} questions!")
        else:
            custom_text = st.text_area("Enter your custom text:", height=200)
            if st.button("Generate Quiz"):
                with st.spinner("Generating questions..."):
                    questions = generate_quiz(custom_text, num_questions)
                    if questions.questions:
                        save_questions(questions)
                        st.success(f"Generated {len(questions.questions)} questions!")

    # View Questions Tab
    with tab2:
        st.header("View Generated Questions")
        questions = load_questions()
        if questions and questions.questions:
            for i, q in enumerate(questions.questions, 1):
                st.subheader(f"Question {i}")
                st.write(q.question)
                st.write("Options:")
                for opt in q.options:
                    is_correct = "✅" if opt.correct.lower() == "true" else ""
                    st.write(f"- {opt.text} {is_correct}")
                if q.news_context:
                    st.write("Context:", q.news_context)
                st.divider()
        else:
            st.info("No questions available. Generate some questions first!")

    # Push to Database Tab
    with tab3:
        st.header("Push Questions to Database")
        content_source = st.text_input("Content Source", placeholder="e.g., Scraped News, Custom Text")
        
        if st.button("Push to Database"):
            questions = load_questions()
            if questions and questions.questions:
                with st.spinner("Pushing questions to database..."):
                    push_to_db(questions, content_source)
            else:
                st.error("No questions available to push. Please generate them first!")

if __name__ == "__main__":
    main()
