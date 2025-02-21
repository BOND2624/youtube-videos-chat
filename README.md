# YouTube Video Chat Assistant

An intelligent chatbot that allows you to have conversations about YouTube video content. The application processes video transcripts and uses advanced AI to provide detailed, contextual answers to your questions.

## Features

- **Smart Video Search**: Search for relevant YouTube videos on any topic
- **Transcript Processing**: Automatically extracts and processes video transcripts
- **AI-Powered Responses**: Uses Groq's Mixtral-8x7b model for detailed, context-aware answers
- **Vector Database**: Stores and retrieves video content efficiently using ChromaDB
- **Web Interface**: Clean, user-friendly Streamlit interface
- **Q&A History**: Keeps track of your conversation history
- **Rate Limiting**: Built-in protection against API overuse
- **Detailed Logging**: Comprehensive logging system for tracking operations

## Demo

Here's a quick demonstration of the YouTube Video Chat Assistant in action:

https://github.com/BOND2624/youtube-videos-chat/raw/main/youtube-video-chat-recording.webm

## Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd youtube-videos-chat
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory and add your API keys:
```env
GROQ_API_KEY=your_groq_api_key
YOUTUBE_API_KEY=your_youtube_api_key
MAX_REQUESTS_PER_MINUTE=60
```

## Usage

1. Start the Streamlit app:
```bash
streamlit run streamlit_app.py
```

2. Enter a topic in the search box and click "Search" to find relevant videos
3. Click "Process" to analyze the video transcripts
4. Ask questions about the processed videos in the question box
5. View your conversation history in the Q&A History section

## System Requirements

- Python 3.8 or higher
- Internet connection for YouTube API and Groq API access
- Sufficient storage space for the vector database

## Architecture

- **Frontend**: Streamlit web interface
- **Backend**: Python with YouTube Data API and Groq API
- **Storage**: ChromaDB for vector storage and retrieval
- **Key Components**:
  - `youtubevideo_chat.py`: Core functionality and API interactions
  - `streamlit_app.py`: Web interface and user interaction
  - `logs/`: Application logs directory
  - `rag_db/`: ChromaDB storage directory

## API Usage

The application uses two main APIs:
1. **YouTube Data API**: For video search and metadata retrieval
2. **Groq API**: For AI-powered question answering

Make sure you have valid API keys and stay within the usage limits.

## Limitations

- Only processes videos with available transcripts
- Maximum context size of 4000 characters per query
- Rate limits: 60 requests per minute
- Currently supports English language content only

## Contributing

Feel free to open issues or submit pull requests for any improvements.

