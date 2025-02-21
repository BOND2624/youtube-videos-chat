import os
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from langchain_groq import ChatGroq
import chromadb
from typing import List, Dict
import json
import time
from dotenv import load_dotenv
import logging
import agentops

# Must precede any llm module imports

from langtrace_python_sdk import langtrace

langtrace.init(api_key = 'cf37198dd30d4d65e149e4581ecc9e19749d94142026236d65460d794bfb90b0')

agentops.init(
    api_key='40691a47-907e-4ab3-9099-13d4c4c3683f',
    default_tags=['crewai']
)

# Load environment variables
load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

if not GROQ_API_KEY or not YOUTUBE_API_KEY:
    raise ValueError("Missing required API keys. Please check your .env file.")

# Initialize YouTube API
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

# Initialize ChromaDB
client = chromadb.PersistentClient(path="./rag_db")
collection = client.get_or_create_collection(name="youtube_content")

# Initialize LLM
llm = ChatGroq(
    model_name="mixtral-8x7b-32768",  
    temperature=0.7,
    groq_api_key=GROQ_API_KEY,
    max_retries=3  
)

def validate_input(text: str, max_length: int = 500) -> str:
    """Validate and sanitize input text"""
    if not text or not isinstance(text, str):
        raise ValueError("Input must be a non-empty string")
    
    # Remove any potential harmful characters
    text = ''.join(char for char in text if char.isprintable())
    
    # Limit length
    return text[:max_length].strip()

def search_youtube_videos(query: str, max_results: int = 20) -> List[Dict]:
    """Search for YouTube videos and return their details"""
    try:
        # Validate input
        query = validate_input(query)
        max_results = min(max(1, max_results), 20)  # Limit between 1 and 10
        
        request = youtube.search().list(
            q=query,
            part='snippet',
            maxResults=max_results,
            type='video'
        )
        response = request.execute()
        
        videos = []
        for item in response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            channel = item['snippet']['channelTitle']
            videos.append({
                'id': video_id,
                'title': title,
                'channel': channel
            })
        return videos
    except Exception as e:
        print(f"Error searching YouTube: {str(e)}")
        return []

def get_video_transcript(video_id: str) -> str:
    """Get transcript for a YouTube video"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return ' '.join([t['text'] for t in transcript])
    except Exception as e:
        print(f"Error getting transcript for video {video_id}: {str(e)}")
        return ""

def chunk_text(text: str, max_chars: int = 1000) -> str:
    """Chunk text to a maximum length while preserving sentence boundaries"""
    if len(text) <= max_chars:
        return text
    
    # Find the last sentence boundary before max_chars
    sentences = text[:max_chars].split('.')
    if len(sentences) > 1:
        return '.'.join(sentences[:-1]) + '.'
    return text[:max_chars] + '...'

def process_content(topic: str):
    """Process content for a given topic"""
    try:
        print(f"\nSearching for videos about '{topic}'...")
        videos = search_youtube_videos(topic)
        
        if not videos:
            print("No videos found.")
            return
        
        print("\nFound videos:")
        print("-" * 80)
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']}")
            print(f"   Channel: {video['channel']}")
            print()
        
        print("\nProcessing videos...")
        print("-" * 80)
        
        # Track processed videos for logging
        processed_videos = []
        
        for video in videos:
            print(f"\nProcessing: {video['title']}")
            transcript = get_video_transcript(video['id'])
            
            if transcript:
                try:
                    # Store in ChromaDB with metadata
                    collection.add(
                        documents=[transcript],
                        metadatas=[{
                            'title': video['title'],
                            'channel': video['channel'],
                            'video_id': video['id']
                        }],
                        ids=[video['id']]
                    )
                    processed_videos.append({
                        'title': video['title'],
                        'channel': video['channel'],
                        'video_id': video['id']
                    })
                    print("✓ Successfully processed")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        print("✓ Video already in database")
                    else:
                        raise
            else:
                print("✗ No transcript available")
        
        # Log processed videos in a structured way
        if processed_videos:
            logging.info(f"Processed {len(processed_videos)} videos for topic '{topic}'")
            logging.debug(f"Processed video details: {json.dumps(processed_videos, indent=2)}")
        
        print("\nContent processing complete!")
        print("-" * 80)
        
    except Exception as e:
        print(f"\nError during processing: {str(e)}")

def query_content(question: str) -> str:
    """Query the stored content"""
    try:
        results = collection.query(
            query_texts=[question],
            n_results=3
        )
        
        if not results['documents'][0]:
            return "No relevant information found. Try processing some videos first."
        
        # Prepare context from results with more structure
        contexts = []
        total_chars = 0
        MAX_TOTAL_CHARS = 4000  # Limit total context size
        
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            # Skip if we've exceeded the total context size
            if total_chars >= MAX_TOTAL_CHARS:
                break
                
            # Chunk the document text
            chunked_doc = chunk_text(doc, max_chars=1000)
            total_chars += len(chunked_doc)
            
            # Format context with more structure
            context = f"""
Source: '{meta['title']}' by {meta['channel']}
URL: https://youtube.com/watch?v={meta['video_id']}
Key Points:
{chunked_doc}
---"""
            contexts.append(context)
        
        full_context = "\n".join(contexts)
        
        # Enhanced system prompt for more detailed answers
        system_prompt = """You are a knowledgeable AI assistant that provides detailed, well-structured answers based on YouTube video transcripts. 
Follow these guidelines:
1. Provide comprehensive answers with specific details, examples, and steps when available
2. Structure your response with clear sections using bullet points or numbered lists where appropriate
3. Include relevant quotes or specific information from the videos when possible
4. Cite the specific video source for each major point
5. If different videos provide conflicting information, acknowledge this and present both perspectives
6. If the information seems incomplete, acknowledge what's missing
7. Focus on actionable advice and practical tips when relevant"""

        # Query LLM with retry and enhanced prompt
        for attempt in range(3):
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"""Based on these video transcripts:

{full_context}

Question: {question}

Please provide a detailed, well-structured answer that covers all relevant information from the videos:"""}
                ]
                
                response = llm.invoke(messages)
                return response.content
            except Exception as e:
                if "rate_limit" in str(e).lower() and attempt < 2:
                    print(f"Rate limit hit, retrying in {(attempt + 1) * 2} seconds...")
                    time.sleep((attempt + 1) * 2)
                    continue
                if "413" in str(e):
                    return "The response was too large. Please try a more specific question or process fewer videos."
                raise
    
    except Exception as e:
        return f"Error during query: {str(e)}"

def main():
    logging.basicConfig(level=logging.INFO)
    print("\nYouTube Video Chat System")
    print("=" * 50)
    
    while True:
        try:
            print("\nOptions:")
            print("1. Process new topic")
            print("2. Ask a question")
            print("3. Exit")
            print("-" * 50)
            
            choice = input("\nChoose an option (1-3): ").strip()
            
            if choice == "1":
                topic = input("\nEnter topic to research: ").strip()
                process_content(topic)
            elif choice == "2":
                question = input("\nEnter your question: ").strip()
                print("\nSearching for answer...")
                print("-" * 50)
                answer = query_content(question)
                print(f"\nAnswer:\n{answer}")
            elif choice == "3":
                print("\nGoodbye!")
                break
            else:
                print("\nInvalid choice. Please try again.")
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")
            print("Please try again.")

if __name__ == "__main__":
    main()