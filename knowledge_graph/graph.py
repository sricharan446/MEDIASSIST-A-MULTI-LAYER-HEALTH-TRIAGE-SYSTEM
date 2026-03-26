"""
MediAssist Knowledge Graph
Comprehensive medical relationships: symptoms, diseases, medicines, and risk factors
"""

import networkx as nx

G = nx.Graph()

# ==============================
# CARDIOVASCULAR DISEASES
# ==============================
# Coronary Artery Disease
G.add_edge("Chest Pain", "Coronary Artery Disease", relation="symptom_of")
G.add_edge("Shortness of Breath", "Coronary Artery Disease", relation="symptom_of")
G.add_edge("Arm Pain", "Coronary Artery Disease", relation="symptom_of")
G.add_edge("High Cholesterol", "Coronary Artery Disease", relation="risk")
G.add_edge("Hypertension", "Coronary Artery Disease", relation="risk")
G.add_edge("Aspirin", "Coronary Artery Disease", relation="treats")
G.add_edge("Atorvastatin", "Coronary Artery Disease", relation="treats")

# Heart Failure
G.add_edge("Shortness of Breath", "Heart Failure", relation="symptom_of")
G.add_edge("Swelling", "Heart Failure", relation="symptom_of")
G.add_edge("Fatigue", "Heart Failure", relation="symptom_of")
G.add_edge("Rapid Heartbeat", "Heart Failure", relation="symptom_of")
G.add_edge("Furosemide", "Heart Failure", relation="treats")
G.add_edge("Ramipril", "Heart Failure", relation="treats")

# Hypertension
G.add_edge("Headache", "Hypertension", relation="symptom_of")
G.add_edge("Dizziness", "Hypertension", relation="symptom_of")
G.add_edge("Chest Pain", "Hypertension", relation="symptom_of")
G.add_edge("Obesity", "Hypertension", relation="risk")
G.add_edge("Amlodipine", "Hypertension", relation="treats")
G.add_edge("Losartan", "Hypertension", relation="treats")

# Stroke
G.add_edge("Numbness", "Stroke", relation="symptom_of")
G.add_edge("Confusion", "Stroke", relation="symptom_of")
G.add_edge("Speech Difficulty", "Stroke", relation="symptom_of")
G.add_edge("Vision Problems", "Stroke", relation="symptom_of")
G.add_edge("Hypertension", "Stroke", relation="risk")
G.add_edge("Diabetes", "Stroke", relation="risk")

# Arrhythmia
G.add_edge("Palpitations", "Arrhythmia", relation="symptom_of")
G.add_edge("Dizziness", "Arrhythmia", relation="symptom_of")
G.add_edge("Fainting", "Arrhythmia", relation="symptom_of")
G.add_edge("Metoprolol", "Arrhythmia", relation="treats")

# ==============================
# RESPIRATORY DISEASES
# ==============================
# Viral Infection / Common Cold
G.add_edge("Fever", "Viral Infection", relation="symptom_of")
G.add_edge("Cough", "Viral Infection", relation="symptom_of")
G.add_edge("Fatigue", "Viral Infection", relation="symptom_of")
G.add_edge("Paracetamol", "Viral Infection", relation="treats")

G.add_edge("Runny Nose", "Common Cold", relation="symptom_of")
G.add_edge("Sneezing", "Common Cold", relation="symptom_of")
G.add_edge("Sore Throat", "Common Cold", relation="symptom_of")
G.add_edge("Cetirizine", "Common Cold", relation="treats")

# Flu
G.add_edge("Fever", "Flu", relation="symptom_of")
G.add_edge("Body Aches", "Flu", relation="symptom_of")
G.add_edge("Chills", "Flu", relation="symptom_of")
G.add_edge("Oseltamivir", "Flu", relation="treats")

# COVID-19
G.add_edge("Fever", "COVID-19", relation="symptom_of")
G.add_edge("Dry Cough", "COVID-19", relation="symptom_of")
G.add_edge("Loss of Smell", "COVID-19", relation="symptom_of")
G.add_edge("Loss of Taste", "COVID-19", relation="symptom_of")
G.add_edge("Fatigue", "COVID-19", relation="symptom_of")

