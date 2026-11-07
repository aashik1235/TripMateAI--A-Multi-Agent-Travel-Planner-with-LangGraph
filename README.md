# TripMate-AI-A-Agent_Travel_planner-with_LangGraph

# How to run ?
# 1. Create virtual environment
python -m venv venv

# 2. Activate virtual environment (Windows)
venv\Scripts\activate

# 3. Install requirements
pip install -r requirements.txt

# 4. Run the project
python main.py


postgresql://aashik:0OccRfVnApzbL39eqEAF0JkGVdf3Bfgd@dpg-dbk10cmc6qcc73d74vb0-a.virginia-postgres.render.com/agentmemory_e0h8



✈️ TripMate AI
Your AI Travel Planning Assistant

TripMate AI is an AI-powered travel planner that helps users plan trips, explore destinations, find hotels, research attractions, and search for flight information through a simple chat interface.
Features
- Plan trips using AI.
- Get destination suggestions.
- Find hotels and tourist attractions.
- Search flight schedule information.
- Ask travel-related questions.
- Continue previous conversations.
Technologies Used
- Python
- Streamlit
- FastAPI
- LangGraph
- Groq
- Tavily
- AviationStack
- PostgreSQL
- Docker
Project Structure
TripMateAI/
│
├── tools/
│   ├── __init__.py
│   ├── flight_tool.py
│   └── tavily_tool.py
│
├── app.py
├── backend.py
├── streamlit_app.py
├── test.py
│
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── .gitignore
├── .env
└── README.md


Installation
1. Clone the project
git clone YOUR_GITHUB_REPOSITORY_URL
cd YOUR_PROJECT_FOLDER


2. Create a virtual environment
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1


3. Install dependencies
pip install -r requirements.txt


4. Create a .env file
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=your_postgresql_url
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
LANGSMITH_API_KEY=your_langsmith_api_key


Keep your API keys private. Never upload your .env file to GitHub.
Run the Application
Open two terminals.

Terminal 1 – FastAPI Backend
uvicorn app:app --reload


API documentation: http://127.0.0.1:8000/docs

Terminal 2 – Streamlit Frontend
streamlit run streamlit_app.py


Open http://localhost:8501 in your browser.
Run with Docker
Build the image:
docker build -t tripmate-backend .


Run the container:
docker run --name tripmate-backend -p 8000:8000 --env-file .env tripmate-backend


Note: Docker currently runs the FastAPI backend only. Run Streamlit separately.
API Endpoints
Method	Endpoint	Description
GET	/	API status
GET	/health	Backend health
POST	/chat	Chat with AI

Important Notes
- PostgreSQL must be configured before starting the backend.
- Flight information is schedule information, not confirmed ticket availability.
- Hotel search does not guarantee room availability.
- Keep all API keys secure.
Future Improvements
- Deploy the application online.
- Add Docker Compose.
- Improve the user interface.
- Add more travel services.