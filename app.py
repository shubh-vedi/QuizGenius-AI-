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
    news_context: str = Field(default="", description="Contextual news information related to the question.")
    tags: List[str] = Field(default_factory=list, description="Tags related to the question.")
    metadata: dict = Field(default_factory=dict, description="Additional metadata for the question.")

class QuizQuestionList(BaseModel):
    questions: List[QuizQuestion]

# News scraping function
def scrape_news():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    urls = [
        "https://economictimes.indiatimes.com/tech/artificial-intelligence",
        "https://economictimes.indiatimes.com/tech/artificial-intelligence/articlelist/msid-79872984,page-1.cms"
    ]
    
    news_list = []
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, "html.parser")
            articles = soup.find_all("div", class_="story-box")
            
            for article in articles:
                title_elem = article.find("h4")
                desc_elem = article.find("p")
                date_elem = article.find("time") or article.find("span", class_="date-format")
                
                if title_elem and desc_elem:
                    title = title_elem.get_text(strip=True)
                    description = desc_elem.get_text(strip=True)
                    date = date_elem.get_text(strip=True) if date_elem else ""
                    
                    news_list.append({
                        "title": title,
                        "description": description,
                        "date": date
                    })
        except requests.RequestException as e:
            st.error(f"Error fetching {url}: {str(e)}")
        except Exception as e:
            st.error(f"Error processing {url}: {str(e)}")
    
    seen_titles = set()
    unique_news = []
    for news in news_list:
        if news["title"] not in seen_titles:
            seen_titles.add(news["title"])
            unique_news.append(news)
    
    return unique_news[:10]

# Shuffle options
def shuffle_options(mcq_list):
    if not mcq_list:
        return []
        
    shuffled_questions = []
    for mcq in mcq_list:
        mcq_copy = mcq.model_copy()
        if mcq_copy.options:
            random.shuffle(mcq_copy.options)
        shuffled_questions.append(mcq_copy)
    return shuffled_questions

# Push quiz questions to Supabase
def push_to_db(questions: QuizQuestionList, supabase_url: str, supabase_key: str, content_source: str):
    if not all([supabase_url, supabase_key, questions.questions]):
        st.error("Missing required parameters for database push")
        return
        
    try:
        client: Client = create_client(supabase_url, supabase_key)
        shuffled_questions = shuffle_options(questions.questions)
        
        for question in shuffled_questions:
            question_dict = question.dict()
            question_dict["metadata"] = {"source": content_source}
            
            response = client.table("daily_genai_quiz").insert(question_dict).execute()
            if hasattr(response, 'error') and response.error:
                st.error(f"Database error: {response.error}")
    except Exception as e:
        st.error(f"Failed to insert questions: {str(e)}")

# Generate quiz questions
def generate_quiz(content: str, num_questions: int, openai_api_key: str) -> QuizQuestionList:
    if not all([content, num_questions, openai_api_key]):
        st.error("Missing required parameters for quiz generation")
        return QuizQuestionList(questions=[])
        
    try:
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.7,
            api_key=openai_api_key
        )
        
        parser = PydanticOutputParser(pydantic_object=QuizQuestionList)
        format_instructions = parser.get_format_instructions()
        
        prompt = PromptTemplate(
            template="""Generate {num_questions} context-based multiple-choice quiz questions from the following news content:

{content}

Guidelines:

1. Question Structure:
    Each question must include a brief context or background related to the news item.
    Ensure the question text references specific details from the news to make it engaging and informative.

Example 1:
    Title: Nobel laureates urge strong AI regulation
    Description: Physics Nobel Prize winner Geoffrey Hinton and chemistry laureate Demis Hassabis on Saturday insisted on a need for strong regulation of artificial intelligence, which played a key role in their awards. Hinton, who made headlines when he quit Google last year and warned of the dangers machines could one day outsmart people, was awarded his Nobel along with American John Hopfield for work on artificial neural networks.

    Question:
    Nobel laureates Geoffrey Hinton and Demis Hassabis emphasize strong AI regulation. Geoffrey Hinton, who warned about AI surpassing human intelligence, was awarded the Nobel Prize for his work on which AI-related technology?

Example 2:
    Title: Advanced AI chips cleared for export to UAE under Microsoft deal
    Description: The US government has authorised the export of advanced artificial intelligence chips to a Microsoft-operated facility in the United Arab Emirates. This approval is part of Microsoft's closely scrutinized partnership with the Emirati AI company G42.

    Question:
    The US has approved the export of advanced AI chips to a Microsoft-operated facility in the UAE. This deal is part of a collaboration with which Emirati AI company?

Example 3:
    Title: Banks to use AI & machine learning to safeguard customers from financial frauds
    Description: In a significant move to address the growing menace of digital financial frauds, the Department of Financial Services (DFS) has directed banks to adopt advanced technologies, including artificial intelligence (AI) and machine learning (ML), to safeguard customers from fraudsters.

    Question:
    The Department of Financial Services (DFS) recently instructed banks to use AI and machine learning technologies to combat which pressing issue in the financial sector?

--- This is the question forming methodology you need to follow

2. Answer Options:
    Provide four distinct multiple-choice options, including only one correct answer.
    Ensure the incorrect options are plausible but clearly distinguishable from the correct answer.

    Example Options:
    - Advanced robotics
    - Artificial neural networks
    - Quantum computing
    - Machine learning frameworks

3. Correct Answer:
    Clearly identify the correct answer in the response.

4. News Context:
    Include a short "news_context" for each question, summarizing the relevant news item.

5. Variety:
    Focus on unique aspects of the content to ensure a variety of topics and perspectives in the questions.

- Questions should be elaborative, incorporating relevant background or situational details from the news to enhance understanding.
- Responses should be returned in JSON format.

Please ensure the variety and elaboration make the questions engaging and informative.

{format_instructions}""",
            input_variables=["content", "num_questions"],
            partial_variables={"format_instructions": format_instructions}
        )
        
        chain = prompt | llm | parser
        return chain.invoke({"content": content, "num_questions": num_questions})
    except Exception as e:
        st.error(f"Error generating quiz: {str(e)}")
        return QuizQuestionList(questions=[])

