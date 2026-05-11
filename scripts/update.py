import logging
import os
from typing import cast
from pathlib import Path

import requests

from rdflib import Graph, URIRef, Node, SKOS

logger = logging.Logger(__name__)

UPSTREAM_DATA_DIR = Path('upstream/vocabularies')
OGC_DATA_DIR = Path('ogc')
VOCABS = 'geosciml', 'earthresourceml'
URI_SOURCE = 'http://resource.geosciml.org/'
URI_TARGET = 'https://www.opengis.net/def/geosciml/'

SPARQL_GSP_ENDPOINT = os.environ['SPARQL_GSP_ENDPOINT']
GRAPH_URI = os.environ['GRAPH_URI']
SPARQL_AUTH = ((os.environ['SPARQL_USERNAME'], os.environ.get('SPARQL_PASSWORD', ''))
               if 'SPARQL_USERNAME' in os.environ else None)


def _main():
    all_g = Graph()
    for vocab in VOCABS:
        upstream_dir = UPSTREAM_DATA_DIR / vocab
        if not upstream_dir.exists():
            logger.warning("%s does not exist", upstream_dir)
            continue

        for fn in upstream_dir.rglob('*.ttl'):
            g = Graph().parse(fn)
            new_g = Graph()
            for triple in g.triples((None, None, None)):
                orig_s = triple[0]
                triple = tuple(URIRef(str(x).replace(URI_SOURCE, URI_TARGET))
                               if isinstance(x, URIRef) else x
                               for x in triple)
                new_g.add(cast(tuple[Node, Node, Node], triple))
                if isinstance(orig_s, URIRef):
                    new_g.add((orig_s, SKOS.exactMatch, triple[0]))
                    new_g.add((triple[0], SKOS.exactMatch, orig_s))
            out_fn = OGC_DATA_DIR / fn.relative_to(UPSTREAM_DATA_DIR)
            out_fn.parent.mkdir(parents=True, exist_ok=True)
            new_g.serialize(destination=out_fn, format='turtle')
            for triple in new_g.triples((None, None, None)):
                all_g.add(triple)

    requests.put(
        SPARQL_GSP_ENDPOINT,
        params={'graph': GRAPH_URI},
        data=all_g.serialize(format='turtle'),
        headers={'Content-Type': 'text/turtle'},
        auth=SPARQL_AUTH,
    ).raise_for_status()


if __name__ == '__main__':
    _main()
