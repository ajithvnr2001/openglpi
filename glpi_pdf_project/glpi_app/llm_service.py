import os
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from unstructured.partition.html import partition_html
from typing import List, Dict
from langchain.llms import OpenAI
from langchain.embeddings import HuggingFaceEmbeddings

class LLMService:
    def __init__(self, model_name: str = "Meta-Llama-3-1-8B-Instruct-FP8"):
        self.model_name = model_name
        self.akash_api_key = os.environ.get("AKASH_API_KEY")
        self.api_base = os.environ.get("AKASH_API_BASE", "https://chatapi.akash.network/api/v1")

        if not self.akash_api_key:
            raise ValueError("AKASH_API_KEY environment variable not set.")

        self.llm = OpenAI(
            model_name=self.model_name,
            openai_api_key=self.akash_api_key,
            openai_api_base=self.api_base,
            temperature=0.7,
            max_tokens=200
        )

    def get_embedding_function(self):
        return HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5")

    def create_vectorstore(self, chunks: List[Dict]):
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [{k: v for k, v in chunk.items() if k != "text"} for chunk in chunks]
        embeddings = self.get_embedding_function()
        return Chroma.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)

    def query_llm(self, db, query: str):
        qa = RetrievalQA.from_chain_type(
            llm=self.llm, 
            chain_type="stuff", 
            retriever=db.as_retriever()
        )
        return qa.run(query)

    def rag_completion(self, documents, query):
        chunks = self.process_documents_to_chunks(documents)
        vector_store = self.create_vectorstore(chunks)
        return self.query_llm(vector_store, query)

    def process_documents_to_chunks(self, documents: List[Dict]) -> List[Dict]:
        chunks = []
        for doc in documents:
            if "content" in doc:
                elements = partition_html(text=doc["content"])
                chunks.extend({
                    "text": str(element),
                    "source_id": doc.get("id"),
                    "source_type": "glpi_ticket"
                } for element in elements)
        return chunks

    def complete(self, prompt, context=None):
        full_prompt = f"{context}\n{prompt}" if context else prompt
        return self.llm.invoke(full_prompt)