# Pneumonia
G.add_edge("Fever", "Pneumonia", relation="symptom_of")
G.add_edge("Cough", "Pneumonia", relation="symptom_of")
G.add_edge("Chest Pain", "Pneumonia", relation="symptom_of")
G.add_edge("Shortness of Breath", "Pneumonia", relation="symptom_of")
G.add_edge("Amoxicillin", "Pneumonia", relation="treats")
G.add_edge("Azithromycin", "Pneumonia", relation="treats")

# Asthma
G.add_edge("Wheezing", "Asthma", relation="symptom_of")
G.add_edge("Shortness of Breath", "Asthma", relation="symptom_of")
G.add_edge("Chest Tightness", "Asthma", relation="symptom_of")
G.add_edge("Cough", "Asthma", relation="symptom_of")
G.add_edge("Salbutamol", "Asthma", relation="treats")
G.add_edge("Budesonide", "Asthma", relation="treats")

# COPD
G.add_edge("Chronic Cough", "COPD", relation="symptom_of")
G.add_edge("Shortness of Breath", "COPD", relation="symptom_of")
G.add_edge("Wheezing", "COPD", relation="symptom_of")
G.add_edge("Smoking", "COPD", relation="risk")
G.add_edge("Tiotropium", "COPD", relation="treats")

# ==============================
# GASTROINTESTINAL DISEASES
# ==============================
# GERD
G.add_edge("Heartburn", "GERD", relation="symptom_of")
G.add_edge("Regurgitation", "GERD", relation="symptom_of")
G.add_edge("Chest Pain", "GERD", relation="symptom_of")
G.add_edge("Pantoprazole", "GERD", relation="treats")
G.add_edge("Omeprazole", "GERD", relation="treats")

# Peptic Ulcer
G.add_edge("Stomach Pain", "Peptic Ulcer", relation="symptom_of")
G.add_edge("Bloating", "Peptic Ulcer", relation="symptom_of")
G.add_edge("Nausea", "Peptic Ulcer", relation="symptom_of")
G.add_edge("Omeprazole", "Peptic Ulcer", relation="treats")
G.add_edge("Sucralfate", "Peptic Ulcer", relation="treats")

# IBS
G.add_edge("Abdominal Pain", "IBS", relation="symptom_of")
G.add_edge("Bloating", "IBS", relation="symptom_of")
G.add_edge("Diarrhea", "IBS", relation="symptom_of")
G.add_edge("Constipation", "IBS", relation="symptom_of")
G.add_edge("Mebeverine", "IBS", relation="treats")

# Gastroenteritis
G.add_edge("Nausea", "Gastroenteritis", relation="symptom_of")
G.add_edge("Vomiting", "Gastroenteritis", relation="symptom_of")
G.add_edge("Diarrhea", "Gastroenteritis", relation="symptom_of")
G.add_edge("ORS", "Gastroenteritis", relation="treats")
G.add_edge("Ondansetron", "Gastroenteritis", relation="treats")

# ==============================
# ENDOCRINE DISEASES
# ==============================
# Diabetes
G.add_edge("Frequent Urination", "Diabetes", relation="symptom_of")
G.add_edge("Excessive Thirst", "Diabetes", relation="symptom_of")
G.add_edge("Fatigue", "Diabetes", relation="symptom_of")
G.add_edge("Blurred Vision", "Diabetes", relation="symptom_of")
G.add_edge("Obesity", "Diabetes", relation="risk")
G.add_edge("Metformin", "Diabetes", relation="treats")
G.add_edge("Insulin", "Diabetes", relation="treats")

# Hypothyroidism
G.add_edge("Fatigue", "Hypothyroidism", relation="symptom_of")
G.add_edge("Weight Gain", "Hypothyroidism", relation="symptom_of")
G.add_edge("Cold Intolerance", "Hypothyroidism", relation="symptom_of")
G.add_edge("Constipation", "Hypothyroidism", relation="symptom_of")
G.add_edge("Levothyroxine", "Hypothyroidism", relation="treats")

# Hyperthyroidism
G.add_edge("Weight Loss", "Hyperthyroidism", relation="symptom_of")
G.add_edge("Rapid Heartbeat", "Hyperthyroidism", relation="symptom_of")
G.add_edge("Anxiety", "Hyperthyroidism", relation="symptom_of")
G.add_edge("Tremors", "Hyperthyroidism", relation="symptom_of")
G.add_edge("Methimazole", "Hyperthyroidism", relation="treats")

