"""
knowledge_graph/graph.py
========================
Expanded Medical Knowledge Graph — NetworkX undirected graph.

ORIGINAL (5 clusters, 17 nodes):
    Fever, Diabetes, BP, Cold, Headache clusters

EXPANDED (15 disease clusters + 6 general health clusters = 21 clusters, 120+ nodes):
    Every disease in the symptom_map is now a cluster:
      1.  Fever / Viral Infection
      2.  Diabetes
      3.  Hypertension / Blood Pressure
      4.  Common Cold
      5.  Headache / Migraine
      6.  Flu / Influenza
      7.  COVID-19
      8.  Malaria
      9.  Muscle Strain
     10.  Anxiety
     11.  Anaemia
     12.  Gastroenteritis
     13.  Asthma
     14.  Urinary Tract Infection
     15.  Dengue Fever
    + 6 general condition clusters:
     16.  Acidity / GERD
     17.  Thyroid
     18.  Kidney
     19.  Liver
     20.  Cholesterol / Heart
     21.  Skin

query_graph(node) — returns a formatted string of all neighbours of node,
or None if node not found in the graph.
"""

import networkx as nx

G = nx.Graph()

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 1: Fever / Viral Infection
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Fever",            "Viral Infection"),
    ("Fever",            "High Temperature"),
    ("Fever",            "Chills"),
    ("Fever",            "Sweating"),
    ("Fever",            "Body Ache"),
    ("Fever",            "Fatigue"),
    ("Fever",            "Dehydration"),
    ("Viral Infection",  "Immune System"),
    ("Viral Infection",  "Inflammation"),
    ("Viral Infection",  "Paracetamol"),
    ("Viral Infection",  "Rest"),
    ("High Temperature", "Febrile Seizure"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 2: Diabetes
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Diabetes",          "High Blood Sugar"),
    ("Diabetes",          "Insulin"),
    ("Diabetes",          "Frequent Urination"),
    ("Diabetes",          "Excessive Thirst"),
    ("Diabetes",          "Blurred Vision"),
    ("Diabetes",          "Fatigue"),
    ("Diabetes",          "Metformin"),
    ("Diabetes",          "HbA1c"),
    ("Diabetes",          "Type 2 Diabetes"),
    ("Diabetes",          "Type 1 Diabetes"),
    ("Diabetes",          "Prediabetes"),
    ("Diabetes",          "Pancreas"),
    ("High Blood Sugar",  "Hyperglycemia"),
    ("Insulin",           "Pancreas"),
    ("Insulin",           "Blood Sugar Control"),
    ("Type 2 Diabetes",   "Obesity"),
    ("Type 2 Diabetes",   "Insulin Resistance"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 3: Hypertension / Blood Pressure
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Hypertension",      "High Blood Pressure"),
    ("Hypertension",      "Heart Disease"),
    ("Hypertension",      "Stroke"),
    ("Hypertension",      "Dizziness"),
    ("Hypertension",      "Chest Pain"),
    ("Hypertension",      "Amlodipine"),
    ("Hypertension",      "Systolic Pressure"),
    ("Hypertension",      "Diastolic Pressure"),
    ("Hypertension",      "Kidney Damage"),
    ("BP",                "Hypertension"),
    ("BP",                "Low Blood Pressure"),
    ("BP",                "Blood Pressure Monitor"),
    ("High Blood Pressure","Salt Restriction"),
    ("High Blood Pressure","Exercise"),
    ("Heart Disease",     "Coronary Artery"),
    ("Heart Disease",     "Cholesterol"),
    ("Stroke",            "Brain"),
    ("Stroke",            "Clot"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 4: Common Cold
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Cold",            "Common Cold"),
    ("Cold",            "Cough"),
    ("Cold",            "Runny Nose"),
    ("Cold",            "Sneezing"),
    ("Cold",            "Sore Throat"),
    ("Cold",            "Nasal Congestion"),
    ("Cold",            "Rhinovirus"),
    ("Common Cold",     "Cetirizine"),
    ("Common Cold",     "Paracetamol"),
    ("Common Cold",     "Steam Inhalation"),
    ("Cough",           "Throat Irritation"),
    ("Cough",           "Cough Syrup"),
    ("Runny Nose",      "Antihistamine"),
    ("Sore Throat",     "Strepsils"),
    ("Sore Throat",     "Gargling"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 5: Headache / Migraine
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Headache",          "Migraine"),
    ("Headache",          "Stress"),
    ("Headache",          "Tension Headache"),
    ("Headache",          "Dehydration"),
    ("Headache",          "Eye Strain"),
    ("Headache",          "Paracetamol"),
    ("Migraine",          "Aura"),
    ("Migraine",          "Light Sensitivity"),
    ("Migraine",          "Nausea"),
    ("Migraine",          "Sumatriptan"),
    ("Migraine",          "Triggers"),
    ("Migraine",          "Throbbing Pain"),
    ("Tension Headache",  "Neck Stiffness"),
    ("Stress",            "Cortisol"),
    ("Stress",            "Anxiety"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 6: Flu / Influenza
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Flu",             "Influenza"),
    ("Flu",             "Fever"),
    ("Flu",             "Body Pain"),
    ("Flu",             "Severe Fatigue"),
    ("Flu",             "Oseltamivir"),
    ("Flu",             "Influenza Virus"),
    ("Flu",             "Flu Vaccine"),
    ("Flu",             "Muscle Ache"),
    ("Influenza",       "Type A Influenza"),
    ("Influenza",       "Type B Influenza"),
    ("Influenza",       "Respiratory Infection"),
    ("Flu Vaccine",     "Immunity"),
    ("Oseltamivir",     "Antiviral"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 7: COVID-19
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("COVID",             "COVID-19"),
    ("COVID",             "SARS-CoV-2"),
    ("COVID",             "Loss of Smell"),
    ("COVID",             "Loss of Taste"),
    ("COVID",             "Dry Cough"),
    ("COVID",             "Fever"),
    ("COVID",             "Breathlessness"),
    ("COVID",             "Paracetamol"),
    ("COVID",             "Isolation"),
    ("COVID",             "Vitamin D"),
    ("COVID-19",          "Long COVID"),
    ("COVID-19",          "Oxygen Saturation"),
    ("COVID-19",          "PCR Test"),
    ("COVID-19",          "Vaccination"),
    ("Loss of Smell",     "Anosmia"),
    ("Breathlessness",    "Pulmonary"),
    ("Vaccination",       "Covishield"),
    ("Vaccination",       "Covaxin"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 8: Malaria
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Malaria",           "Plasmodium"),
    ("Malaria",           "Fever"),
    ("Malaria",           "Chills"),
    ("Malaria",           "Profuse Sweating"),
    ("Malaria",           "Artemether"),
    ("Malaria",           "Lumefantrine"),
    ("Malaria",           "Anopheles Mosquito"),
    ("Malaria",           "Blood Smear Test"),
    ("Malaria",           "Spleen Enlargement"),
    ("Malaria",           "Cerebral Malaria"),
    ("Plasmodium",        "Plasmodium Falciparum"),
    ("Plasmodium",        "Plasmodium Vivax"),
    ("Artemether",        "Antimalarial"),
    ("Anopheles Mosquito","Mosquito Net"),
    ("Anopheles Mosquito","Repellent"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 9: Muscle Strain
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Muscle Strain",     "Leg Pain"),
    ("Muscle Strain",     "Muscle Pain"),
    ("Muscle Strain",     "Muscle Spasm"),
    ("Muscle Strain",     "Inflammation"),
    ("Muscle Strain",     "Diclofenac"),
    ("Muscle Strain",     "Rest and Ice"),
    ("Muscle Strain",     "Physiotherapy"),
    ("Muscle Strain",     "Overexertion"),
    ("Leg Pain",          "Cramps"),
    ("Leg Pain",          "Deep Vein Thrombosis"),
    ("Muscle Pain",       "DOMS"),
    ("Muscle Pain",       "Electrolyte Imbalance"),
    ("Diclofenac",        "NSAID"),
    ("NSAID",             "Ibuprofen"),
    ("NSAID",             "Naproxen"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 10: Anxiety
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Anxiety",           "Panic Attack"),
    ("Anxiety",           "Palpitations"),
    ("Anxiety",           "Sweating"),
    ("Anxiety",           "Shortness of Breath"),
    ("Anxiety",           "Dizziness"),
    ("Anxiety",           "Escitalopram"),
    ("Anxiety",           "Stress"),
    ("Anxiety",           "Generalised Anxiety Disorder"),
    ("Anxiety",           "Cognitive Behavioural Therapy"),
    ("Anxiety",           "Mindfulness"),
    ("Panic Attack",      "Adrenaline"),
    ("Panic Attack",      "Hyperventilation"),
    ("Palpitations",      "Heart Rate"),
    ("Escitalopram",      "SSRI"),
    ("SSRI",              "Serotonin"),
    ("Generalised Anxiety Disorder", "Worrying"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 11: Anaemia
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Anemia",            "Iron Deficiency"),
    ("Anemia",            "Low Hemoglobin"),
    ("Anemia",            "Fatigue"),
    ("Anemia",            "Pale Skin"),
    ("Anemia",            "Weakness"),
    ("Anemia",            "Dizziness"),
    ("Anemia",            "Ferrous Sulphate"),
    ("Anemia",            "Vitamin B12"),
    ("Anemia",            "Folic Acid"),
    ("Anemia",            "RBC Count"),
    ("Iron Deficiency",   "Diet"),
    ("Iron Deficiency",   "Iron Rich Foods"),
    ("Low Hemoglobin",    "Hemoglobin Test"),
    ("Ferrous Sulphate",  "Iron Supplement"),
    ("Vitamin B12",       "Methylcobalamin"),
    ("Vitamin B12",       "Nerve Function"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 12: Gastroenteritis
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Gastroenteritis",   "Nausea"),
    ("Gastroenteritis",   "Vomiting"),
    ("Gastroenteritis",   "Diarrhea"),
    ("Gastroenteritis",   "Stomach Pain"),
    ("Gastroenteritis",   "Dehydration"),
    ("Gastroenteritis",   "ORS"),
    ("Gastroenteritis",   "Ondansetron"),
    ("Gastroenteritis",   "Food Poisoning"),
    ("Gastroenteritis",   "Norovirus"),
    ("Gastroenteritis",   "Rotavirus"),
    ("Diarrhea",          "Loose Stools"),
    ("Diarrhea",          "Electrolytes"),
    ("Nausea",            "Antiemetic"),
    ("ORS",               "Oral Rehydration"),
    ("Food Poisoning",    "Bacteria"),
    ("Food Poisoning",    "Contaminated Food"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 13: Asthma
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Asthma",            "Wheezing"),
    ("Asthma",            "Breathlessness"),
    ("Asthma",            "Chest Tightness"),
    ("Asthma",            "Cough"),
    ("Asthma",            "Salbutamol Inhaler"),
    ("Asthma",            "Budesonide Inhaler"),
    ("Asthma",            "Bronchospasm"),
    ("Asthma",            "Allergens"),
    ("Asthma",            "Dust Mites"),
    ("Asthma",            "Peak Flow Meter"),
    ("Wheezing",          "Airway Narrowing"),
    ("Bronchospasm",      "Smooth Muscle"),
    ("Salbutamol Inhaler","Bronchodilator"),
    ("Budesonide Inhaler","Corticosteroid"),
    ("Allergens",         "Pollen"),
    ("Allergens",         "Pet Dander"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 14: Urinary Tract Infection
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Urinary Tract Infection", "Burning Urination"),
    ("Urinary Tract Infection", "Frequent Urination"),
    ("Urinary Tract Infection", "Lower Back Pain"),
    ("Urinary Tract Infection", "Cloudy Urine"),
    ("Urinary Tract Infection", "Nitrofurantoin"),
    ("Urinary Tract Infection", "E. Coli"),
    ("Urinary Tract Infection", "Urine Culture"),
    ("Urinary Tract Infection", "Bladder Infection"),
    ("Urinary Tract Infection", "Kidney Infection"),
    ("UTI",                     "Urinary Tract Infection"),
    ("Burning Urination",       "Dysuria"),
    ("E. Coli",                 "Bacteria"),
    ("Bladder Infection",       "Cystitis"),
    ("Nitrofurantoin",          "Antibiotic"),
    ("Kidney Infection",        "Pyelonephritis"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 15: Dengue Fever
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Dengue",              "Dengue Fever"),
    ("Dengue",              "High Fever"),
    ("Dengue",              "Skin Rash"),
    ("Dengue",              "Joint Pain"),
    ("Dengue",              "Severe Headache"),
    ("Dengue",              "Paracetamol"),
    ("Dengue",              "Aedes Mosquito"),
    ("Dengue",              "Platelet Count"),
    ("Dengue",              "Dengue NS1 Test"),
    ("Dengue",              "ORS"),
    ("Dengue Fever",        "Dengue Hemorrhagic Fever"),
    ("Dengue Fever",        "Dengue Shock Syndrome"),
    ("Aedes Mosquito",      "Mosquito Net"),
    ("Aedes Mosquito",      "Repellent"),
    ("Platelet Count",      "Thrombocytopenia"),
    ("Skin Rash",           "Petechiae"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 16: Acidity / GERD
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Acidity",           "GERD"),
    ("Acidity",           "Heartburn"),
    ("Acidity",           "Acid Reflux"),
    ("Acidity",           "Stomach Acid"),
    ("Acidity",           "Omeprazole"),
    ("Acidity",           "Antacid"),
    ("Acidity",           "H. Pylori"),
    ("Acidity",           "Spicy Food"),
    ("Acidity",           "Bloating"),
    ("GERD",              "Gastroesophageal Reflux"),
    ("GERD",              "Esophagus"),
    ("Heartburn",         "Chest Burning"),
    ("Omeprazole",        "Proton Pump Inhibitor"),
    ("Antacid",           "Pantoprazole"),
    ("Antacid",           "Ranitidine"),
    ("H. Pylori",         "Gastric Ulcer"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 17: Thyroid
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Thyroid",           "Hypothyroidism"),
    ("Thyroid",           "Hyperthyroidism"),
    ("Thyroid",           "TSH"),
    ("Thyroid",           "T3"),
    ("Thyroid",           "T4"),
    ("Thyroid",           "Goiter"),
    ("Thyroid",           "Fatigue"),
    ("Thyroid",           "Weight Gain"),
    ("Hypothyroidism",    "Levothyroxine"),
    ("Hypothyroidism",    "Low Metabolism"),
    ("Hypothyroidism",    "Hair Loss"),
    ("Hyperthyroidism",   "Methimazole"),
    ("Hyperthyroidism",   "Rapid Heartbeat"),
    ("Hyperthyroidism",   "Weight Loss"),
    ("TSH",               "Pituitary Gland"),
    ("Goiter",            "Iodine Deficiency"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 18: Kidney
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Kidney",            "Kidney Stone"),
    ("Kidney",            "Kidney Infection"),
    ("Kidney",            "Creatinine"),
    ("Kidney",            "Kidney Failure"),
    ("Kidney",            "Lower Back Pain"),
    ("Kidney",            "Frequent Urination"),
    ("Kidney Stone",      "Renal Calculi"),
    ("Kidney Stone",      "Severe Back Pain"),
    ("Kidney Stone",      "Blood in Urine"),
    ("Kidney Stone",      "Tamsulosin"),
    ("Kidney Failure",    "Dialysis"),
    ("Kidney Failure",    "Swelling"),
    ("Creatinine",        "GFR"),
    ("Creatinine",        "Kidney Function Test"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 19: Liver
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Liver",             "Jaundice"),
    ("Liver",             "Hepatitis"),
    ("Liver",             "Fatty Liver"),
    ("Liver",             "Liver Cirrhosis"),
    ("Liver",             "SGPT"),
    ("Liver",             "SGOT"),
    ("Jaundice",          "Yellow Skin"),
    ("Jaundice",          "Yellow Eyes"),
    ("Jaundice",          "Bilirubin"),
    ("Hepatitis",         "Hepatitis A"),
    ("Hepatitis",         "Hepatitis B"),
    ("Hepatitis",         "Hepatitis C"),
    ("Fatty Liver",       "Obesity"),
    ("Fatty Liver",       "Alcohol"),
    ("Liver Cirrhosis",   "Fibrosis"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 20: Cholesterol / Heart
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Cholesterol",       "LDL"),
    ("Cholesterol",       "HDL"),
    ("Cholesterol",       "Triglycerides"),
    ("Cholesterol",       "Heart Disease"),
    ("Cholesterol",       "Atorvastatin"),
    ("Cholesterol",       "Rosuvastatin"),
    ("LDL",               "Bad Cholesterol"),
    ("HDL",               "Good Cholesterol"),
    ("Atorvastatin",      "Statin"),
    ("Rosuvastatin",      "Statin"),
    ("Triglycerides",     "Fatty Acids"),
    ("Heart Disease",     "Coronary Artery Disease"),
    ("Heart Disease",     "Heart Attack"),
    ("Heart Attack",      "Myocardial Infarction"),
    ("Heart Attack",      "ECG"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cluster 21: Skin
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Skin",              "Rash"),
    ("Skin",              "Acne"),
    ("Skin",              "Eczema"),
    ("Skin",              "Psoriasis"),
    ("Skin",              "Itching"),
    ("Rash",              "Allergic Reaction"),
    ("Rash",              "Antihistamine"),
    ("Acne",              "Pimples"),
    ("Acne",              "Clindamycin Gel"),
    ("Eczema",            "Dermatitis"),
    ("Eczema",            "Moisturiser"),
    ("Psoriasis",         "Autoimmune"),
    ("Psoriasis",         "Steroid Cream"),
    ("Itching",           "Calamine Lotion"),
    ("Itching",           "Cetirizine"),
])

# ─────────────────────────────────────────────────────────────────────────────
# Cross-cluster bridges (shared symptoms / related conditions)
# ─────────────────────────────────────────────────────────────────────────────
G.add_edges_from([
    ("Fatigue",           "Anemia"),
    ("Fatigue",           "Diabetes"),
    ("Fatigue",           "Thyroid"),
    ("Fatigue",           "Viral Infection"),
    ("Dizziness",         "Anemia"),
    ("Dizziness",         "Hypertension"),
    ("Dizziness",         "Anxiety"),
    ("Dehydration",       "Fever"),
    ("Dehydration",       "Gastroenteritis"),
    ("Dehydration",       "Dengue"),
    ("Obesity",           "Diabetes"),
    ("Obesity",           "Hypertension"),
    ("Obesity",           "Fatty Liver"),
    ("Cough",             "Asthma"),
    ("Cough",             "Cold"),
    ("Shortness of Breath", "Asthma"),
    ("Shortness of Breath", "Anxiety"),
    ("Joint Pain",        "Dengue"),
    ("Joint Pain",        "Muscle Strain"),
])


# ─────────────────────────────────────────────────────────────────────────────
# query_graph — public API used by app.py
# ─────────────────────────────────────────────────────────────────────────────
def query_graph(node: str) -> str | None:
    """
    Return a formatted string of all neighbours for the given node,
    or None if the node is not in the graph.

    Accepts any capitalisation — tries exact match first,
    then case-insensitive match.
    """
    if not node:
        return None

    # Exact match
    if G.has_node(node):
        matched = node
    else:
        # Case-insensitive fallback
        node_lower = node.lower()
        matched = next(
            (n for n in G.nodes() if n.lower() == node_lower),
            None
        )
        if matched is None:
            # Partial / substring match as last resort
            matched = next(
                (n for n in G.nodes() if node_lower in n.lower()),
                None
            )

    if matched is None:
        return None

    neighbours = list(G.neighbors(matched))
    if not neighbours:
        return None

    neighbour_str = ", ".join(sorted(neighbours))
    return (
        f"Medical Knowledge Graph — '{matched}':\n"
        f"Related concepts: {neighbour_str}\n"
        f"(Total connections: {len(neighbours)})"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Quick stats (printed when module is run directly)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"Nodes : {G.number_of_nodes()}")
    print(f"Edges : {G.number_of_edges()}")
    print()
    # Test a few queries
    for term in ["Diabetes", "Acidity", "Dengue", "Thyroid", "Asthma", "UTI", "Unknown"]:
        result = query_graph(term)
        print(f"query_graph('{term}'):")
        print(f"  {result}")
        print()