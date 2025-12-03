from rdflib import Graph, Namespace, RDF, RDFS, SH, Literal, BNode
from rdflib.compare import to_isomorphic
import hashlib
from pyvis.network import Network
import webbrowser
import os
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.parsers.notation3 import BadSyntax
import pyparsing

# Namespaces
CCCEV = Namespace("http://data.europa.eu/m8g/")
CPSV = Namespace("http://purl.org/vocab/cpsv#")
SC = Namespace("http://example.org/schema#")

# Pyvis graph visualization
def visualize_graph(ttl_file, open_in_browser=False):
    # Load TTL file
    g = Graph()
    g.parse(ttl_file, format="turtle")  

    net = Network(height="1440px", width="100%", notebook=True, directed=True, cdn_resources='remote')
    net.force_atlas_2based()

    # Just visual effects
    def node_color(uri):
        if (uri, RDF.type, CPSV.PublicService) in g:
            return "gold"
        if (uri, RDF.type, CCCEV.Constraint) in g:
            return "maroon"
        if (uri, RDF.type, CCCEV.InformationConcept) in g:
            return "darkturquoise"
        if (uri, RDF.type, SC.Applicant) in g:
            return "yellowgreen"
        return "lightgrey"

    # Just a way to make the graph more readable
    def node_label(uri):
        if isinstance(uri, Literal):
            return str(uri)

        for lbl in g.objects(uri, RDFS.label):
            return str(lbl)
        for lbl in g.objects(uri, CCCEV.name):
            return str(lbl)

        uri_str = str(uri).rstrip('/') # <--- SAFETY FIX
        if "#" in uri_str:
            return uri_str.split("#")[-1]
        return uri_str.split("/")[-1]

    # Add nodes and edges, skipping rdf:type for extra readability
    for s, p, o in g:
        if p == RDF.type:
            continue

        # Subject
        net.add_node(str(s), label=node_label(s), color=node_color(s))

        # Object
        if isinstance(o, Literal):
            net.add_node(str(o), label=node_label(o), color="beige", shape="box") # if it's a literal put it in a text box instead of a circular node
        else:
            net.add_node(str(o), label=node_label(o), color=node_color(o))

        # Edge
        net.add_edge(str(s), str(o), label=node_label(p), arrows="to")

    html_file = ttl_file.replace("ttl", "html")
    # Render and show
    net.save_graph(html_file)
    if open_in_browser:
        webbrowser.open("file://" + os.path.abspath(html_file)) # Use absolute path for browser


# Hashing Graphs
def get_semantic_hash(rdf_text):
    """
    Parses RDF, canonicalizes it, and returns a hash of the logical structure.
    Ignores formatting, whitespace and line order.
    """
    g = Graph()
    try:
        g.parse(data=rdf_text, format="turtle")
    except Exception as e:
        return "INVALID_RDF"

    iso_g = to_isomorphic(g)
    
    # Generate a deterministic hash based on the sorted triples (the string representation)
    triples = sorted(list(iso_g))
    triples_string = "".join([str(t) for t in triples])
    return hashlib.md5(triples_string.encode('utf-8')).hexdigest()


def validate_shacl_syntax(shacl_ttl_string):
    """
    Checks syntactic validity of a SHACL file on three levels.
    Resolves Blank Nodes to their Parent Shape names for readability.
    """
    g = Graph()
    
    # --- LEVEL 1: RDF Syntax ---
    try:
        g.parse(data=shacl_ttl_string, format="turtle")
    except (BadSyntax, Exception) as e:
        return False, "RDF_SYNTAX", str(e).replace("\n", " ")

    namespaces = dict(g.namespaces())
    
    # --- LEVEL 2: Embedded SPARQL Syntax ---
    # Find the node that holds the query
    query_finder = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?constraintNode ?sparql
        WHERE {
            ?constraintNode sh:select ?sparql .
        }
    """
    
    collected_errors = []
    
    try:
        results = g.query(query_finder)
        
        for row in results:
            constraint_node = row.constraintNode
            sparql_string = str(row.sparql)
            
            # --- THE FIX: Resolve Name ---
            shape_name = "Unknown_Shape"
            
            if isinstance(constraint_node, BNode):
                # It's a Blank Node. Who owns it?
                # Usually linked via sh:sparql
                parents = list(g.subjects(SH.sparql, constraint_node))
                if parents:
                    # Found the parent (e.g., ex:income_shape)
                    shape_name = str(parents[0]).split("#")[-1].split("/")[-1]
                else:
                    # Fallback: maybe it's a property shape with a sparql constraint?
                    # (Less common but possible)
                    parents = list(g.subjects(SH.property, constraint_node))
                    if parents:
                        shape_name = str(parents[0]).split("#")[-1].split("/")[-1] + "_Prop"
            else:
                # It has a URI
                shape_name = str(constraint_node).split("#")[-1].split("/")[-1]

            # --- Compile Check ---
            try:
                prepareQuery(sparql_string, initNs=namespaces)
            except pyparsing.ParseException as pe:
                msg = str(pe).replace("\n", " ").split("(at char")[0].strip()
                collected_errors.append(f"{shape_name}: {msg}")
            except Exception as e:
                msg = str(e).replace("\n", " ")
                collected_errors.append(f"{shape_name}: {msg}")
                
    except Exception as e:
        return False, "QUERY_EXTRACTION", str(e)

    if collected_errors:
        full_report = " | ".join(collected_errors)
        return False, "SPARQL_SYNTAX", full_report

    return True, "VALID", "OK"


# Helper: resolve node paths (return nodes, not literals) 
def resolve_node_path(citizen_g, root_uri, path_list, datatype):
    
    # 1. Determine how deep to go
    if datatype == "URI":
        # For Identity logic (City, Person), the Value IS the Node.
        traversal_parts = path_list
    else:
        # For Value logic (Income, Area), the Value is a Literal. Stop one step BEFORE the literal to get the Node holding it.
        traversal_parts = path_list[:-1]

    # 2. Traverse
    current_nodes = {root_uri}
    
    for part in traversal_parts:
        next_nodes = set()
        pred = SC[part] # Assumes our schema matches the namespace
        
        for node in current_nodes:
            # Find all objects connected by this predicate
            for obj in citizen_g.objects(node, pred):
                # Safety check: Ensure we don't accidentally traverse into a Literal 
                # (unless it's the final step of a URI path, but usually URIs point to URIs)
                if isinstance(obj, Literal) and datatype == "URI":
                     continue # Skip weird data errors
                next_nodes.add(obj)
        
        current_nodes = next_nodes
        
        # Optimization: If dead end, stop early
        if not current_nodes:
            return set()

    return current_nodes