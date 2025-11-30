from rdflib import Namespace, Graph, SH, RDF
import csv

# Helper to parse SHACL validation report
def parse_validation_report(conforms, results_graph, results_text):
    """
    Parses the SHACL validation graph into a flat dictionary for CSV logging.
    """

    # If it passed, return a clean success record
    if conforms:
        return {
            "violation_count": 0,
            "failed_shapes": "None",
            "messages": "None",
            "full_report": "Conforms: True"
        }

    # If it failed, extract details from the graph
    failed_shapes = set()
    messages = []

    # Find all nodes of type sh:ValidationResult
    for result_node in results_graph.subjects(RDF.type, SH.ValidationResult):
        
        # Extract the Shape Name (Source Shape) should return a URI like http://example.org/income_shape
        source_shape = results_graph.value(result_node, SH.sourceShape)
        if source_shape:
            # Split to get just "income_shape"
            shape_name = str(source_shape).split("/")[-1].split("#")[-1]
            failed_shapes.add(shape_name)

        # Extract the Message
        message = results_graph.value(result_node, SH.resultMessage)
        if message:
            messages.append(str(message))

    return {
        "violation_count": len(messages),
        "failed_shapes": "; ".join(sorted(list(failed_shapes))), # Stringify for CSV
        "messages": " | ".join(messages), # Stringify for CSV
        "full_report": results_text # Keep raw text just in case
    }
    

def apply_mutations(base_graph, actions):
    """
    Applies text-based Turtle mutations.
    """
    
    PREFIX_HEADER = """
    @prefix : <http://example.org/schema#> .
    @prefix ex: <http://example.org/> .
    @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
    """
    
    # 1. Clone
    new_graph = Graph()
    for ns in base_graph.namespaces():
        new_graph.bind(ns[0], ns[1])
    for t in base_graph: new_graph.add(t)
    
    for action in actions:        
        # --- ACTION: PATCH NODE (The Clean Way) ---
        if action['type'] == 'patch_node':
            snippet = action['turtle']
            
            # A. Parse the partial snippet
            full_turtle = PREFIX_HEADER + "\n" + snippet
            snippet_graph = Graph()
            try:
                snippet_graph.parse(data=full_turtle, format="turtle")
            except Exception as e:
                raise ValueError(f"Invalid Turtle in patch: {e}")

            # B. Apply the updates line-by-line
            for s, p, o in snippet_graph:
                # 1. Remove the OLD value for this specific property
                #    (Keeps other properties of 's' intact)
                new_graph.remove((s, p, None))
                
                # 2. Add the NEW value
                new_graph.add((s, p, o))

        elif action['type'] == 'no_action':
            pass
            
    return new_graph

# Write to csv
def flush_context_to_csv(context_dict, csv_file):
    # Read headers from the existing file
    with open(csv_file, 'r', encoding='utf-8', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader) # Grabs the first row (the headers)

    # Align data to those headers
    row_data = []
    for h in headers:
        value = context_dict.get(h, "N/A") # safe get with default
        row_data.append(value)

    # Write the row
    with open(csv_file, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(row_data)
        
