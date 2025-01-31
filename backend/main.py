from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import pandas as pd
from bs4 import BeautifulSoup
from typing import List, Dict, Any
import xml.etree.ElementTree as ET
import json
from datetime import datetime
import re
import logging
import asyncio
from urllib.parse import quote

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

class SitemapURL(BaseModel):
    url: str

class BlogAnalysis(BaseModel):
    title: str
    url: str
    summary: str
    keywords: List[str]
    word_count: int
    date_analyzed: str
    slug: str
    meta_description: str

def extract_slug_from_url(url: str) -> str:
    """Extract the blog slug from the URL."""
    match = re.search(r'/post/([^/]+)/?$', url)
    return match.group(1) if match else ""

def extract_meta_description(soup: BeautifulSoup) -> str:
    """Extract meta description from the page."""
    meta_tag = soup.find('meta', attrs={'name': 'description'}) or \
               soup.find('meta', attrs={'property': 'og:description'})
    return meta_tag.get('content', '') if meta_tag else ''

def clean_url(url: str) -> str:
    """Clean and validate URL by removing whitespace and encoding special characters."""
    # Remove whitespace and newlines
    url = ' '.join(url.split())
    # Remove any non-printable characters
    url = ''.join(char for char in url if ord(char) >= 32)
    # Ensure proper encoding of special characters while preserving URL structure
    parts = url.split('://', 1)
    if len(parts) == 2:
        scheme, path = parts
        # Only encode the path part, not the scheme
        path = quote(path, safe=':/?=&')
        return f"{scheme}://{path}"
    return url

