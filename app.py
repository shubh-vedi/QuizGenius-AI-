import os
import random
import pickle
import requests
from bs4 import BeautifulSoup
from typing import List, Union
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from supabase import create_client, Client
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define Models
class Option(BaseModel):
    text: str = Field(description="The text of the option.")
    correct: bool = Field(description="Whether the option is correct or not (true/false).")

class QuizQuestion(BaseModel):
    question: str = Field(description="The quiz question about recent AI developments.")
    options: List[Option] = Field(description="The possible answers to the question. The list should contain 4 options.")
    news_context: str = Field(default=None, description="Contextual news information related to the question.")
    tags: List[str] = Field(default_factory=list, description="Tags related to the question.")
    metadata: dict = Field(default={}, description="Additional metadata for the question.")

class QuizQuestionList(BaseModel):
    questions: List[QuizQuestion]

# News scraping function
def scrape_news():
    # Add headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    # You might want to try multiple news sources to ensure fresh content
    urls = [
        "https://economictimes.indiatimes.com/tech/artificial-intelligence",
        "https://economictimes.indiatimes.com/tech/artificial-intelligence/articlelist/msid-79872984,page-1.cms"  # Latest articles page
    ]
    
    news_list = []
    for url in urls:
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                articles = soup.find_all("div", class_="story-box")
                
                for article in articles:
                    title = article.find("h4").get_text(strip=True) if article.find("h4") else "No title"
                    description = article.find("p").get_text(strip=True) if article.find("p") else "No description"
                    date_elem = article.find("time") or article.find("span", class_="date-format")
                    date = date_elem.get_text(strip=True) if date_elem else None
                    
                    # Only add articles if they have content
                    if title != "No title" and description != "No description":
                        news_list.append({
                            "title": title,
                            "description": description,
                            "date": date
                        })
            else:
                st.error(f"Failed to fetch news from {url}. Status code: {response.status_code}")
        except Exception as e:
            st.error(f"Error scraping {url}: {e}")
    
    # Sort by date if available and remove duplicates
    seen_titles = set()
    unique_news = []
    for news in news_list:
        if news["title"] not in seen_titles:
            seen_titles.add(news["title"])
            unique_news.append(news)
    
    return unique_news[:10]  # Return top 10 unique articles

# Shuffle options
def shuffle_options(mcq_list):
    shuffled_questions = []
    for mcq in mcq_list:
        mcq_copy = mcq.model_copy()
        random.shuffle(mcq_copy.options)
        shuffled_questions.append(mcq_copy)
    return shuffled_questions

# Push quiz questions to Supabase
def push_to_db(questions: QuizQuestionList, supabase_url, supabase_key, content_source):
    client: Client = create_client(supabase_url, supabase_key)
    shuffled_questions = shuffle_options(questions.questions)
    for question in shuffled_questions:
        question.metadata = {"source": content_source}
        try:
            client.table("daily_genai_quiz").insert(question.dict()).execute()
        except Exception as e:
            st.error(f"Failed to insert question: {e}")

# Generate quiz questions
def generate_quiz(content: str, num_questions: int, openai_api_key: str) -> QuizQuestionList:
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
        prompt = PromptTemplate(
            template=("""
                Generate {num_questions} context-based multiple-choice quiz questions from the following news content:
                {content}

                Guidelines:
                1. Questions must reference details from the news to make them engaging.
                2. Provide four distinct answer options (one correct).
                3. Include a "news_context" summarizing the news item.
                4. Ensure variety and relevance in the questions.
                
                Format the output as a JSON object with a 'questions' array containing objects with:
                - question (string)
                - options (array of objects with 'text' and 'correct' fields, where 'correct' is a boolean true/false)
                - news_context (string)
                - tags (array of strings)
                - metadata (object)
            """),
            input_variables=["content", "num_questions"]
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

# Load questions locally
def load_questions(filename="questions.pkl") -> Union[QuizQuestionList, None]:
    if os.path.exists(filename):
        with open(filename, "rb") as f:
            return pickle.load(f)
    return None

# Main App
def main():
    st.title("QuizGenius AI 🤖")

    choice = st.selectbox("Choose an action:", [
        "Scrape news and generate questions",
        "Use custom text to generate questions",
        "Push questions to the database"
    ])

    num_questions = st.number_input("Number of Questions", min_value=1, value=5)

    # Load keys from .env file
    openai_api_key = os.getenv("OPENAI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([openai_api_key, supabase_url, supabase_key]):
        st.error("Missing configuration. Please ensure .env file contains all required keys.")
        return

    if choice == "Scrape news and generate questions":
        if st.button("Scrape and Generate"):
            with st.spinner("Fetching latest AI news..."):
                news_list = scrape_news()
                if news_list:
                    content = "\n\n".join([
                        f"Date: {news['date']}\nTitle: {news['title']}\nDescription: {news['description']}"
                        for news in news_list
                    ])
                    st.info(f"Found {len(news_list)} recent AI news articles")
                    
                    with st.spinner("Generating quiz questions..."):
                        questions = generate_quiz(content, num_questions, openai_api_key)
                        if questions.questions:
                            st.success(f"Generated {len(questions.questions)} questions!")
                            for q in questions.questions:
                                st.write(q.dict())
                            save_questions(questions)
                        else:
                            st.error("No questions generated!")
                else:
                    st.error("No news articles found!")

    elif choice == "Use custom text to generate questions":
        custom_text = st.text_area("Enter custom text:")
        if st.button("Generate from Custom Text"):
            if custom_text.strip():
                questions = generate_quiz(custom_text, num_questions, openai_api_key)
                if questions.questions:
                    st.success(f"Generated {len(questions.questions)} questions!")
                    for q in questions.questions:
                        st.write(q.dict())
                    save_questions(questions)
                else:
                    st.error("No questions generated!")

    elif choice == "Push questions to the database":
        content_source = st.radio(
            "Select content source:",
            ["Scraped News", "Custom Text"],
            horizontal=True
        )
        
        if st.button("Push to Database"):
            questions = load_questions()
            if questions and questions.questions:
                push_to_db(questions, supabase_url, supabase_key, content_source)
                st.success("Questions pushed successfully!")
            else:
                st.error("No questions available to push. Please generate them first.")

# Run the app
if __name__ == "__main__":
    main()