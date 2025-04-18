# Import relevant functionality
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

# Load environment variables from .env file
load_dotenv()

# Create the agent
memory = MemorySaver()
model = ChatOpenAI(model_name="gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
search = TavilySearchResults(max_results=2, api_key=os.getenv("TAVILY_API_KEY"))
tools = [search]
agent_executor = create_react_agent(model, tools, checkpointer=memory)

# Initialize conversation history
conversation_history = []
thread_id = "abc123"  # You can generate a unique ID if needed

def chat_with_agent(user_input):
    # Add user message to history
    conversation_history.append(HumanMessage(content=user_input))
    
    # Configure the agent
    config = {"configurable": {"thread_id": thread_id}}
    
    # Process the conversation
    for step in agent_executor.stream(
        {"messages": conversation_history},
        config,
        stream_mode="values",
    ):
        # Get the latest message
        latest_message = step["messages"][-1]
        
    # Add the agent's response to history
    conversation_history.append(latest_message)
    
    # Return the latest message for display
    return latest_message

# Interactive chat loop
print("Welcome to the AI Assistant! Type 'exit' to end the conversation.")
print("=" * 50)



# Main conversation loop
while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit", "bye"]:
        print("Goodbye!")
        break
    
    response = chat_with_agent(user_input)
    print("AI Assistant:")
    response.pretty_print()
    print("=" * 50)