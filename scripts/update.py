import argparse
import logging
import os
import shutil
from typing import cast
from pathlib import Path

import requests

from rdflib import Graph, URIRef, Node, SKOS

import queries

logger = logging.getLogger(__name__)

UPSTREAM_DATA_DIR = Path('upstream')
OGC_DATA_DIR = Path('ogc')
SOURCES = {
    'vocabularies': [
        'geosciml',
        'earthresourceml'
    ],
    'root': [
        'catalogue.ttl',
    ],
}
URI_SOURCE = 'http://resource.geosciml.org/'
URI_TARGET = 'https://www.opengis.net/def/geosciml/'


def _main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Skip SPARQL upload')
    args = parser.parse_args()

    if not args.dry_run:
        missing = [v for v in ('SPARQL_GSP_ENDPOINT', 'GRAPH_URI') if v not in os.environ]
        if missing:
            raise EnvironmentError(f"Missing required environment variable(s): {', '.join(missing)}")

    if OGC_DATA_DIR.exists():
        shutil.rmtree(OGC_DATA_DIR)
        logger.info("Cleared %s", OGC_DATA_DIR)

    all_g = Graph()
    for source_type, vocabs in SOURCES.items():
        for vocab in vocabs:
            if source_type == 'root':
                upstream_dir = UPSTREAM_DATA_DIR / vocab
            else:
                upstream_dir = UPSTREAM_DATA_DIR / source_type / vocab
            if not upstream_dir.exists():
                logger.warning("Upstream directory %s does not exist, skipping", upstream_dir)
                continue

            if upstream_dir.is_file():
                ttl_files = [upstream_dir]
            else:
                ttl_files = list(upstream_dir.rglob('*.ttl'))
            logger.info("Processing '%s/%s': found %d TTL file(s)", source_type, vocab, len(ttl_files))

            for fn in ttl_files:
                logger.info("  Parsing %s", fn)
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

                for query in queries.ENTAILMENTS:
                    new_g.update(query)

                out_fn = OGC_DATA_DIR / fn.relative_to(UPSTREAM_DATA_DIR)
                out_fn.parent.mkdir(parents=True, exist_ok=True)
                new_g.serialize(destination=out_fn, format='turtle')
                logger.info("  Written %d triples to %s", len(new_g), out_fn)
                for triple in new_g.triples((None, None, None)):
                    all_g.add(triple)

    logger.info("Total triples across all vocabs: %d", len(all_g))

    if args.dry_run:
        logger.info("Dry run — skipping upload")
    else:
        sparql_endpoint = os.environ['SPARQL_GSP_ENDPOINT']
        graph_uri = os.environ['GRAPH_URI']
        sparql_auth = ((os.environ['SPARQL_USERNAME'], os.environ.get('SPARQL_PASSWORD', ''))
                       if 'SPARQL_USERNAME' in os.environ else None)

        logger.info("Uploading graph to %s (graph URI: %s)", sparql_endpoint, graph_uri)
        response = requests.put(
            sparql_endpoint,
            params={'graph': graph_uri},
            data=all_g.serialize(format='turtle'),
            headers={'Content-Type': 'text/turtle'},
            auth=sparql_auth,
        )
        response.raise_for_status()
        logger.info("Upload complete (HTTP %d)", response.status_code)


if __name__ == '__main__':
    _main()
