# QuizGenius AI 🤖

QuizGenius AI is an intelligent quiz generation system that automatically creates high-quality multiple-choice questions from AI-related news or custom content. Built with GPT-4o and Streamlit, it helps create engaging quizzes while staying current with AI developments.

## 🌟 Features

- **Real-time News Scraping**: Automatically fetches the latest AI news from Google News RSS feeds
- **Custom Content Support**: Generate questions from any custom text input
- **Smart Question Generation**: Uses GPT-4 to create contextually relevant questions
- **Database Integration**: Seamlessly stores questions in Supabase for future use
- **User-friendly Interface**: Clean, intuitive Streamlit interface
- **Flexible Configuration**: Adjustable number of questions and content sources

## 🚀 Quick Start

1. **Clone the repository**
bash
git clone https://github.com/yourusername/quizgenius-ai.git

cd quizgenius-ai

2. **Install dependencies**
bash
pip install -r requirements.txt


3. **Environment Setup**
Create a `.env` file in the root directory:
env
OPENAI_API_KEY=your_openai_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key


4. **Run the application**
   
   streamlit run app.py


## 📋 Requirements

- Python 3.8+
- Dependencies:
  ```
  streamlit
  langchain
  openai
  supabase-py
  beautifulsoup4
  feedparser
  python-dotenv
  pydantic
  ```

## 💡 Usage

1. **Select Action**:
   - Scrape news and generate questions
   - Use custom text to generate questions
   - Push questions to the database

2. **Configure**:
   - Set number of questions
   - Choose content source (Scraped News/Custom Text)

3. **Generate & Store**:
   - Click generate to create questions
   - Review generated questions
   - Push to database for storage

## 🏗️ Architecture

- Frontend: Streamlit
- Language Model: GPT-4 via OpenAI API
- Database: Supabase
- News Source: Google News RSS Feeds

## 📝 License

MIT License

## 👥 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 🔗 Contact

- GitHub: shubh-vedi
- Email: shubhamnv2@gmail.com

## 🙏 Acknowledgments

- OpenAI for GPT-4o API
- Streamlit team for the amazing framework
- Supabase for database solutions

---
Made with ❤️ by shubham vedi
