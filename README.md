# Exploring Neuro-Symbolic Pipelines for Structured Knowledge Extraction
This repository contains the full implementation, experimental results and the final typeset report of my Master's Dissertation in Data Science. The project introduces a novel Neuro-Symbolic architecture, designed to transform unstructured legislative text into personalized service delivery through a Public Service Recommender System.

![banner](./images/banner.png)

## The Problem
Public administration often seems like a bureaucratic maze. Citizens are legally entitled to various services and benefits to which they remain unaware, a significant accessibility gap that exists due to the complexity and fragmentation of the underlying legislation.

This project approaches this real-world issue as a Data Science challenge. How do we make legal prose machine-readable and validate citizen data against it, without losing the mathematical certainty required for administrative acts? Current AI approaches rely on Large Language Models, which offer linguistic fluency but lack formality and certainly. In digital governance, a hallucination is a potentially catastrophic failure. This work  argues that we must decouple interpretation (Neural) from execution (Symbolic) to ensure accountability.

## Knowledge Sources & Data Models
The project uses:
- Unstructured Knowledge: Natural language regulatory documents defining eligibility conditions for Greek public services (e.g., Special Parental Leave Allowance, Student Housing Allowance).
- Structured Semantics: European Commission standard vocabularies, specifically the Core Public Service Vocabulary (CPSV-AP) and the Core Criterion and Core Evidence Vocabulary (CCCEV), expressed in RDF/Turtle.
- Large Language Models: The neural layer utilizes Gemini 2.5 Flash and Pro through the free version of the API.

## Methodology
This dissertation is composed of four stages:
1. The Extraction & Generation Pipeline: Development of a multi-step workflow that uses LLMs to parse legal PDFs and extract eligibility preconditions. These are mapped to intermediate representations before being synthesized into executable SHACL (Shapes Constraint Language) and SPARQL constraints.
2. Testing & Validation: An execution environment based on PySHACL. The system is evaluated through a custom-built Mutation Testing framework that applies controlled ablations to "Golden" citizen profiles to detect logic collapse. Different prompting strategies and LLMs are tested, keeping logs.
3. Results Data Analysis: Post-hoc statistical analysis of experimental logs. This phase focuses on quantifying the effect of different experimental configurations and assessing the overall real-life feasibility of the project.
4. Report: An analytical written report, typeset in LaTeX, documenting the whole process in a comprehensive way.

## Results and Key Takeaways
The results of the experimental campaign identify that:
- Syntactic Validity was ~80%. LLMs are highly capable of generating code that runs without syntax errors.
- Functional Logic Accuracy collapses to ~25%, especially in cases involving complex dependencies or recursive relationships.
The findings suggest that symbolic grounding  is a prerequisite for trustworthy Digital Governance and outperforms plain use of LLMs.

## Future Work
Scaling: Extending the framework to handle multi-lingual EU legislative corpuses.

## Repository Contents
`Citizens:` Domain-specific ontologies (RDFS) and YAML-based mutation scenarios for the test suites.

`Good results:` A curated collection of successful pipeline artifacts to be used as example outputs.

`Precondition documents:` The raw legislative PDF sources used as input for the extraction phase.

`Prompts:` System instructions for the different pipeline stages and prompting strategies.

`Thesis:` Full LaTeX source code, images and bibliography for the dissertation report. Includes a compiled PDF.

`src:` Core Python code for the execution of the pipeline pipeline, including local libraries for utility code.

`Experimennt Cockpit.ipynb:` The primary interactive environment for pipeline iterations and mutation testing loops.

`Master_Results.csv`: The dataset containing logs for all experimental runs.

`Results Analysis.ipynb`: Data Analysis and visualization of the experimental logs.

## Project Context
This dissertation was submitted as a requirement for the MSc in Data Science at the International Hellenic University.
