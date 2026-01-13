SELECT ?this (SUM(?income) as ?totalIncome) 
(COUNT(DISTINCT ?child) as ?childCount)
WHERE {
    OPTIONAL {
        { ?this :hasIncome ?inc . ?inc :amount ?income . }
        UNION
        { ?this :hasParent ?p . 
        ?p :hasIncome ?p_inc . 
        ?p_inc :amount ?income . }
    }
    OPTIONAL {
        ?this :hasParent ?parent .
        ?parent :hasChild ?child .
        ?child :isDependent true .
    }
}
GROUP BY ?this