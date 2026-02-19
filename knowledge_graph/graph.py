import networkx as nx

# create graph
G = nx.Graph()

# add relationships
G.add_edge("Python", "FastAPI", relation="framework")
G.add_edge("FastAPI", "Backend", relation="used_for")
G.add_edge("RAG", "ChromaDB", relation="uses")
G.add_edge("RAG", "Embeddings", relation="based_on")
G.add_edge("Ollama", "LLM", relation="type")
G.add_edge("ChromaDB", "Vector Database", relation="type")

def query_graph(node):
    if node in G:
        neighbors = list(G.neighbors(node))
        return f"{node} is related to: {', '.join(neighbors)}"
    else:
        return "No knowledge found in graph."
