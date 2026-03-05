import networkx as nx

G = nx.Graph()

# ==============================
# Diseases and symptoms
# ==============================
G.add_edge("Fever", "Viral Infection", relation="symptom_of")
G.add_edge("Cold", "Viral Infection", relation="symptom_of")
G.add_edge("Cough", "Viral Infection", relation="symptom_of")

G.add_edge("Headache", "Migraine", relation="symptom_of")
G.add_edge("Nausea", "Migraine", relation="symptom_of")

G.add_edge("Chest Pain", "Heart Disease", relation="symptom_of")
G.add_edge("High BP", "Heart Disease", relation="risk")

G.add_edge("High Sugar", "Diabetes", relation="symptom_of")
G.add_edge("Frequent Urination", "Diabetes", relation="symptom_of")

# ==============================
# Medicines
# ==============================
G.add_edge("Paracetamol", "Fever", relation="treats")
G.add_edge("Dolo 650", "Fever", relation="treats")
G.add_edge("Insulin", "Diabetes", relation="treats")
G.add_edge("Aspirin", "Heart Disease", relation="treats")

# ==============================
def query_graph(term):
    term = term.title()

    if term not in G:
        return "No medical knowledge found."

    neighbors = list(G.neighbors(term))
    response = f"🩺 Medical Info for {term}:\n"

    for n in neighbors:
        relation = G.get_edge_data(term, n)["relation"]
        response += f"- {relation} → {n}\n"

    response += "\n⚠️ This is AI guidance only. Consult a doctor for real diagnosis."
    return response