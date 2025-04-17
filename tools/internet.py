import os
from langchain_core.tools import tool
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.document_loaders import FireCrawlLoader
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium_recaptcha_solver import RecaptchaSolver
from selenium.webdriver.common.by import By
from typing import Annotated, List, Union, Dict, Any
from bs4 import BeautifulSoup
from logger import setup_logger
from load_cfg import FIRECRAWL_API_KEY,CHROMEDRIVER_PATH
from pydantic import BaseModel, Field
import time
import random
import json

# Set up logger
logger = setup_logger()

# Global search counter
search_count = 0
MAX_SEARCHES = 5

class URLListInput(BaseModel):
    urls: List[str] = Field(description="List of URLs to scrape")

@tool
def google_search(query: str) -> str:
    """
    Perform a Google search based on the given query and return the top 5 results.
    Limited to 5 searches per session.

    Args:
        query (str): The search query to use.

    Returns:
        str: A string containing the titles, snippets, and links of the top 5 search results.
    """
    global search_count
    
    if search_count >= MAX_SEARCHES:
        logger.warning("Maximum number of searches reached")
        return "Error: Maximum number of searches (5) reached for this session"
    
    search_count += 1
    logger.info(f"Search {search_count}/{MAX_SEARCHES} for query: {query}")

    try:
        time.sleep(random.uniform(2, 5))
        logger.info(f"Performing Google search for query: {query}")
        chrome_options = Options()
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
        chrome_options.add_argument(f'--user-agent={user_agent}')
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        service = Service(CHROMEDRIVER_PATH)

        with webdriver.Chrome(options=chrome_options, service=service) as driver:
            encoded_query = query.replace(" ", "+")
            url = f"https://www.google.com/search?q={encoded_query}"
            driver.get(url)
            time.sleep(random.uniform(3, 7))

            # Check if CAPTCHA is present and solve it if needed
            if "recaptcha" in driver.page_source:
                logger.info("CAPTCHA detected. Attempting to solve...")
                print("CAPTCHA detected! Please solve it manually in the browser window.")
                print("The script will wait until you complete the CAPTCHA.")
                # Wait for manual CAPTCHA solving
                # You can adjust the maximum wait time as needed
                max_wait_time = 300  # 5 minutes
                wait_increment = 5   # Check every 5 seconds
                waited = 0
                
                while waited < max_wait_time:
                    # Check if we're past the CAPTCHA page
                    if "recaptcha" not in driver.page_source and "Our systems have detected unusual traffic" not in driver.page_source:
                        print("CAPTCHA appears to be solved! Continuing...")
                        break
                    
                    time.sleep(wait_increment)
                    waited += wait_increment
                    if waited % 30 == 0:  # Notify every 30 seconds
                        print(f"Still waiting for CAPTCHA to be solved... ({waited} seconds elapsed)")
                
                if waited >= max_wait_time:
                    logger.warning("Maximum wait time for CAPTCHA exceeded")
                    return "Error: CAPTCHA solving timeout exceeded"
            
            # Wait for the search results to load
            driver.implicitly_wait(5)

            html = driver.page_source

        soup = BeautifulSoup(html, 'html.parser')
        search_results = soup.select('.g') 
        search = ""
        for result in search_results[:5]:
            time.sleep(random.uniform(0.5, 1.5))
            title_element = result.select_one('h3')
            title = title_element.text if title_element else 'No Title'
            snippet_element = result.select_one('.VwiC3b')
            snippet = snippet_element.text if snippet_element else 'No Snippet'
            link_element = result.select_one('a')
            link = link_element['href'] if link_element else 'No Link'
            search += f"{title}\n{snippet}\n{link}\n\n"

        logger.info("Google search completed successfully")
        return search
    except Exception as e:
        logger.error(f"Error during Google search: {str(e)}")
        return f'Error: {e}'

@tool
def scrape_webpage(url: str) -> str:
    """
    Scrape a single web page for detailed information using WebBaseLoader.
    
    Args:
        url (str): The URL to scrape.
        
    Returns:
        str: The content of the scraped web page.
    """
    try:
        logger.info(f"Scraping webpage: {url}")
        loader = WebBaseLoader([url])
        docs = loader.load()
        content = "\n\n".join([f'\n{doc.page_content}\n' for doc in docs])
        logger.info("Webpage scraping completed successfully")
        return content
    except Exception as e:
        logger.error(f"Error during webpage scraping: {str(e)}")
        return f"Error during webpage scraping: {str(e)}"

@tool
def firecrawl_scrape_webpage(url: str) -> str:
    """
    Scrape a single web page using FireCrawlLoader.
    
    Args:
        url (str): The URL to scrape.
        
    Returns:
        str: The content of the scraped web page.
    """
    if not FIRECRAWL_API_KEY:
        return "Error: FireCrawl API key is not set"

    try:
        logger.info(f"Scraping webpage using FireCrawl: {url}")
        loader = FireCrawlLoader(
            api_key=FIRECRAWL_API_KEY,
            url=url,
            mode="scrape"
        )
        result = loader.load()
        logger.info("FireCrawl scraping completed successfully")
        return str(result)
    except Exception as e:
        logger.error(f"Error during FireCrawl scraping: {str(e)}")
        return f"Error during FireCrawl scraping: {str(e)}"

@tool
def scrape_webpages_with_fallback(urls_str: str) -> str:
    """
    Attempt to scrape webpages using FireCrawl, falling back to WebBaseLoader if unsuccessful.
    
    Args:
        urls_str (str): A string of comma-separated URLs or a JSON string of URLs.
        
    Returns:
        str: The scraped content from either FireCrawl or WebBaseLoader.
    """
    logger.info(f"Received URLs: {urls_str}")
    
    try:
        # Try to parse as JSON first
        try:
            urls = json.loads(urls_str)
        except:
            # If not JSON, try to parse as comma-separated list
            urls = [url.strip() for url in urls_str.split(',')]
        
        # If it's a single string (not a list), make it a list
        if isinstance(urls, str):
            urls = [urls]
            
        logger.info(f"Parsed URLs: {urls}")
            
        all_content = []
        
        for url in urls:
            try:
                logger.info(f"Attempting to scrape {url} with FireCrawl")
                content = firecrawl_scrape_webpage(url)
                
                # If we got an error message back, try the fallback
                if content.startswith("Error"):
                    logger.warning(f"FireCrawl failed for {url}, trying WebBaseLoader")
                    content = scrape_webpage(url)
                    
                all_content.append(f"--- Content from {url} ---\n{content}")
            except Exception as e:
                logger.error(f"Both scraping methods failed for {url}: {str(e)}")
                all_content.append(f"Error scraping {url}: {str(e)}")
        
        return "\n\n".join(all_content)
    except Exception as e:
        logger.error(f"Error in scrape_webpages_with_fallback: {str(e)}")
        return f"Error: Unable to scrape webpages: {str(e)}"

logger.info("Web scraping tools initialized")


