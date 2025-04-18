import os
from typing import Dict, List, Tuple, TypedDict, Annotated
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import Tool
from langchain.chains import LLMChain
from langgraph.graph import StateGraph, Graph, END
from langchain.agents import AgentExecutor, create_react_agent
from langchain_community.utilities import WikipediaAPIWrapper
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun
from tavily import TavilyClient
from langchain_community.tools.tavily_search import TavilySearchResults

# Set up environment variables for tracing
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "langchain-academy"

# Load environment variables
load_dotenv()

# Initialize the LLM with specific configuration
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0
)

# Initialize Tavily search
tavily = TavilySearchResults(api_key=os.getenv("TAVILY_API_KEY"))
wikipedia = WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper())

# Define tools
tools = [
    Tool(
        name="Tavily Search",
        func=tavily.run,
        description="Useful for searching the internet for current information. Use this as your primary search tool."
    ),
    Tool(
        name="Wikipedia",
        func=wikipedia.run,
        description="Useful for getting detailed information from Wikipedia"
    )
]

# Define research prompt
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.agents.openai_functions_agent.agent_token_buffer_memory import AgentTokenBufferMemory
from langchain.agents import AgentType, create_openai_functions_agent

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

# Define synthesis prompt
synthesis_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a synthesis agent. Your task is to analyze the research and provide a clear, concise response."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "Based on the research provided, synthesize a clear response: {research_result}")
])

# Create the research agent using OpenAI Functions format
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

# Create synthesis chain
synthesis_chain = LLMChain(llm=llm, prompt=synthesis_prompt)

# Define state type
class AgentState(TypedDict):
    chat_history: List[BaseMessage]
    research_result: str
    final_response: str
    step_count: int

def research_step(state: AgentState) -> AgentState:
    """Execute research step"""
    # Extract the last user message
    last_message = next((msg.content for msg in reversed(state["chat_history"]) 
                        if isinstance(msg, HumanMessage)), "")
    
    # Execute research
    research_result = research_executor.invoke({
        "input": last_message,
        "chat_history": state["chat_history"]
    })
    
    state["research_result"] = research_result["output"]
    state["step_count"] += 1
    return state

def synthesis_step(state: AgentState) -> AgentState:
    """Execute synthesis step"""
    # Synthesize research results
    synthesis_result = synthesis_chain.invoke({
        "research_result": state["research_result"],
        "chat_history": state["chat_history"]
    })
    
    state["final_response"] = synthesis_result["text"]
    state["chat_history"].append(AIMessage(content=synthesis_result["text"]))
    state["step_count"] += 1
    return state

def should_continue(state: AgentState) -> str:
    """Determine if the process should continue"""
    if state["step_count"] >= 4 or state.get("final_response"):
        return "end"
    return "continue"

def create_agent_graph() -> Graph:
    """Create the workflow graph"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("research", research_step)
    workflow.add_node("synthesis", synthesis_step)
    
    # Add edges
    workflow.add_edge("research", "synthesis")
    workflow.add_conditional_edges(
        "synthesis",
        should_continue,
        {
            "continue": "research",
            "end": END
        }
    )
    
    # Set entry point
    workflow.set_entry_point("research")
    
    return workflow.compile()

class Chatbot:
    def __init__(self):
        self.graph = create_agent_graph()
    
    async def process_message(self, user_input: str) -> str:
        """Process user input and return response"""
        state: AgentState = {
            "chat_history": [HumanMessage(content=user_input)],
            "research_result": "",
            "final_response": "",
            "step_count": 0
        }
        
        try:
            result = await self.graph.ainvoke(state)
            return result["final_response"]
        except Exception as e:
            print(f"Error in processing: {str(e)}")
            return "I encountered an error while processing your request."

async def main():
    print("Initializing chatbot with LangChain tracing enabled...")
    chatbot = Chatbot()
    
    print("\nChatbot initialized. Type 'quit' to exit.")
    print("(Press Ctrl+C to exit at any time)")
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() == 'quit':
                break
            
            if not user_input:
                continue
                
            print("\nProcessing...")
            response = await chatbot.process_message(user_input)
            print(f"\nBot: {response}")
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())