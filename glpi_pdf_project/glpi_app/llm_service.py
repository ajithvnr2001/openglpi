import os
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from unstructured.partition.html import partition_html
from typing import List, Dict
from langchain_openai import OpenAI  # Import from langchain_openai
from langchain_community.embeddings import HuggingFaceEmbeddings  # Import from langchain_community


class LLMService:
    def __init__(self, model_name: str = "Meta-Llama-3-1-8B-Instruct-FP8"):  # Default to a Llama3 model
        self.model_name = model_name
        self.akash_api_key = os.environ.get("AKASH_API_KEY")
        self.api_base = os.environ.get("AKASH_API_BASE", "https://chatapi.akash.network/api/v1")

        if not self.akash_api_key:
            raise ValueError("AKASH_API_KEY environment variable not set.")

        self.llm = OpenAI(
            model=self.model_name,  # Use 'model' instead of 'model_name'
            api_key=self.akash_api_key,  # Use 'api_key' instead of 'openai_api_key'
            base_url=self.api_base,  # Use 'base_url' instead of 'openai_api_base'
            temperature=0.2,
            max_tokens=500
        )

    def get_embedding_function(self):
        """Returns the HuggingFace embedding function for BAAI/bge-large-en-v1.5."""
        return HuggingFaceEmbeddings(model_name="BAAI/bge-large-en-v1.5")

    def create_vectorstore(self, chunks: List[Dict]):
        """Creates a Chroma vector store from a list of text chunks."""
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [
            {key: value for key, value in chunk.items() if key != "text"}
            for chunk in chunks
        ]
        embeddings = self.get_embedding_function()
        db = Chroma.from_texts(texts=texts, embedding=embeddings, metadatas=metadatas)
        return db

    def query_llm(self, db, query: str):
        """Queries the LLM using RetrievalQA."""
        qa = RetrievalQA.from_chain_type(
            llm=self.llm, chain_type="stuff", retriever=db.as_retriever(search_kwargs={'k': 1})
        )
        result = qa.invoke({"query": query})["result"] # Use invoke and get result
        return result

    def rag_completion(self, documents, query):
        """RAG completion on the documents based on the query."""
        chunks = self.process_documents_to_chunks(documents)
        vector_store = self.create_vectorstore(chunks)
        return self.query_llm(vector_store, query)

    def process_documents_to_chunks(self, documents: List[Dict]) -> List[Dict]:
        """Processes GLPI documents and extracts text chunks."""
        chunks = []
        list_tags = ["ul", "ol", "li"]  # List of tags to include as list items
        for doc in documents:
            if "content" in doc:
                content = doc["content"]
                elements = partition_html(text=content, include_page_breaks=False, include_metadata=False, include_element_types=list_tags)
                for element in elements:
                    chunks.append(
                        {
                            "text": str(element),
                            "source_id": doc.get("id"),
                            "source_type": "glpi_ticket",
                        }
                    )
        return chunks

    def complete(self, prompt, context=None):
        """Completes a prompt using the OpenAI-compatible API."""
        if context:
          prompt = context + prompt
        return self.llm.invoke(prompt)
