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

class SitemapURL(BaseModel):
    url: str

class BlogAnalysis(BaseModel):
    title: str
    url: str
    summary: str

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
                    
                    # Extract main content (this might need adjustment based on your blog structure)
                    content = ""
                    main_content = soup.find('article') or soup.find('main') or soup.find('div', class_='content')
                    if main_content:
                        content = main_content.get_text(strip=True)
                    
                    # Call DeepSek API for analysis (placeholder - you'll need to implement this)
                    # This is where you'll integrate with DeepSek's API
                    summary = "Placeholder summary - DeepSek API integration pending"
                    
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