# ==============================
# MUSCULOSKELETAL DISEASES
# ==============================
# Rheumatoid Arthritis
G.add_edge("Joint Pain", "Rheumatoid Arthritis", relation="symptom_of")
G.add_edge("Joint Swelling", "Rheumatoid Arthritis", relation="symptom_of")
G.add_edge("Morning Stiffness", "Rheumatoid Arthritis", relation="symptom_of")
G.add_edge("Methotrexate", "Rheumatoid Arthritis", relation="treats")

# Osteoarthritis
G.add_edge("Joint Pain", "Osteoarthritis", relation="symptom_of")
G.add_edge("Stiffness", "Osteoarthritis", relation="symptom_of")
G.add_edge("Limited Movement", "Osteoarthritis", relation="symptom_of")
G.add_edge("Age", "Osteoarthritis", relation="risk")
G.add_edge("Paracetamol", "Osteoarthritis", relation="treats")
G.add_edge("Glucosamine", "Osteoarthritis", relation="treats")

# Gout
G.add_edge("Intense Joint Pain", "Gout", relation="symptom_of")
G.add_edge("Swelling", "Gout", relation="symptom_of")
G.add_edge("Redness", "Gout", relation="symptom_of")
G.add_edge("High Uric Acid", "Gout", relation="risk")
G.add_edge("Colchicine", "Gout", relation="treats")
G.add_edge("Allopurinol", "Gout", relation="treats")

# Sciatica
G.add_edge("Lower Back Pain", "Sciatica", relation="symptom_of")
G.add_edge("Leg Pain", "Sciatica", relation="symptom_of")
G.add_edge("Numbness", "Sciatica", relation="symptom_of")
G.add_edge("Tingling", "Sciatica", relation="symptom_of")
G.add_edge("Pregabalin", "Sciatica", relation="treats")

# Fibromyalgia
G.add_edge("Widespread Pain", "Fibromyalgia", relation="symptom_of")
G.add_edge("Fatigue", "Fibromyalgia", relation="symptom_of")
G.add_edge("Sleep Problems", "Fibromyalgia", relation="symptom_of")
G.add_edge("Cognitive Difficulties", "Fibromyalgia", relation="symptom_of")
G.add_edge("Pregabalin", "Fibromyalgia", relation="treats")
G.add_edge("Duloxetine", "Fibromyalgia", relation="treats")

# ==============================
# NEUROLOGICAL DISEASES
# ==============================
# Migraine
G.add_edge("Headache", "Migraine", relation="symptom_of")
G.add_edge("Nausea", "Migraine", relation="symptom_of")
G.add_edge("Light Sensitivity", "Migraine", relation="symptom_of")
G.add_edge("Sumatriptan", "Migraine", relation="treats")
G.add_edge("Naproxen", "Migraine", relation="treats")

# Epilepsy
G.add_edge("Seizures", "Epilepsy", relation="symptom_of")
G.add_edge("Loss of Consciousness", "Epilepsy", relation="symptom_of")
G.add_edge("Confusion", "Epilepsy", relation="symptom_of")
G.add_edge("Levetiracetam", "Epilepsy", relation="treats")

# Vertigo
G.add_edge("Dizziness", "Vertigo", relation="symptom_of")
G.add_edge("Loss of Balance", "Vertigo", relation="symptom_of")
G.add_edge("Nausea", "Vertigo", relation="symptom_of")
G.add_edge("Betahistine", "Vertigo", relation="treats")
G.add_edge("Meclizine", "Vertigo", relation="treats")

# ==============================
# MENTAL HEALTH
# ==============================
# Anxiety
G.add_edge("Excessive Worry", "Anxiety", relation="symptom_of")
G.add_edge("Restlessness", "Anxiety", relation="symptom_of")
G.add_edge("Palpitations", "Anxiety", relation="symptom_of")
G.add_edge("Escitalopram", "Anxiety", relation="treats")

