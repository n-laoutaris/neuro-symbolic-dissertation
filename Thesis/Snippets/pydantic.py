class Paths(BaseModel):
    path: List[str]
    datatype: str
    
class InformationConcept(BaseModel):
    name: str
    related_paths: List[Paths]  
    
class Constraint(BaseModel):
    name: str
    desc: str
    constrains: List[InformationConcept]  

schema = list[Constraint]