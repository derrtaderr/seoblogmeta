from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
from dotenv import load_dotenv
import pandas as pd
from bs4 import BeautifulSoup
from typing import List
import xml.etree.ElementTree as ET
import json

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

async def analyze_content_with_deepseek(content: str, title: str) -> str:
    """
    Analyze content using DeepSeek Reasoner (R1) API to generate SEO-optimized summary
    """
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    As an SEO expert, analyze this blog post titled "{title}" and create a compelling 2-3 sentence summary.
    
    Follow these steps:
    1. Identify the main topic and key concepts
    2. Extract important keywords and phrases
    3. Create a concise summary that:
       - Captures the main value proposition
       - Incorporates relevant keywords naturally
       - Uses active voice and engaging language
       - Maintains SEO best practices
    
    Blog Content:
    {content[:4000]}  # Limiting content length to avoid token limits
    
    Provide only the final summary without any additional commentary or step-by-step analysis.
    """
    
    payload = {
        "model": "deepseek-reasoner",  # Using the R1 model for better reasoning
        "messages": [
            {
                "role": "system", 
                "content": "You are an expert SEO content analyst specializing in creating engaging, keyword-rich summaries that drive organic traffic while maintaining readability and value for users."
            },
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,  # Lower temperature for more focused outputs
        "max_tokens": 150,  # Limiting response length for summary
        "top_p": 0.8,  # Maintaining good diversity while ensuring quality
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content'].strip()
            else:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"DeepSeek API error: {response.text}"
                )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling DeepSeek API: {str(e)}"
        )

@app.post("/analyze-sitemap")
async def analyze_sitemap(sitemap: SitemapURL):
    try:
        # Fetch sitemap
        async with httpx.AsyncClient() as client:
            response = await client.get(sitemap.url)
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch sitemap")
            
            # Parse sitemap XML
            root = ET.fromstring(response.text)
            blog_urls = []
            
            # Extract blog URLs
            for url in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
                if "/blog/" in url.text:
                    blog_urls.append(url.text)

        analyzed_blogs = []
        
        # Process each blog
        for blog_url in blog_urls:
            async with httpx.AsyncClient() as client:
                response = await client.get(blog_url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    title = soup.title.string if soup.title else "No title"
                    
                    # Extract main content
                    content = ""
                    main_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
                    if main_content:
                        content = main_content.get_text(strip=True)
                        
                        # Generate SEO-optimized summary using DeepSeek
                        summary = await analyze_content_with_deepseek(content, title)
                        
                        analyzed_blogs.append({
                            "title": title,
                            "url": blog_url,
                            "summary": summary
                        })

        # Create Excel file
        df = pd.DataFrame(analyzed_blogs)
        excel_path = "blog_analysis.xlsx"
        df.to_excel(excel_path, index=False)
        
        return {"status": "success", "analyzed_count": len(analyzed_blogs)}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 