# Depression
G.add_edge("Persistent Sadness", "Depression", relation="symptom_of")
G.add_edge("Loss of Interest", "Depression", relation="symptom_of")
G.add_edge("Fatigue", "Depression", relation="symptom_of")
G.add_edge("Sleep Changes", "Depression", relation="symptom_of")
G.add_edge("Sertraline", "Depression", relation="treats")

# Panic Disorder
G.add_edge("Panic Attacks", "Panic Disorder", relation="symptom_of")
G.add_edge("Palpitations", "Panic Disorder", relation="symptom_of")
G.add_edge("Shortness of Breath", "Panic Disorder", relation="symptom_of")
G.add_edge("Paroxetine", "Panic Disorder", relation="treats")

# ==============================
# INFECTIOUS DISEASES
# ==============================
# Malaria
G.add_edge("Fever", "Malaria", relation="symptom_of")
G.add_edge("Chills", "Malaria", relation="symptom_of")
G.add_edge("Sweating", "Malaria", relation="symptom_of")
G.add_edge("Artemether", "Malaria", relation="treats")

# Dengue
G.add_edge("Fever", "Dengue", relation="symptom_of")
G.add_edge("Rash", "Dengue", relation="symptom_of")
G.add_edge("Joint Pain", "Dengue", relation="symptom_of")
G.add_edge("Eye Pain", "Dengue", relation="symptom_of")
G.add_edge("Paracetamol", "Dengue", relation="treats")

# Typhoid
G.add_edge("Sustained Fever", "Typhoid", relation="symptom_of")
G.add_edge("Headache", "Typhoid", relation="symptom_of")
G.add_edge("Weakness", "Typhoid", relation="symptom_of")
G.add_edge("Azithromycin", "Typhoid", relation="treats")

# UTI
G.add_edge("Burning Urination", "UTI", relation="symptom_of")
G.add_edge("Frequent Urination", "UTI", relation="symptom_of")
G.add_edge("Cloudy Urine", "UTI", relation="symptom_of")
G.add_edge("Nitrofurantoin", "UTI", relation="treats")

# ==============================
# DERMATOLOGICAL
# ==============================
# Eczema
G.add_edge("Itching", "Eczema", relation="symptom_of")
G.add_edge("Dry Skin", "Eczema", relation="symptom_of")
G.add_edge("Red Patches", "Eczema", relation="symptom_of")
G.add_edge("Hydrocortisone", "Eczema", relation="treats")

# Psoriasis
G.add_edge("Red Patches", "Psoriasis", relation="symptom_of")
G.add_edge("Silvery Scales", "Psoriasis", relation="symptom_of")
G.add_edge("Itching", "Psoriasis", relation="symptom_of")
G.add_edge("Clobetasol", "Psoriasis", relation="treats")

# Shingles
G.add_edge("Painful Rash", "Shingles", relation="symptom_of")
G.add_edge("Blisters", "Shingles", relation="symptom_of")
G.add_edge("Burning", "Shingles", relation="symptom_of")
G.add_edge("Acyclovir", "Shingles", relation="treats")

# ==============================
# UROLOGICAL
# ==============================
# Kidney Stones
G.add_edge("Severe Flank Pain", "Kidney Stones", relation="symptom_of")
G.add_edge("Blood in Urine", "Kidney Stones", relation="symptom_of")
G.add_edge("Painful Urination", "Kidney Stones", relation="symptom_of")
G.add_edge("Tamsulosin", "Kidney Stones", relation="treats")

# BPH
G.add_edge("Frequent Urination", "BPH", relation="symptom_of")
G.add_edge("Weak Urine Stream", "BPH", relation="symptom_of")
G.add_edge("Difficulty Starting Urination", "BPH", relation="symptom_of")
G.add_edge("Age", "BPH", relation="risk")
G.add_edge("Tamsulosin", "BPH", relation="treats")
G.add_edge("Finasteride", "BPH", relation="treats")

# ==============================
# ANEMIA
# ==============================
G.add_edge("Fatigue", "Anemia", relation="symptom_of")
G.add_edge("Pale Skin", "Anemia", relation="symptom_of")
G.add_edge("Weakness", "Anemia", relation="symptom_of")
G.add_edge("Dizziness", "Anemia", relation="symptom_of")
G.add_edge("Ferrous Sulphate", "Anemia", relation="treats")
G.add_edge("Vitamin B12", "Anemia", relation="treats")


