from gwenlake.api import APIClient
from langchain.text_splitter import RecursiveCharacterTextSplitter


class DocumentTextReader:

    def __init__(self, file):
        try:
            files = {'file': (file, open(file,'rb'))}
            self.document = APIClient().fetch(f"/documents/readtext", files=files, method="post")
        except Exception as e:
            print(e)
    
    def get_content(self):
        return self.document["pages"]

    def get_chunks(self, chunk_size=512, chunk_overlap=50):
        documents = [doc["text"] for doc in self.document["pages"]]
        text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = text_splitter.create_documents(documents)
        return chunks
