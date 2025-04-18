#!/usr/bin/env python3
"""
Basic Research Agent

This script implements a research agent using LangChain and OpenAI.
It converts the functionality from the basic_researcherV2.ipynb notebook
into a standalone Python script.
"""

import os
import getpass
import argparse
import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

def set_env_var(var_name: str) -> None:
    """Set environment variable if not already set."""
    if not os.environ.get(var_name):
        os.environ[var_name] = getpass.getpass(f"{var_name}: ")

def setup_environment() -> None:
    """Setup all required environment variables."""
    # Check if we should skip prompting for environment variables
    if os.environ.get("SKIP_ENV_PROMPT") == "true":
        print("Skipping environment variable prompts...")
        return
    
    # Set OpenAI API key
    set_env_var("OPENAI_API_KEY")
    
    # Set LangChain tracing (optional)
    set_env_var("LANGCHAIN_API_KEY")
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"

def create_research_agent():
    """Create and return a research agent."""
    from langchain_openai import ChatOpenAI
    from langchain_community.tools.tavily_search import TavilySearchResults
    from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
    from langchain_community.utilities import WikipediaAPIWrapper
    from langchain.tools import Tool
    from langgraph.graph import StateGraph, END
    from langchain_core.messages import HumanMessage, AIMessage
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
    from langchain.chains import LLMChain
    
    # Initialize the LLM
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Initialize search tools
    tavily = None
    if os.environ.get("TAVILY_API_KEY"):
        tavily = TavilySearchResults(api_key=os.environ.get("TAVILY_API_KEY"))
    
    wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())
    
    # Define tools
    tools = []
    
    if tavily:
        tools.append(
            Tool(
                name="Tavily Search",
                func=tavily.run,
                description="Useful for searching the internet for current information."
            )
        )
    
    tools.append(
        Tool(
            name="Wikipedia",
            func=wikipedia.run,
            description="Useful for getting detailed information from Wikipedia."
        )
    )
    
    # Create the agent
    from langchain.agents import AgentExecutor, create_openai_functions_agent
    from langchain.agents.openai_functions_agent.agent_token_buffer_memory import AgentTokenBufferMemory
    
    # Define research prompt
    template = """You are a research assistant. Your job is to help answer questions using the available tools.

Tool Names: {tool_names}

Tool Details:
{tools}

Remember to share your thoughts after using each tool.
"""

    research_prompt = ChatPromptTemplate.from_messages([
        ("system", template),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])
    
    # Create memory for token buffer
    memory = AgentTokenBufferMemory(llm=llm, max_token_limit=2000)
    
    # Create the research agent
    research_agent = create_openai_functions_agent(
        llm=llm,
        tools=tools,
        prompt=research_prompt
    )
    
    # Create the executor with memory
    research_executor = AgentExecutor(
        agent=research_agent,
        tools=tools,
        memory=memory,
        verbose=True
    )
    
    return research_executor

def main():
    """Main function to run the research agent."""
    # Setup environment
    setup_environment()
    
    # Create the research agent
    agent = create_research_agent()
    
    # Import message classes
    from langchain_core.messages import HumanMessage, AIMessage
    
    print("Research Agent initialized. Type 'quit' to exit.")
    print("-" * 50)
    
    # Initialize chat history
    chat_history = []
    
    # Main conversation loop
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ["exit", "quit", "bye"]:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        try:
            print("\nResearching...")
            # Add chat_history to the input
            result = agent.invoke({
                "input": user_input,
                "chat_history": chat_history
            })
            print(f"\nResult: {result['output']}")
            
            # Update chat history with the user question and agent response
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=result['output']))
            
            print("-" * 50)
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a basic research agent")
    parser.add_argument("--no-env-prompt", action="store_true", 
                        help="Don't prompt for environment variables")
    args = parser.parse_args()
    
    if args.no_env_prompt:
        # Skip environment variable prompting
        os.environ["SKIP_ENV_PROMPT"] = "true"
        
    main() 