# ==============================
# QUERY FUNCTION
# ==============================
def query_graph(term: str) -> str:
    """
    Query the medical knowledge graph for information about a term.
    Returns symptoms, diseases, medicines, or risk factors related to the term.
    """
    term = term.title()

    if term not in G:
        # Try case-insensitive search
        for node in G.nodes():
            if node.lower() == term.lower():
                term = node
                break
        else:
            return "No medical knowledge found for this term."

    neighbors = list(G.neighbors(term))
    if not neighbors:
        return f"No connections found for {term}."

    # Categorize relationships
    symptoms = []
    diseases = []
    medicines = []
    risks = []

    for neighbor in neighbors:
        edge_data = G.get_edge_data(term, neighbor)
        relation = edge_data.get("relation", "related_to")

        if relation == "symptom_of":
            diseases.append(neighbor)
        elif relation == "treats":
            if term in MEDICINE_NODES:
                diseases.append(neighbor)
            else:
                medicines.append(neighbor)
        elif relation == "risk":
            risks.append(neighbor)
        else:
            # Reverse lookup
            if neighbor in MEDICINE_NODES:
                medicines.append(neighbor)
            else:
                symptoms.append(neighbor)

    response = f"🩺 Medical Knowledge for **{term}**:\n\n"

    if diseases:
        response += "**Associated Conditions:**\n"
        for d in diseases:
            response += f"- {d}\n"

    if symptoms:
        response += "\n**Related Symptoms:**\n"
        for s in symptoms:
            response += f"- {s}\n"

    if medicines:
        response += "\n**Treatment Options:**\n"
        for m in medicines:
            response += f"- {m}\n"

    if risks:
        response += "\n**Risk Factors:**\n"
        for r in risks:
            response += f"- {r}\n"

    response += "\n⚠️ *This is AI-generated guidance only. Always consult a healthcare professional for diagnosis and treatment.*"
    return response


# List of known medicine nodes for better categorization
MEDICINE_NODES = {
    "Paracetamol", "Aspirin", "Metformin", "Insulin", "Amlodipine", "Losartan",
    "Atorvastatin", "Furosemide", "Ramipril", "Metoprolol", "Amoxicillin",
    "Azithromycin", "Salbutamol", "Budesonide", "Tiotropium", "Pantoprazole",
    "Omeprazole", "Sucralfate", "Mebeverine", "ORS", "Ondansetron", "Levothyroxine",
    "Methimazole", "Methotrexate", "Glucosamine", "Colchicine", "Allopurinol",
    "Pregabalin", "Duloxetine", "Sumatriptan", "Naproxen", "Levetiracetam",
    "Betahistine", "Meclizine", "Escitalopram", "Sertraline", "Paroxetine",
    "Artemether", "Nitrofurantoin", "Hydrocortisone", "Clobetasol", "Acyclovir",
    "Tamsulosin", "Finasteride", "Ferrous Sulphate", "Vitamin B12", "Cetirizine",
    "Oseltamivir", "Rivaroxaban", "Gabapentin", "Diclofenac"
}


def get_all_diseases() -> list:
    """Return list of all diseases in the knowledge graph."""
    # Diseases are nodes that have 'symptom_of' edges pointing to them
    diseases = set()
    for u, v, data in G.edges(data=True):
        if data.get("relation") == "symptom_of":
            diseases.add(v)
        elif data.get("relation") == "treats":
            diseases.add(v)
    return list(diseases - MEDICINE_NODES)


def get_all_symptoms() -> list:
    """Return list of all symptoms in the knowledge graph."""
    symptoms = set()
    for u, v, data in G.edges(data=True):
        if data.get("relation") == "symptom_of":
            symptoms.add(u)
    return list(symptoms)


def get_medicines_for_disease(disease: str) -> list:
    """Return list of medicines that treat a given disease."""
    disease = disease.title()
    medicines = []
    for neighbor in G.neighbors(disease):
        edge_data = G.get_edge_data(disease, neighbor)
        if edge_data.get("relation") == "treats":
            medicines.append(neighbor)
    # Also check reverse
    for u, v, data in G.edges(data=True):
        if v == disease and data.get("relation") == "treats":
            medicines.append(u)
    return list(set(medicines) & MEDICINE_NODES)
