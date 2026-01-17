"""Core pipeline module for the neuro-symbolic dissertation, orchestrating LLM-based SHACL generation and validation."""

# Standard library imports
import json
import time

# Third-party imports
from pydantic import BaseModel
from rdflib import Graph, Namespace
from typing import List

# Local imports
from src.graph_utils import get_semantic_hash, resolve_node_path, validate_shacl_syntax, visualize_graph
from src.llm_utils import call_gemini, call_gemini_json, call_gemini_pdf, initialize_gemini_client, reflect, with_retries
from src.parsing_utils import read_txt

# Constants for Turtle graph prefixes
PREFIXES = """@prefix ex: <http://example.org/> .
@prefix cccev: <http://data.europa.eu/m8g/> .
@prefix cpsv: <http://purl.org/vocab/cpsv#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

"""

# Standard headers for SHACL shapes
STANDARD_HEADERS = """
@prefix : <http://example.org/schema#> .
@prefix ex: <http://example.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
"""

def run_main_pipeline(ctx, artifact_dir: str, progress_bar, DOCUMENT_NAME: str, PROMPT_VERSION: str, GEMINI_MODEL: str, current_run_id: int):
    """Runs the main neuro-symbolic pipeline for SHACL generation and validation.

    Orchestrates the end-to-end process: document summarization, information model creation,
    graph generation, SHACL synthesis, validation, visualization.

    Args:
        ctx: Context dictionary to store results and metadata.
        artifact_dir: Directory to save generated artifacts.
        progress_bar: Progress bar object for updates.
        DOCUMENT_NAME: Name of the document being processed.
        PROMPT_VERSION: Version of prompts to use.
        GEMINI_MODEL: Gemini model name for LLM calls.
        current_run_id: ID of the current experiment run.

    Returns:
        Updated context dictionary with results and execution time.
    """
    # Initialize Gemini client
    initialize_gemini_client(model_name=GEMINI_MODEL)

    execution_start_time = time.time()

    ### 1.1 Document → Preconditions Summary
    progress_bar.set_description(f"Run {current_run_id}: Generating Preconditions Summary...")

    file_path = f"Precondition documents/{DOCUMENT_NAME}.pdf"
    prompt = read_txt(f'Prompts/{PROMPT_VERSION}/summarization.txt')
    preconditions_summary = with_retries(call_gemini_pdf, prompt, file_path)
    # Optional: reflexion
    if PROMPT_VERSION == 'Reflexion':
        preconditions_summary = reflect([prompt], preconditions_summary)

    # Save artifact
    with open(f"{artifact_dir}/{DOCUMENT_NAME} preconditions summary.txt", "w") as f:
        f.write(preconditions_summary)

    ### 1.2. Preconditions Summary + Citizen Schema (TTL) → Information Model (JSON)
    progress_bar.set_description(f"Run {current_run_id}: Generating Information Model...")

    citizen_schema = read_txt(f"Citizens/{DOCUMENT_NAME} schema.ttl")

    class Paths(BaseModel):
        path: List[str]
        datatype: str

    class InformationConcept(BaseModel):
        name: str
        related_paths: List[Paths]  # Links the concept to citizen data available

    class Constraint(BaseModel):
        name: str
        desc: str
        constrains: List[InformationConcept]

    schema = list[Constraint]

    # Formulate prompt content and call Gemini
    prompt = read_txt(f'Prompts/{PROMPT_VERSION}/preconditions_to_JSON.txt')
    content = [prompt, preconditions_summary, citizen_schema]
    info_model_str = with_retries(call_gemini_json, content, schema)
    # Optional: reflexion
    if PROMPT_VERSION == 'Reflexion':
        info_model_str = reflect(content, info_model_str, schema)

    # Save artifact
    with open(f"{artifact_dir}/{DOCUMENT_NAME} information model.json", "w") as f:
        f.write(info_model_str)

    ### 1.3 Information Model (JSON) → Public Service Graph (TTL)
    # Parse JSON string
    info_model = json.loads(info_model_str)
    service_name = DOCUMENT_NAME

    triples = [PREFIXES]
    triples.append(f"ex:{service_name} a cpsv:PublicService .\n\n")

    # Convert constraints + concepts into triples
    for constraint in info_model:
        constraint_name = constraint["name"]
        constraint_desc = constraint["desc"].replace('"', '\\"')

        # Public service -> holdsRequirement -> constraint
        triples.append(f"ex:{service_name} cpsv:holdsRequirement ex:{constraint_name} .\n")

        # Constraint node
        triples.append(f'ex:{constraint_name} a cccev:Constraint ; dct:description "{constraint_desc}" .\n')

        # InformationConcept nodes
        for concept in constraint.get("constrains", []):
            concept_name = concept["name"]

            # Link constraint to concept
            triples.append(f"ex:{constraint_name} cccev:constrains ex:{concept_name} .\n")

            # Declare information concept
            triples.append(f'ex:{concept_name} a cccev:InformationConcept .\n')

        triples.append("\n")  # Spacing for readability

    service_graph_ttl = "".join(triples)

    # Log semantic hash
    ctx["Service Graph Hash"] = get_semantic_hash(service_graph_ttl)

    # Save artifact
    with open(f"{artifact_dir}/{DOCUMENT_NAME} service graph.ttl", "w") as f:
        f.write(service_graph_ttl)

    ### 1.4. Graph Visualization / Inspection
    visualize_graph(f"{artifact_dir}/{DOCUMENT_NAME} service graph.ttl")  # Also saves its own HTML artifact

    ### 2.1. Information Model (JSON) → SHACL-spec (JSON)
    shacl_spec_json = []

    for constraint in info_model:
        # Rename for clarity downstream
        shape_name = constraint["name"].replace("_condition", "_shape")
        desc = constraint["desc"]

        concepts = []
        # Iterate concepts (e.g., family_income, residency_city)
        for concept in constraint.get("constrains", []):
            related_paths = []

            paths_source = concept.get("related_paths", [])

            for rp in paths_source:
                # Capture the path and datatype (URI vs Literal)
                related_paths.append({
                    "path": rp["path"],
                    "datatype": rp["datatype"]
                })

            concepts.append({
                "name": concept["name"],
                "related_paths": related_paths
            })

        shacl_spec_json.append({
            "shape_name": shape_name,
            "desc": desc,
            "concepts": concepts
        })

    # Save artifact
    with open(f"{artifact_dir}/{DOCUMENT_NAME} shacl-spec.json", "w") as f:
        json.dump(shacl_spec_json, f, indent=2)

    ### 2.2. SHACL-spec (JSON) + Citizen Schema (TTL) → SHACL Shapes (TTL)
    progress_bar.set_description(f"Run {current_run_id}: Generating SHACL Shapes...")

    # Convert JSON to string for prompt
    shacl_spec_str = json.dumps(shacl_spec_json)
    prompt = read_txt(f'Prompts/{PROMPT_VERSION}/shacl_spec_to_shacl_ttl.txt')
    content = [prompt, shacl_spec_str, citizen_schema]

    shacl_shapes = with_retries(call_gemini, content)
    # Optional: reflexion
    if PROMPT_VERSION == 'Reflexion':
        shacl_shapes = reflect(content, shacl_shapes)

    # Cleanup Gemini markdown formatting
    shacl_shapes = shacl_shapes.strip("`").replace("turtle", "").replace("ttl", "").strip()

    # Strip existing headers to avoid duplicates/conflicts
    lines = shacl_shapes.split('\n')
    body_lines = [line for line in lines if not line.strip().lower().startswith('@prefix')]
    clean_body = '\n'.join(body_lines)
    # Prepend correct headers
    shacl_shapes = STANDARD_HEADERS + "\n" + clean_body

    # Log validation results
    ctx["SHACL Graph Hash"] = get_semantic_hash(shacl_shapes)
    is_valid, error_stage, error_message = validate_shacl_syntax(shacl_shapes)
    ctx["SHACL Valid Syntax"] = is_valid
    ctx["SHACL Error Type"] = error_stage
    ctx["SHACL Error Message"] = error_message

    # Save artifact
    with open(f"{artifact_dir}/{DOCUMENT_NAME} shacl shapes.ttl", "w") as f:
        f.write(shacl_shapes)

    ### 3.1 Public Service Graph (TTL) + Citizen Graph (TTL) + Information Model (JSON) → Citizen-Service Graph (TTL)
    EX = Namespace("http://example.org/")
    SC = Namespace("http://example.org/schema#")

    # Load service and citizen TTLs and info model
    citizen_ttl = f"Citizens/{DOCUMENT_NAME} eligible.ttl"

    # Realize them into graphs
    unified_graph = Graph()
    unified_graph.parse(data=service_graph_ttl, format="turtle")
    citizen_graph = Graph()
    citizen_graph.parse(citizen_ttl, format="turtle")

    # Merge citizen triples into main graph
    for triple in citizen_graph:
        unified_graph.add(triple)

    # Automatically determine the root citizen node
    root_candidates = list(citizen_graph.subjects(predicate=None, object=SC.Applicant))
    citizen_root = root_candidates[0]

    # Add mapsTo edges
    for constraint in info_model:
        for concept in constraint["constrains"]:
            concept_uri = EX[concept["name"]]

            for path_obj in concept["related_paths"]:
                path_list = path_obj["path"]
                dtype = path_obj["datatype"]

                # Pass the datatype to the resolver
                subject_nodes = resolve_node_path(citizen_graph, citizen_root, path_list, dtype)

                for subj in subject_nodes:
                    # Connect the Information Concept to the Data Node
                    unified_graph.add((concept_uri, EX.mapsTo, subj))

    # Serialize unified graph into TTL and save to file
    unified_graph.serialize(f"{artifact_dir}/{DOCUMENT_NAME} citizen-service graph.ttl", format="turtle")

    ### 3.2 Visualize the unified graph
    visualize_graph(f"{artifact_dir}/{DOCUMENT_NAME} citizen-service graph.ttl")

    # This marks the end of the main pipeline. 
    ctx["Execution Time"] = round(time.time() - execution_start_time)

    return ctx