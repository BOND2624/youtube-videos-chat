import streamlit as st
from youtubevideo_chat import search_youtube_videos, process_content, query_content, validate_input
import logging
from datetime import datetime
import os
import json
from typing import Dict, Any
import hashlib
import time

def sanitize_log_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize sensitive data before logging"""
    sensitive_fields = ['api_key', 'key', 'password', 'token']
    sanitized = {}
    
    for key, value in data.items():
        if any(field in key.lower() for field in sensitive_fields):
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            sanitized[key] = sanitize_log_data(value)
        else:
            sanitized[key] = value
    return sanitized

# Set up logging
if not os.path.exists('logs'):
    os.makedirs('logs')

class CustomFormatter(logging.Formatter):
    def format(self, record):
        if hasattr(record, 'qa_data'):
            # Format Q&A data specially
            record.msg = f"Q&A Session:\n{json.dumps(record.qa_data, indent=2)}"
        return super().format(record)

# Configure logging with different levels for different handlers
file_handler = logging.FileHandler(f'logs/app_{datetime.now().strftime("%Y%m%d")}.log')
file_handler.setLevel(logging.INFO)  # Set file handler to INFO level

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)  # Set console handler to INFO level

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler, stream_handler]
)

# Apply custom formatter to file handler only
file_handler.setFormatter(CustomFormatter())

# Initialize session state
if 'processed_topic' not in st.session_state:
    st.session_state.processed_topic = None
if 'qa_history' not in st.session_state:
    st.session_state.qa_history = []
if 'videos' not in st.session_state:
    st.session_state.videos = []
if 'request_timestamps' not in st.session_state:
    st.session_state.request_timestamps = []
if 'last_cleanup_time' not in st.session_state:
    st.session_state.last_cleanup_time = time.time()

# Rate limiting
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))

def check_rate_limit() -> bool:
    """
    Implement rate limiting using session state
    Returns True if request is allowed, False if rate limit exceeded
    """
    current_time = time.time()
    
    # Cleanup old timestamps every 10 seconds to prevent memory growth
    if current_time - st.session_state.last_cleanup_time > 10:
        st.session_state.request_timestamps = [
            ts for ts in st.session_state.request_timestamps 
            if ts > current_time - 60
        ]
        st.session_state.last_cleanup_time = current_time
    
    if len(st.session_state.request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
        return False
    
    st.session_state.request_timestamps.append(current_time)
    return True

# App configuration
st.set_page_config(page_title="YouTube Chat", layout="centered")
st.title("YouTube Video Chat")

# Main input
topic = st.text_input("Topic", help="Enter a topic to search for YouTube videos")

# Pre-validate input
topic_valid = False
if topic:
    try:
        topic = validate_input(topic)
        topic_valid = True
    except ValueError as e:
        st.error(f"Invalid input: {str(e)}")

col1, col2 = st.columns(2)
with col1:
    if st.button("🔍 Search", disabled=not topic_valid):
        if not check_rate_limit():
            st.error("Rate limit exceeded. Please try again later.")
        else:
            try:
                logging.info(f"Searching videos for topic: {topic}")
                videos = search_youtube_videos(topic)
                if videos:
                    st.session_state.videos = videos
                    logging.info(f"Found {len(videos)} videos for topic: {topic}")
                    logging.info("Videos found:")
                    for video in st.session_state.videos:
                        logging.info(f"- {video['title']} (by {video['channel']})")
                    st.success(f"Found {len(videos)} videos!")
                else:
                    st.warning("No videos found for this topic")
                    logging.warning(f"No videos found for topic: {topic}")
            except Exception as e:
                logging.error(f"Error searching videos: {str(e)}")
                st.error(f"Failed to search videos: {str(e)}")

with col2:
    if st.button("📥 Process", disabled=not st.session_state.videos):
        if not check_rate_limit():
            st.error("Rate limit exceeded. Please try again later.")
        else:
            with st.spinner("Processing videos..."):
                try:
                    process_content(topic)
                    st.session_state.processed_topic = topic
                    logging.info(f"Successfully processed content for topic: {topic}")
                    st.success("✅ Processed!")
                except Exception as e:
                    logging.error(f"Error processing content: {str(e)}")
                    st.error(f"Failed to process content: {str(e)}")

# Show videos if available
if st.session_state.videos:
    st.divider()
    st.caption("Found Videos:")
    for video in st.session_state.videos:
        st.caption(f"▶ {video['title']} - {video['channel']}")

# Query section
st.divider()
question = st.text_input("Question", help="Ask about the processed videos")

# Pre-validate question
question_valid = False
if question:
    try:
        question = validate_input(question)
        question_valid = True
    except ValueError as e:
        st.error(f"Invalid input: {str(e)}")

if st.button("💭 Get Answer", disabled=not (question_valid and st.session_state.processed_topic)):
    if not check_rate_limit():
        st.error("Rate limit exceeded. Please try again later.")
    else:
        with st.spinner("Thinking..."):
            try:
                response = query_content(question)
                
                # Check if response indicates no relevant information
                if "not contain information" in response.lower():
                    st.warning("No relevant information found in the processed videos")
                    logging.warning(f"No relevant information found for question: {question}")
                else:
                    st.write(response)
                
                # Sanitize data before logging
                qa_data = sanitize_log_data({
                    "topic": st.session_state.processed_topic,
                    "question": question,
                    "answer": response,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "videos_processed": len(st.session_state.videos)
                })
                
                # Add to session history
                st.session_state.qa_history.append(qa_data)
                
                # Log with custom format
                logger = logging.getLogger()
                logger.info("", extra={"qa_data": qa_data})
                
            except Exception as e:
                error_msg = str(e)
                logging.error(f"Error getting answer: {error_msg}")
                st.error(f"Failed to get answer: {error_msg}")

# Show Q&A History
if st.session_state.qa_history:
    st.divider()
    with st.expander("📝 Q&A History"):
        for qa in st.session_state.qa_history:
            st.markdown(f"*Q:* {qa['question']}")
            st.markdown(f"*A:* {qa['answer']}")
            st.caption(f"Topic: {qa['topic']} - {qa['timestamp']}")
            st.caption(f"Videos processed: {qa.get('videos_processed', 'N/A')}")
            st.divider()