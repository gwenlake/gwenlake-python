import logging
from opensearchpy import OpenSearch, helpers

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


logger = logging.getLogger(__name__)


class OpenSearchDocumentStore:

    def __init__(self, uri, index, use_ssl=True, verify_certs=False, ca_certs=None, timeout=30):
        self.client = OpenSearch(uri, http_compress=True, use_ssl=use_ssl, verify_certs=verify_certs, ca_certs=ca_certs, ssl_assert_hostname=False, ssl_show_warn=False)
        self.index_name = index
        self.timeout = timeout

    def count(self, query: str):
        q = { "query": query, "track_total_hits": True, "size": 1 }
        resp = self.client.search(body=q, index=self.index_name, request_timeout=self.timeout)
        return resp['hits']['total']['value']

    def get_by_id(self, id: str):
        try:
            data = self.client.get(id=id, index=self.index_name)
            if "_source" in data:
                return data["_source"]
        except:
            pass
        return None

    def delete(self, ids):
        if not isinstance(ids, list):
            ids = [ids]
        if len(ids)==0:
            logger.warning("No documents to be deleted from OpenSearch.")
            return False
        for id in ids:
            self.client.delete(index=self.index_name, id=id)
        return True

    def add(self, documents, column_id="id"):
        if not isinstance(documents, list):
            documents = [documents]
        if len(documents)==0:
            logger.warning("No documents to be added to OpenSearch.")
            return False
        def _generator(documents):
            for doc in documents:
                yield {"_index" : self.index_name, "_id": doc[column_id], "_source": doc}
        success, failed = helpers.bulk(self.client, _generator(documents))
        if success < len(documents):
            logger.warning(f"Some documents failed to be added to OpenSearch. Failures: {failed}")
        logger.info(f"Indexed {success} documents")
        return True

    def query(self, q, aggs=None, sort=None, page=1, per_page=5000, fields=None, all=False, track_total_hits=True):

        # if all==True:
        #     per_page = 10000

        q = { "query": q, "size": per_page }

        if (page > 1) and (all == False):
            q["from"] = (page-1) * per_page

        if track_total_hits:
            q["track_total_hits"] = True

        if fields:
            q["fields"] = fields

        if aggs:
            q["aggs"]=aggs

        if sort:
            q["sort"] = sort

        # réfléchir au search after pour remplacer le scroll
        # if all:
        #     q["search_after"] = search_after
        
        documents = []

        if not all:
            resp = self.client.search(body=q, index=self.index_name, request_timeout=self.timeout)
            # total = resp['hits']['total']['value']
            documents = [hit["_source"] for hit in resp['hits']['hits']]
            if aggs:
                return documents, resp["aggregations"]
            return documents

        resp = self.client.search(body=q, index=self.index_name, request_timeout=self.timeout, scroll='1m')
        for doc in resp['hits']['hits']:
            documents.append(doc["_source"])
        scroll_id = resp['_scroll_id']
        while len(resp['hits']['hits']):
            resp = self.client.scroll(scroll_id=scroll_id, scroll='1m')
            for doc in resp['hits']['hits']:
                documents.append(doc["_source"])
            if scroll_id != resp["_scroll_id"]:
                self.client.clear_scroll(scroll_id=scroll_id)
                scroll_id = resp['_scroll_id']
        self.client.clear_scroll(scroll_id=scroll_id)
        # total = len(documents)
        # per_page = len(documents)
        # return {"object": "list", "total": total, "page": page, "per_page": per_page, "data": documents}
        return documents
    