# Save questions locally
def save_questions(questions: QuizQuestionList, filename="questions.pkl"):
    try:
        with open(filename, "wb") as f:
            pickle.dump(questions, f)
    except Exception as e:
        st.error(f"Error saving questions: {str(e)}")

# Load questions locally
def load_questions(filename="questions.pkl") -> Union[QuizQuestionList, None]:
    try:
        if os.path.exists(filename):
            with open(filename, "rb") as f:
                return pickle.load(f)
    except Exception as e:
        st.error(f"Error loading questions: {str(e)}")
    return None

# Main App
def main():
    st.title("QuizGenius AI 🤖")
    
    # Load keys from .env file first
    openai_api_key = os.getenv("OPENAI_API_KEY")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([openai_api_key, supabase_url, supabase_key]):
        st.error("Missing configuration. Please ensure .env file contains OPENAI_API_KEY, SUPABASE_URL, and SUPABASE_KEY.")
        return

    choice = st.selectbox("Choose an action:", [
        "Scrape news and generate questions",
        "Use custom text to generate questions",
        "Push questions to the database"
    ])

    num_questions = st.number_input("Number of Questions", min_value=1, max_value=20, value=5)

    if choice == "Scrape news and generate questions":
        if st.button("Scrape and Generate"):
            with st.spinner("Fetching latest AI news..."):
                news_list = scrape_news()
                if news_list:
                    content = "\n\n".join([
                        f"Date: {news.get('date', '')}\nTitle: {news.get('title', '')}\nDescription: {news.get('description', '')}"
                        for news in news_list
                    ])
                    st.info(f"Found {len(news_list)} recent AI news articles")
                    
                    with st.spinner("Generating quiz questions..."):
                        questions = generate_quiz(content, num_questions, openai_api_key)
                        if questions and questions.questions:
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
                with st.spinner("Generating questions..."):
                    questions = generate_quiz(custom_text, num_questions, openai_api_key)
                    if questions and questions.questions:
                        st.success(f"Generated {len(questions.questions)} questions!")
                        print(questions.questions)
                        for q in questions.questions:
                            st.write(q.dict())
                        save_questions(questions)
                    else:
                        st.error("No questions generated!")
            else:
                st.error("Please enter some text to generate questions.")

    elif choice == "Push questions to the database":
        content_source = st.radio(
            "Select content source:",
            ["Scraped News", "Custom Text"],
            horizontal=True
        )
        
        if st.button("Push to Database"):
            questions = load_questions()
            if questions and questions.questions:
                with st.spinner("Pushing questions to database..."):
                    push_to_db(questions, supabase_url, supabase_key, content_source)
                    st.success("Questions pushed successfully!")
            else:
                st.error("No questions available to push. Please generate them first.")

if __name__ == "__main__":
    main()
