from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.compare import to_isomorphic
import hashlib
from pyvis.network import Network
import webbrowser
import os
from rdflib.plugins.sparql import prepareQuery
from rdflib.plugins.parsers.notation3 import BadSyntax
import pyparsing


# Pyvis graph visualization
def visualize_graph(ttl_file, open_in_browser=False):
    # Load TTL file
    g = Graph()
    g.parse(ttl_file, format="turtle")  

    # Namespace
    CCCEV = Namespace("http://data.europa.eu/m8g/")
    CPSV = Namespace("http://purl.org/vocab/cpsv#")
    SC = Namespace("http://example.org/schema#")

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

# shacl shape syntax deep check
def validate_shacl_syntax(shacl_ttl_string):
    """
    Checks syntactic validity of a SHACL file on three levels:
    1. RDF/Turtle Syntax
    2. SHACL Structure (Basic)
    3. Embedded SPARQL Syntax
    
    Returns: (is_valid (bool), error_stage (str), error_message (str))
    """
    def shape_name(uri):
        # Helper to make error messages readable
        return uri.split("#")[-1] if "#" in uri else uri.split("/")[-1]
    
    g = Graph()
    
    # --- LEVEL 1: RDF Syntax ---
    try:
        g.parse(data=shacl_ttl_string, format="turtle")
    except (BadSyntax, Exception) as e:
        return False, "RDF_SYNTAX", str(e).replace("\n", " ")

    # Extract namespaces to help the SPARQL parser later
    namespaces = dict(g.namespaces())
    
    # --- LEVEL 2: Embedded SPARQL Syntax ---
    # We query the graph to find every 'sh:select' string
    query_finder = """
        PREFIX sh: <http://www.w3.org/ns/shacl#>
        SELECT ?shape ?sparql
        WHERE {
            ?shape sh:select ?sparql .
        }
    """
    
    try:
        results = g.query(query_finder)        
        for row in results:
            shape_uri = str(row.shape)
            sparql_string = str(row.sparql)
            
            try:
                # Attempt to compile the SPARQL string
                prepareQuery(sparql_string, initNs=namespaces)
                
            except pyparsing.ParseException as pe:
                # This captures syntax errors like missing brackets } or bad keywords
                return False, "SPARQL_SYNTAX", f"Shape {shape_name(shape_uri)}: {pe}"
            except Exception as e:
                return False, "SPARQL_OTHER", f"Shape {shape_name(shape_uri)}: {str(e)}"
                
    except Exception as e:
        return False, "QUERY_EXTRACTION", str(e)

    # If we survived all checks
    return True, "VALID", "OK"

