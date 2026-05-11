ENTAILMENTS = [
    '''
    PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
    PREFIX schema: <https://schema.org/>
    INSERT { ?s skos:prefLabel ?l }
    WHERE { ?s schema:name ?l }
    '''
]