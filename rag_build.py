"""Construye el indice RAG.

Carga los archivos .md de una carpeta con LangChain, genera embeddings con
Ollama (nomic-embed-text) y los guarda en una base vectorial local ChromaDB.

Uso:
    python rag_build.py [--docs DIR] [--chroma DIR] [--collection NOMBRE]
"""

import argparse
import uuid

import chromadb

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_community.embeddings import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

CHROMA_DIR = "./chroma_db"
DOCS_DIR = "./docs"
COLLECTION_NAME = "docs_rag"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_EMBED_MODEL = "nomic-embed-text"


def build_index(docs_dir: str, chroma_dir: str, collection_name: str) -> None:
    print(f"[1/4] Cargando documentos desde {docs_dir} ...")
    loader = DirectoryLoader(
        docs_dir,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=True,
    )
    documents = loader.load()
    if not documents:
        raise SystemExit(f"No se encontraron archivos .md en {docs_dir}")

    print(f"[2/4] Dividiendo en fragmentos ({len(documents)} documentos) ...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"      -> {len(chunks)} fragmentos generados")

    print(f"[3/4] Generando embeddings con Ollama ({OLLAMA_EMBED_MODEL}) ...")
    embeddings = OllamaEmbeddings(
        model=OLLAMA_EMBED_MODEL,
        base_url=OLLAMA_BASE_URL,
    )
    texts = [chunk.page_content for chunk in chunks]
    vectors = embeddings.embed_documents(texts)

    print(f"[4/4] Guardando {len(vectors)} vectores en ChromaDB ({chroma_dir}) ...")
    client = chromadb.PersistentClient(
        path=chroma_dir,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
    )
    try:
        client.delete_collection(collection_name)
    except Exception:
        pass
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},
    )
    collection.add(
        ids=[f"chunk_{uuid.uuid4().hex}" for _ in chunks],
        documents=texts,
        embeddings=vectors,
        metadatas=[{"source": chunk.metadata.get("source", "desconocido")} for chunk in chunks],
    )
    print(f"      -> Indice listo con {collection.count()} fragmentos en la coleccion '{collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construye el indice RAG en ChromaDB.")
    parser.add_argument("--docs", default=DOCS_DIR, help="Carpeta con los archivos .md")
    parser.add_argument("--chroma", default=CHROMA_DIR, help="Carpeta de ChromaDB")
    parser.add_argument("--collection", default=COLLECTION_NAME, help="Nombre de la coleccion")
    args = parser.parse_args()
    build_index(args.docs, args.chroma, args.collection)
