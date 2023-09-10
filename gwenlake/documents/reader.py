from gwenlake.api import Client


class DocumentTextReader:

    def __init__(self, file):
        try:
            files = {'file': (file, open(file,'rb'))}
            self.document = Client().fetch(f"/documents/textreader", files=files, method="post")
        except Exception as e:
            print(e)
    
    def get_content(self):
        return self.document["pages"]
