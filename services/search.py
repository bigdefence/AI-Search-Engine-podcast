from googleapiclient.discovery import build
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from readability import Document
import requests
from rank_bm25 import BM25Okapi
import nltk
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
from utils.config import GOOGLE_API_KEY, CSE_ID, NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
from utils.text_processing import preprocess_text
import trafilatura
from urllib.parse import urlparse
from langchain.retrievers import EnsembleRetriever
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
sentence_transformer = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

async def google_search(query, api_key, cse_id, num_results=10, search_type=None):
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        params = {
            'q': query,
            'cx': cse_id,
            'num': num_results,
            'dateRestrict': 'd7'  # 지난 7일간의 뉴스 검색
        }
        
        if search_type == "image":
            params['searchType'] = "image"
        
        result = await asyncio.to_thread(service.cse().list(**params).execute)
        
        if search_type == "image":
            return [{"title": item.get('title', 'No title'),
                     "link": item.get('link', 'No link'),
                     "image": item.get('image', {}).get('thumbnailLink', '')} for item in result.get('items', [])]
        else:
            return [{"title": item.get('title', 'No title'), 
                     "snippet": item.get('snippet', 'No snippet'), 
                     "link": item.get('link', 'No link'), 
                     "image": item.get('pagemap', {}).get('cse_image', [{'src': ''}])[0].get('src', '')} for item in result.get('items', [])]
    except Exception as e:
        print(f"Google Search Error: {e}")
        return []

async def naver_search(query, num_results=10, search_type=None):
    headers = {
        "X-Naver-Client-Id": NAVER_CLIENT_ID,
        "X-Naver-Client-Secret": NAVER_CLIENT_SECRET
    }
    
    if search_type == "image":
        url = f"https://openapi.naver.com/v1/search/image?query={query}&display={num_results}&sort=date"
    else:
        url = f"https://openapi.naver.com/v1/search/news.json?query={query}&display={num_results}&sort=date"  # 뉴스 검색 및 최신순 정렬
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                result = await response.json()
                if search_type == "image":
                    return [{"title": item['title'], "link": item['link'], "image": item['thumbnail']} for item in result.get('items', [])]
                else:
                    return [{"title": item['title'], "snippet": item['description'], "link": item['link'], "source": "Naver"} for item in result.get('items', [])]
    except Exception as e:
        print(f"Naver Search Error: {e}")
        return []



def remove_duplicates(results):
    seen_links = set()
    unique_results = []
    for result in results:
        if result['link'] not in seen_links:
            unique_results.append(result)
            seen_links.add(result['link'])
    return unique_results

async def fetch_all_search_results(query):
    num_results_google = 5
    num_results_naver = 5

    google_text_task = google_search(query, GOOGLE_API_KEY, CSE_ID, num_results=num_results_google)
    naver_text_task = naver_search(query, num_results=num_results_naver)

    google_text,naver_text= await asyncio.gather(
        google_text_task,naver_text_task
    )
    
    text_results = remove_duplicates(google_text + naver_text)
    return text_results

async def fetch_content_async(url, session, timeout=10):
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                return f"Error: HTTP {response.status}"

            html_content = await response.text()
            extracted_content = trafilatura.extract(html_content)
            if extracted_content:
                text = extracted_content
            else:
                doc = Document(html_content)
                article_content = doc.summary()
                soup = BeautifulSoup(article_content, 'html.parser')
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()

            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split(" "))
            text = ' '.join(chunk for chunk in chunks if chunk)

            return text[:4000]

    except asyncio.TimeoutError:
        return "Error: Request timed out"
    except aiohttp.ClientError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"

async def fetch_and_process_content(search_results):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_content_async(result['link'], session) for result in search_results]
        contents = await asyncio.gather(*tasks)
        
        for i, content in enumerate(contents):
            if not content.startswith("Error"):
                search_results[i]['content'] = content
                search_results[i]['preprocessed_content'] = preprocess_text(content)
            else:
                search_results[i]['content'] = "No content available."
                search_results[i]['preprocessed_content'] = ""
    
    return search_results


def get_domain(url):
    return urlparse(url).netloc


def semantic_search(query, search_results, top_k=8):
    ensemble_retriever = create_ensemble_retriever(search_results, query)
    retrieved_docs = ensemble_retriever.invoke(query)
    
    retrieved_indices = []
    for doc in retrieved_docs[:top_k]:
        for i, result in enumerate(search_results):
            if result['title'] == doc.metadata['title'] and result['link'] == doc.metadata['link']:
                if i not in retrieved_indices:
                    retrieved_indices.append(i)
                break
    return retrieved_indices


def prepare_chunked_documents(search_results, chunk_size=500, chunk_overlap=50):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    
    chunked_docs = []
    for result in search_results:
        chunks = text_splitter.create_documents([result['preprocessed_content']])
        for i, chunk in enumerate(chunks):
            chunked_docs.append(Document(
                page_content=chunk.page_content,
                metadata={
                    "title": result['title'],
                    "link": result['link'],
                    "chunk_id": i
                }
            ))
    return chunked_docs

def create_ensemble_retriever(search_results, query):
    chunked_documents = prepare_chunked_documents(search_results)
    
    # BM25 Retriever 생성
    bm25_retriever = BM25Retriever.from_documents(chunked_documents)
    bm25_retriever.k = 8  # 상위 8개 결과 반환
    
    # FAISS Retriever 생성
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    faiss_vectorstore = FAISS.from_documents(chunked_documents, embeddings)
    faiss_retriever = faiss_vectorstore.as_retriever(search_kwargs={"k": 10})
    
    # Ensemble Retriever 생성
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.15, 0.85]
    )
    
    return ensemble_retriever