async def analyze_content_with_deepseek(title: str, content: str) -> Dict[str, Any]:
    try:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("DeepSeek API key not found in environment variables")

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        # Clean and prepare content
        cleaned_content = ' '.join(content.split())
        if len(cleaned_content) > 8000:  # Limit content length
            cleaned_content = cleaned_content[:8000] + "..."

        prompt = f"""Please analyze this blog post and provide the output in JSON format.

Title: "{title}"
Content: {cleaned_content}

Please provide:
1. An SEO-optimized meta description (2-3 sentences, max 155 characters) that includes relevant keywords and encourages clicks
2. A comprehensive SEO summary (2-3 sentences) that highlights the main value proposition and key takeaways
3. A list of 5-7 relevant keywords/phrases specific to this content, focusing on operational and business terms where applicable

Your response must be a valid JSON object with this exact structure:
{{
    "meta_description": "your meta description here",
    "seo_summary": "your summary here",
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}

Important: Respond ONLY with the JSON object, no other text."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are an expert SEO analyst. Always respond with a valid JSON object following the exact structure provided in the prompt. Do not include any other text in your response."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800
                }
            )
            
            if response.status_code == 401:
                logger.error(f"DeepSeek API authentication failed: {response.text}")
                raise ValueError("Invalid API key or authentication failed")
                
            response.raise_for_status()
            result = response.json()
            
            # Log the raw response for debugging
            logger.info(f"DeepSeek API raw response: {response.text}")
            
            if "choices" not in result or not result["choices"]:
                logger.error(f"Invalid response format from DeepSeek API: {result}")
                raise ValueError("Invalid response format from DeepSeek API")
                
            content = result["choices"][0]["message"]["content"]
            logger.info(f"DeepSeek API content response: {content}")
            
            # Clean the content string to ensure it's valid JSON
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]
            if content.endswith('```'):
                content = content[:-3]
            content = content.strip()
            
            try:
                analyzed = json.loads(content)
                return {
                    "meta_description": analyzed.get("meta_description", ""),
                    "seo_summary": analyzed.get("seo_summary", ""),
                    "keywords": analyzed.get("keywords", [])
                }
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse content as JSON: {content}")
                logger.error(f"JSON parse error: {str(e)}")
                raise ValueError(f"Failed to parse DeepSeek API response as JSON: {str(e)}")

    except httpx.HTTPError as e:
        logger.error(f"DeepSeek API error: {e.response.status_code} - {e.response.text if hasattr(e, 'response') else str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error in analyze_content_with_deepseek: {str(e)}")
        raise

async def fetch_url_with_retry(url: str, max_retries: int = 3) -> httpx.Response:
    """Fetch URL with retry logic and detailed error handling."""
    cleaned_url = clean_url(url)
    logger.info(f"Fetching URL: {cleaned_url}")
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(cleaned_url)
                response.raise_for_status()
                return response
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            if attempt == max_retries - 1:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"HTTP error: {e.response.status_code} - {e.response.text}"
                )
        except httpx.TimeoutException:
            logger.error(f"Timeout occurred while fetching {cleaned_url}")
            if attempt == max_retries - 1:
                raise HTTPException(status_code=504, detail="Request timed out")
        except Exception as e:
            logger.error(f"Error fetching {cleaned_url}: {str(e)}")
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail=f"Error fetching URL: {str(e)}")
        
        await asyncio.sleep(1)  # Wait before retrying

async def parse_sitemap_content(content: str) -> List[str]:
    """Parse sitemap content in either XML or plain text format."""
    blog_urls = []
    
    # First try to parse as XML
    try:
        root = ET.fromstring(content)
        # Check for both sitemap index and regular sitemap formats
        namespaces = {
            'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'
        }
        
        # First try to find URLs directly
        urls = root.findall(".//ns:loc", namespaces)
        if not urls:
            # If no URLs found, try without namespace
            urls = root.findall(".//loc")
        
        for url in urls:
            if url.text and "/post/" in url.text:
                cleaned_url = clean_url(url.text)
                if cleaned_url:
                    blog_urls.append(cleaned_url)
    except ET.ParseError:
        # If XML parsing fails, treat as plain text
        logger.info("Parsing sitemap as plain text")
        # Split content into lines and clean up
        lines = content.strip().split()
        for line in lines:
            line = line.strip()
            if line and "/post/" in line:
                cleaned_url = clean_url(line)
                if cleaned_url:
                    blog_urls.append(cleaned_url)
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(blog_urls))

def extract_content_from_html(soup: BeautifulSoup) -> tuple[str, int]:
    """Extract content from HTML with better handling of different content structures."""
    content = ""
    
    # Try different content selectors in order of preference
    content_selectors = [
        ('article', {}),
        ('main', {}),
        ('div', {'class_': 'content'}),
        ('div', {'class_': 'post-content'}),
        ('div', {'class_': 'blog-post'}),
        ('div', {'class_': 'entry-content'}),
        ('div', {'id': 'content'}),
        ('div', {'class_': 'article-content'})
    ]
    
    for tag, attrs in content_selectors:
        main_content = soup.find(tag, attrs)
        if main_content:
            # Remove unwanted elements
            for unwanted in main_content.find_all(['script', 'style', 'nav', 'header', 'footer']):
                unwanted.decompose()
            
            # Get text content
            content = main_content.get_text(separator=' ', strip=True)
            break
    
    # If no content found, try getting body text as fallback
    if not content and soup.body:
        content = soup.body.get_text(separator=' ', strip=True)
    
    # Clean up content
    content = ' '.join(content.split())  # Remove extra whitespace
    word_count = len(content.split())
    
    return content, word_count

@app.post("/analyze-sitemap")
async def analyze_sitemap(sitemap: SitemapURL):
    try:
        logger.info(f"Starting analysis of sitemap: {sitemap.url}")
        
        # Validate sitemap URL
        if not sitemap.url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid sitemap URL. Must start with http:// or https://")
        
        try:
            logger.info("Fetching sitemap...")
            response = await fetch_url_with_retry(sitemap.url)
            sitemap_content = response.text
            logger.info("Successfully fetched sitemap")
            
            # Parse sitemap content
            blog_urls = await parse_sitemap_content(sitemap_content)
            
            if not blog_urls:
                logger.warning("No blog URLs found in sitemap")
                raise HTTPException(status_code=404, detail="No blog posts found in sitemap")
            
            logger.info(f"Found {len(blog_urls)} blog URLs")
            
            analyzed_blogs = []
            error_count = 0
            max_errors = 3  # Maximum number of consecutive errors before stopping
            
            for blog_url in blog_urls:
                try:
                    logger.info(f"Analyzing blog: {blog_url}")
                    response = await fetch_url_with_retry(blog_url)
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Extract title
                    title = soup.title.string if soup.title else "No title"
                    title = ' '.join(title.split())  # Clean up whitespace
                    
                    # Extract meta description
                    current_meta = extract_meta_description(soup)
                    
                    # Extract content
                    content, word_count = extract_content_from_html(soup)
                    
                    if content:
                        logger.info(f"Analyzing content with DeepSeek for: {title}")
                        analysis = await analyze_content_with_deepseek(title, content)
                        
                        analyzed_blogs.append({
                            "Title": title,
                            "URL": blog_url,
                            "Slug": extract_slug_from_url(blog_url),
                            "Current Meta Description": current_meta,
                            "Suggested Meta Description": analysis.get("meta_description", ""),
                            "SEO Summary": analysis["seo_summary"],
                            "Keywords": ", ".join(analysis["keywords"]),
                            "Word Count": word_count,
                            "Date Analyzed": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        logger.info(f"Successfully analyzed: {title}")
                        error_count = 0  # Reset error count on success
                    else:
                        logger.warning(f"No content found for: {blog_url}")
                        error_count += 1
                    
                    # Add a small delay between blog analyses to avoid rate limiting
                    await asyncio.sleep(2)  # Increased delay
                    
                except Exception as e:
                    logger.error(f"Error analyzing blog {blog_url}: {str(e)}")
                    error_count += 1
                    if error_count >= max_errors:
                        logger.error(f"Too many consecutive errors ({max_errors}), stopping analysis")
                        break
                    continue

            if not analyzed_blogs:
                raise HTTPException(status_code=404, detail="No blogs could be analyzed successfully")

            # Create Excel file
            logger.info("Creating Excel file...")
            df = pd.DataFrame(analyzed_blogs)
            
            column_order = [
                "Title",
                "URL",
                "Slug",
                "Current Meta Description",
                "Suggested Meta Description",
                "SEO Summary",
                "Keywords",
                "Word Count",
                "Date Analyzed"
            ]
            df = df[column_order]
            
            excel_path = "blog_analysis.xlsx"
            
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Blog Analysis')
                
                worksheet = writer.sheets['Blog Analysis']
                for idx, col in enumerate(df.columns):
                    max_length = max(
                        df[col].astype(str).apply(len).max(),
                        len(col)
                    )
                    worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 100)
            
            logger.info(f"Analysis completed successfully. Analyzed {len(analyzed_blogs)} blogs.")
            return {
                "status": "success", 
                "analyzed_count": len(analyzed_blogs),
                "excel_path": excel_path
            }
            
        except Exception as e:
            logger.error(f"Error processing sitemap: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error processing sitemap: {str(e)}")
            
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 